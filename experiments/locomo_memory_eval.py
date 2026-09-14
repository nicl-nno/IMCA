"""Frozen, model-free LoCoMo evidence retrieval and narrow calendar QA.

This is not the official generative QA metric or a leaderboard submission.
Ranking receives conversation text and question only, never released annotations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import statistics
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from conversation_memory import (  # noqa: E402
    PARTICIPANT_MISMATCH_MULTIPLIER,
    PROFILES,
    RULES_VERSION,
    TEMPORAL_OVERLAP_MULTIPLIER,
    ConversationMemory,
)
from inspectable_memory import InspectableMemory, digest  # noqa: E402

COMMIT = "3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376"
DATA_SHA256 = "79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4"
SOURCE_URL = f"https://raw.githubusercontent.com/snap-research/locomo/{COMMIT}/data/locomo10.json"
CATEGORIES = {
    1: "multi_hop",
    2: "temporal",
    3: "open_domain",
    4: "single_hop",
    5: "adversarial",
}
SOURCE_FILES = (
    "python/conversation_memory.py",
    "python/temporal_language.py",
    "python/inspectable_memory.py",
    "experiments/locomo_memory_eval.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def question_id(sample_id: str, index: int) -> str:
    return f"{sample_id}/qa/{index:03d}"


def normalized_ids(entries: list[str]) -> list[str]:
    # Released evidence sometimes combines several IDs in one string and uses :05.
    return sorted(
        {
            f"D{int(a)}:{int(b)}"
            for entry in entries
            for a, b in re.findall(r"D(\d+):(\d+)", entry)
        }
    )


def exact_gold_date(value) -> str | None:
    """Independent scorer parser: full date only; never reused for extraction."""
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", value.strip(), flags=re.I)
    cleaned = " ".join(cleaned.replace(",", " ").split())
    for fmt in ("%d %B %Y", "%B %d %Y", "%d %b %Y", "%b %d %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def evidence_metrics(ids: list[str], gold: list[str]) -> dict:
    hits = [i + 1 for i, item in enumerate(ids) if item in gold]
    overlap = len(set(ids) & set(gold))
    return {
        "hit_at_5": int(bool(hits)),
        "recall_at_5": overlap / len(gold) if gold else None,
        "mrr_at_5": 1 / min(hits) if hits else 0.0,
        "full_evidence_at_5": int(bool(gold) and overlap == len(gold)),
    }


def latency_summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "p50_ms": None, "p95_ms": None}
    ordered = sorted(values)
    return {
        "n": len(values),
        "p50_ms": statistics.median(values),
        "p95_ms": ordered[max(0, (95 * len(values) + 99) // 100 - 1)],
    }


def aggregate(rows: list[dict]) -> dict:
    evidence_rows = [r for r in rows if r["category"] != 5 and r["evidence_ids"]]
    result = {"n": len(evidence_rows)}
    for metric in ("hit_at_5", "recall_at_5", "mrr_at_5", "full_evidence_at_5"):
        result[metric] = (
            statistics.mean(r["metrics"][metric] for r in evidence_rows)
            if evidence_rows
            else None
        )
    return result


def build_manifest(data: list[dict], data_hash: str, repeats: int) -> dict:
    return {
        "dataset_url": SOURCE_URL,
        "dataset_commit": COMMIT,
        "dataset_sha256": data_hash,
        "official_dataset": data_hash == DATA_SHA256,
        "rules_version": RULES_VERSION,
        "source_hashes": {name: sha256(ROOT / name) for name in SOURCE_FILES},
        "question_order": [
            question_id(s["sample_id"], i) for s in data for i in range(len(s["qa"]))
        ],
        "profiles": list(PROFILES),
        "top_k": 5,
        "latency_repeats": repeats,
        "model": None,
        "llm_calls": 0,
        "embedding_calls": 0,
        "inputs": "speaker + raw text + session timestamp; no images or generated observations",
        "bm25": {
            "k1": 1.2,
            "b": 0.75,
            "normalization": "fixed lightweight English suffix rules",
        },
        "temporal_overlap_multiplier": TEMPORAL_OVERLAP_MULTIPLIER,
        "guarded_profile": {
            "base_index": "raw BM25",
            "participant_states": ["supported", "unknown", "mismatch", "not_requested"],
            "unknown_subject": "neutral; never filtered or penalized",
            "explicit_mismatch_multiplier": PARTICIPANT_MISMATCH_MULTIPLIER,
            "unknown_when": (
                "participant penalty disabled when the question starts with When "
                "and has no calendar constraint"
            ),
            "temporal_gate": "bonus only for an explicit question-time overlap",
            "selection_note": (
                "rules and multiplier developed on these same ten conversations; "
                "not a held-out result"
            ),
        },
        "date_reader": "same deterministic abstaining top-1 reader for every profile",
        "evidence_denominator": "all distinct normalized gold IDs, including nonexistent IDs",
        "empty_evidence": "excluded from evidence aggregates; retained in frozen results and audit",
        "adversarial": "lure evidence rate only, not positive recall or answer accuracy",
        "split": "all conversations; descriptive diagnostic, not untouched holdout",
        "timing": "in-process search; median of repeats per question; rotated profile order",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def freeze_retrieval(
    data: list[dict], repeats: int, work: Path
) -> tuple[list[dict], list[dict]]:
    """Annotations cannot reach the memory constructor or search interface."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    rows, inventories = [], []
    for sample_index, sample in enumerate(data):
        journal = InspectableMemory(work / f"conversation-{sample_index}.sqlite")
        try:
            started = time.perf_counter()
            memory = ConversationMemory(
                sample["sample_id"], sample["conversation"], journal
            )
            ingestion_ms = (time.perf_counter() - started) * 1000
            events = [event for episode in memory.episodes for event in episode.events]
            inventories.append(
                {
                    "conversation": sample["sample_id"],
                    "episodes": len(memory.episodes),
                    "events": len(events),
                    "dated_events": sum(bool(e["times"]) for e in events),
                    "time_precisions": dict(
                        Counter(t["precision"] for e in events for t in e["times"])
                    ),
                    "modalities": dict(Counter(e["modality"] for e in events)),
                    "context_links": sum(len(e.context_ids) for e in memory.episodes),
                    "state_assertions": memory.state_assertions,
                    "state_replacements": memory.state_replacements,
                    "ingestion_ms": ingestion_ms,
                    "index_hash": memory.index_hash,
                    "ids": list(memory.by_id),
                    "journal_revision": journal.revision,
                }
            )
            # Deliberately copy just the question, with no answer/evidence/category.
            questions = [qa["question"] for qa in sample["qa"]]
            for i, question in enumerate(questions):
                offset = i % len(PROFILES)
                for profile in PROFILES[offset:] + PROFILES[:offset]:
                    timings, saved = [], None
                    for _ in range(repeats):
                        started = time.perf_counter()
                        result = memory.search(question, profile=profile)
                        timings.append((time.perf_counter() - started) * 1000)
                        if saved is not None and result != saved:
                            raise AssertionError("non-deterministic retrieval")
                        saved = result
                    started = time.perf_counter()
                    answer = memory.date_answer(question, saved["ids"])
                    reader_ms = (time.perf_counter() - started) * 1000
                    rows.append(
                        {
                            "question_id": question_id(sample["sample_id"], i),
                            "conversation": sample["sample_id"],
                            "question": question,
                            **saved,
                            "date_answer": answer,
                            "search_ms": timings,
                            "reader_ms": reader_ms,
                        }
                    )
        finally:
            journal.close()
    return rows, inventories


def score_frozen(data: list[dict], frozen: list[dict], inventories: list[dict]) -> dict:
    """Scoring runs only after the full retrieval artifact has been persisted."""
    labels = {
        question_id(s["sample_id"], i): qa for s in data for i, qa in enumerate(s["qa"])
    }
    known_ids = {s["conversation"]: set(s["ids"]) for s in inventories}
    audit, scored = [], []
    for sample in data:
        for i, qa in enumerate(sample["qa"]):
            original = qa.get("evidence", [])
            gold = normalized_ids(original)
            raw = {
                item for entry in original for item in re.findall(r"D\d+:\d+", entry)
            }
            known = known_ids[sample["sample_id"]]
            missing = sorted(set(gold) - known)
            if not gold or missing or raw != set(gold):
                audit.append(
                    {
                        "question_id": question_id(sample["sample_id"], i),
                        "category": qa["category"],
                        "raw_evidence": original,
                        "evidence_ids": gold,
                        "missing_ids": missing,
                        "raw_missing_ids": sorted(raw - known),
                        "empty": not gold,
                    }
                )
    seen = set()
    for row in frozen:
        qa = labels[row["question_id"]]
        key = (row["question_id"], row["profile"])
        if key in seen or row["profile"] not in PROFILES:
            raise ValueError("duplicate or invalid frozen profile")
        seen.add(key)
        if row["question"] != qa["question"]:
            raise ValueError("question changed after retrieval")
        if len(row["ids"]) > 5 or len(set(row["ids"])) != len(row["ids"]):
            raise ValueError("invalid frozen top-5")
        if not set(row["ids"]) <= known_ids[row["conversation"]]:
            raise ValueError("unknown retrieved ID")
        gold = normalized_ids(qa.get("evidence", []))
        exact = (
            exact_gold_date(qa.get("answer"))
            if re.match(r"^when\b", row["question"], re.I)
            else None
        )
        adversarial = qa["category"] == 5
        scored.append(
            {
                **row,
                "category": qa["category"],
                "evidence_ids": gold,
                "gold_answer": qa.get("answer"),
                "exact_gold_date": exact,
                "metrics": None
                if adversarial or not gold
                else evidence_metrics(row["ids"], gold),
                "lure_hit_at_5": int(bool(set(row["ids"]) & set(gold)))
                if adversarial and gold
                else None,
                "date_correct": row["date_answer"]["answer"] == exact
                if exact
                else None,
            }
        )
    if seen != {(qid, p) for qid in labels for p in PROFILES}:
        raise ValueError("incomplete frozen experiment")
    profiles = {}
    for profile in PROFILES:
        subset = [r for r in scored if r["profile"] == profile]
        dates = [r for r in subset if r["exact_gold_date"]]
        answered = [r for r in dates if r["date_answer"]["answer"] is not None]
        lures = [r for r in subset if r["lure_hit_at_5"] is not None]
        profiles[profile] = {
            "evidence": aggregate(subset),
            "by_category": {
                name: aggregate([r for r in subset if r["category"] == cat])
                for cat, name in CATEGORIES.items()
                if cat != 5
            },
            "by_conversation": {
                s["sample_id"]: aggregate(
                    [r for r in subset if r["conversation"] == s["sample_id"]]
                )
                for s in data
            },
            "adversarial": {
                "n": len(lures),
                "lure_hit_at_5": statistics.mean(r["lure_hit_at_5"] for r in lures)
                if lures
                else None,
                "date_reader_answers": sum(
                    r["date_answer"]["answer"] is not None
                    for r in subset
                    if r["category"] == 5
                ),
            },
            "calendar_qa": {
                "n": len(dates),
                "answered": len(answered),
                "correct": sum(r["date_correct"] for r in dates),
                "coverage": len(answered) / len(dates) if dates else None,
                "accuracy": statistics.mean(r["date_correct"] for r in dates)
                if dates
                else None,
                "precision_answered": statistics.mean(
                    r["date_correct"] for r in answered
                )
                if answered
                else None,
            },
            "search_latency": latency_summary(
                [statistics.median(r["search_ms"]) for r in subset]
            ),
            "reader_latency": latency_summary([r["reader_ms"] for r in subset]),
        }
    baseline = {
        r["question_id"]: r for r in scored if r["profile"] == "bm25" and r["metrics"]
    }
    paired = {}
    for profile in PROFILES[1:]:
        changes = Counter()
        for row in scored:
            if row["profile"] == profile and row["question_id"] in baseline:
                before = baseline[row["question_id"]]["metrics"]["hit_at_5"]
                after = row["metrics"]["hit_at_5"]
                changes[
                    "win" if after > before else "loss" if after < before else "tie"
                ] += 1
        paired[profile] = dict(changes)
    return {
        "profiles": profiles,
        "paired_hit_at_5_vs_bm25": paired,
        "data_audit": audit,
        "inventories": inventories,
        "rows": scored,
    }


def run(dataset: Path, output: Path, repeats: int):
    data_hash = sha256(dataset)
    if data_hash != DATA_SHA256:
        raise ValueError("dataset hash differs from pinned official LoCoMo")
    if repeats < 1:
        raise ValueError("repeats must be positive")
    data = read_json(dataset)
    output.mkdir(parents=True, exist_ok=False)
    manifest = build_manifest(data, data_hash, repeats)
    write_json(output / "manifest.json", manifest)  # freeze before any scoring
    with tempfile.TemporaryDirectory(prefix="locomo-memory-") as folder:
        frozen, inventories = freeze_retrieval(data, repeats, Path(folder))
    write_json(output / "retrieval.json", {"rows": frozen, "inventories": inventories})
    report = score_frozen(data, frozen, inventories)
    report["manifest_sha256"] = sha256(output / "manifest.json")
    report["retrieval_sha256"] = sha256(output / "retrieval.json")
    report["ranking_digest"] = digest(
        [
            {k: v for k, v in row.items() if k not in {"search_ms", "reader_ms"}}
            for row in frozen
        ]
    )
    write_json(output / "results.json", report)
    print(
        json.dumps(
            {
                "profiles": report["profiles"],
                "paired": report["paired_hit_at_5_vs_bm25"],
                "audit_rows": len(report["data_audit"]),
                "output": str(output),
            },
            indent=2,
        )
    )


def verify(dataset: Path, output: Path):
    manifest = read_json(output / "manifest.json")
    saved = read_json(output / "results.json")
    if sha256(dataset) != manifest["dataset_sha256"]:
        raise ValueError("dataset changed")
    if sha256(output / "manifest.json") != saved["manifest_sha256"]:
        raise ValueError("manifest changed")
    if sha256(output / "retrieval.json") != saved["retrieval_sha256"]:
        raise ValueError("frozen retrieval changed")
    for name, expected in manifest["source_hashes"].items():
        if sha256(ROOT / name) != expected:
            raise ValueError(f"source changed: {name}")
    frozen = read_json(output / "retrieval.json")
    rescored = score_frozen(read_json(dataset), frozen["rows"], frozen["inventories"])
    for key, value in rescored.items():
        if value != saved[key]:
            raise ValueError(f"replay differs: {key}")
    print("Verified source/data hashes, frozen retrieval, all scores, and audit.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "external/locomo/locomo10.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify(args.dataset, args.output)
    else:
        run(args.dataset, args.output, args.repeats)


if __name__ == "__main__":
    main()

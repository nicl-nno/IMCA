"""Freeze model-free context retrieval, then score released LoCoMo annotations."""

from __future__ import annotations

import argparse
import platform
import statistics
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from locomo_memory_eval import (
    CATEGORIES,
    DATA_SHA256,
    ROOT,
    SOURCE_FILES,
    SOURCE_URL,
    aggregate,
    evidence_metrics,
    exact_gold_date,
    latency_summary,
    normalized_ids,
    question_id,
    read_json,
    sha256,
    write_json,
)

from conversation_context_memory import (
    POLICIES,
    PROFILES,
    VERSION,
    ContextConversationMemory,
)
from conversation_memory import ConversationMemory
from inspectable_memory import InspectableMemory

SOURCES = (
    *SOURCE_FILES,
    "python/conversation_context_memory.py",
    "experiments/locomo_context_eval.py",
)


def freeze(data: list[dict], repeats: int, work: Path) -> tuple[list[dict], list[dict]]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    rows, inventories = [], []
    for sample in data:
        journal = InspectableMemory(work / f"{sample['sample_id']}.sqlite")
        try:
            started = time.perf_counter()
            memory = ContextConversationMemory(
                ConversationMemory(sample["sample_id"], sample["conversation"], journal)
            )
            inventories.append(
                {
                    "conversation": sample["sample_id"],
                    "ids": list(memory.positions),
                    "ingestion_ms": (time.perf_counter() - started) * 1000,
                }
            )
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
                    rows.append(
                        {
                            "question_id": question_id(sample["sample_id"], i),
                            "conversation": sample["sample_id"],
                            "question": question,
                            **saved,
                            "search_ms": timings,
                            "date_answer": memory.memory.date_answer(
                                question, saved["ids"]
                            ),
                        }
                    )
        finally:
            journal.close()
    return rows, inventories


def score(data: list[dict], frozen: dict) -> dict:
    labels = {
        question_id(s["sample_id"], i): qa for s in data for i, qa in enumerate(s["qa"])
    }
    inventories = {
        item["conversation"]: set(item["ids"]) for item in frozen["inventories"]
    }
    seen, rows = set(), []
    for row in frozen["rows"]:
        key = (row["question_id"], row["profile"])
        if key in seen or row["profile"] not in PROFILES:
            raise ValueError("duplicate or invalid profile")
        seen.add(key)
        qa = labels[row["question_id"]]
        if row["question"] != qa["question"] or not row["question_id"].startswith(
            row["conversation"] + "/qa/"
        ):
            raise ValueError("question or conversation changed")
        if (
            len(row["ids"]) > 5
            or len(set(row["ids"])) != len(row["ids"])
            or not set(row["ids"]) <= inventories[row["conversation"]]
        ):
            raise ValueError("invalid top-5")
        gold = normalized_ids(qa.get("evidence", []))
        adversarial = qa["category"] == 5
        date_gold = (
            exact_gold_date(qa.get("answer"))
            if not adversarial and row["question"].lower().startswith("when ")
            else None
        )
        rows.append(
            {
                "question_id": row["question_id"],
                "profile": row["profile"],
                "conversation": row["conversation"],
                "category": qa["category"],
                "evidence_ids": gold,
                "metrics": evidence_metrics(row["ids"], gold)
                if gold and not adversarial
                else None,
                "lure": int(bool(set(gold) & set(row["ids"])))
                if gold and adversarial
                else None,
                "ids": row["ids"],
                "search_ms": statistics.median(row["search_ms"]),
                "date_gold": date_gold,
                "date_answer": row["date_answer"],
            }
        )
    if seen != {(qid, profile) for qid in labels for profile in PROFILES}:
        raise ValueError("incomplete experiment")
    profiles = {}
    for profile in PROFILES:
        subset = [r for r in rows if r["profile"] == profile]
        lures = [r["lure"] for r in subset if r["lure"] is not None]
        dates = [r for r in subset if r["date_gold"]]
        profiles[profile] = {
            "evidence": aggregate(subset),
            "by_category": {
                name: aggregate([r for r in subset if r["category"] == cat])
                for cat, name in CATEGORIES.items()
                if cat != 5
            },
            "lure_at_5": statistics.mean(lures) if lures else None,
            "lure_n": len(lures),
            "search_latency": latency_summary([r["search_ms"] for r in subset]),
            "calendar_qa": {
                "n": len(dates),
                "answered": sum(r["date_answer"]["answer"] is not None for r in dates),
                "correct": sum(
                    r["date_answer"]["answer"] == r["date_gold"] for r in dates
                ),
            },
        }
    paired = {}
    for reference in ("bm25", "guarded"):
        before = {
            r["question_id"]: r
            for r in rows
            if r["profile"] == reference and r["metrics"] is not None
        }
        paired[reference] = {}
        for profile in PROFILES:
            subset = [
                r
                for r in rows
                if r["profile"] == profile and r["question_id"] in before
            ]
            changes = {}
            for metric in ("hit_at_5", "recall_at_5", "mrr_at_5", "full_evidence_at_5"):
                cases = {"win": [], "loss": [], "tie": []}
                for row in subset:
                    delta = (
                        row["metrics"][metric]
                        - before[row["question_id"]]["metrics"][metric]
                    )
                    cases[
                        "win" if delta > 0 else "loss" if delta < 0 else "tie"
                    ].append(row["question_id"])
                changes[metric] = {
                    "counts": {k: len(v) for k, v in cases.items()},
                    "win_ids": cases["win"],
                    "loss_ids": cases["loss"],
                }
            paired[reference][profile] = changes
    return {"profiles": profiles, "paired": paired, "rows": rows}


def verify(dataset: Path, output: Path):
    manifest, saved = (
        read_json(output / "manifest.json"),
        read_json(output / "results.json"),
    )
    if sha256(dataset) != manifest["dataset_sha256"]:
        raise ValueError("dataset changed")
    for name, expected in manifest["source_hashes"].items():
        if sha256(ROOT / name) != expected:
            raise ValueError(f"source changed: {name}")
    for filename in ("manifest.json", "retrieval.json"):
        if sha256(output / filename) != saved[filename + "_sha256"]:
            raise ValueError(f"artifact changed: {filename}")
    replay = score(read_json(dataset), read_json(output / "retrieval.json"))
    if any(saved[key] != value for key, value in replay.items()):
        raise ValueError("scoring replay changed")
    print("Verified source hashes, frozen top-5, and all scores.")


def run(dataset: Path, output: Path, repeats: int):
    if sha256(dataset) != DATA_SHA256 or repeats < 1:
        raise ValueError("requires pinned official data and positive repeats")
    data = read_json(dataset)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "version": VERSION,
        "dataset_url": SOURCE_URL,
        "dataset_sha256": sha256(dataset),
        "source_hashes": {name: sha256(ROOT / name) for name in SOURCES},
        "question_order": [
            question_id(s["sample_id"], i) for s in data for i in range(len(s["qa"]))
        ],
        "profiles": list(PROFILES),
        "policies": {name: asdict(policy) for name, policy in POLICIES.items()},
        "top_k": 5,
        "model": None,
        "llm_calls": 0,
        "embedding_calls": 0,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repeats": repeats,
        "timing": "median of repeated in-process searches, rotated profile order; no search result cache; shared indexes built once per conversation",
        "selection_note": "exploratory development on previously inspected conversations; no held-out claim",
        "context_contract": "only same-session neighboring raw turns; individual IDs count toward top-5; context is not inferred subject or evidence",
    }
    write_json(output / "manifest.json", manifest)
    with tempfile.TemporaryDirectory(prefix="locomo-context-") as work:
        rows, inventories = freeze(data, repeats, Path(work))
    frozen = {"rows": rows, "inventories": inventories}
    write_json(output / "retrieval.json", frozen)
    report = score(data, frozen)
    report.update(
        {
            filename + "_sha256": sha256(output / filename)
            for filename in ("manifest.json", "retrieval.json")
        }
    )
    write_json(output / "results.json", report)
    for name, result in report["profiles"].items():
        print(
            name,
            {
                "hit": result["evidence"]["hit_at_5"],
                "recall": result["evidence"]["recall_at_5"],
                "lure": result["lure_at_5"],
                "vs_bm25": report["paired"]["bm25"][name]["hit_at_5"]["counts"],
                "vs_guarded": report["paired"]["guarded"][name]["hit_at_5"]["counts"],
            },
            flush=True,
        )


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

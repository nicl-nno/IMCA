"""Post-hoc diagnostics of frozen LoCoMo runs; never used by ranking."""

from __future__ import annotations

import argparse
import random
import statistics
from pathlib import Path

from locomo_memory_eval import aggregate, read_json, sha256, verify, write_json
from temporal_language import extract_times

EXAMPLES = (
    "conv-30/qa/047",
    "conv-49/qa/068",
    "conv-50/qa/043",
    "conv-47/qa/014",
    "conv-30/qa/099",
    "conv-26/qa/003",
    "conv-26/qa/040",
    "conv-26/qa/025",
    "conv-48/qa/051",
    "conv-26/qa/107",
    "conv-47/qa/038",
)


def clustered_interval(rows: list[dict], before: str, after: str, metric: str) -> dict:
    paired = {}
    for row in rows:
        if row["metrics"] is not None:
            paired.setdefault(row["question_id"], {})[row["profile"]] = row
    groups = {}
    for variants in paired.values():
        a, b = variants[before], variants[after]
        groups.setdefault(a["conversation"], []).append(
            b["metrics"][metric] - a["metrics"][metric]
        )
    names = sorted(groups)
    rng = random.Random(42)
    samples = []
    for _ in range(10000):
        chosen = rng.choices(names, k=len(names))
        values = [delta for name in chosen for delta in groups[name]]
        samples.append(statistics.mean(values))
    samples.sort()
    return {
        "before": before,
        "after": after,
        "metric": metric,
        "delta": statistics.mean(delta for group in groups.values() for delta in group),
        "percentile_95_interval": [samples[249], samples[9749]],
        "unit": "whole conversation",
        "clusters": len(groups),
        "samples": 10000,
        "seed": 42,
        "interpretation": "exploratory; ten clusters, not a held-out significance claim",
    }


def audit(dataset: Path, output: Path) -> dict:
    verify(dataset, output)
    data = read_json(dataset)
    report = read_json(output / "results.json")
    utterances = {
        s["sample_id"]: {
            turn["dia_id"]: {
                "speaker": turn["speaker"],
                "text": turn["text"],
                "session_time": s["conversation"][key + "_date_time"],
            }
            for key, turns in s["conversation"].items()
            if key.startswith("session_") and not key.endswith("_date_time")
            for turn in turns
        }
        for s in data
    }
    indexed = {}
    for row in report["rows"]:
        indexed.setdefault(row["question_id"], {})[row["profile"]] = row
    examples = []
    for qid in EXAMPLES:
        variants = indexed[qid]
        first = variants["bm25"]
        sources = set(first["evidence_ids"])
        sources.update(r["date_answer"].get("source") for r in variants.values())
        examples.append(
            {
                "question_id": qid,
                "question": first["question"],
                "gold_answer": first["gold_answer"],
                "category": first["category"],
                "evidence_ids": first["evidence_ids"],
                "variants": {
                    p: {
                        "ids": r["ids"],
                        "date_answer": r["date_answer"],
                        "metrics": r["metrics"],
                    }
                    for p, r in variants.items()
                },
                "sources": {
                    s: utterances[first["conversation"]].get(s)
                    for s in sorted(sources - {None})
                },
            }
        )
    explicit_date = [r for r in report["rows"] if extract_times(r["question"], None)]
    return {
        "results_sha256": sha256(output / "results.json"),
        "audit_source_sha256": sha256(Path(__file__)),
        "role": "post-hoc analysis, no feedback to retriever",
        "clustered_intervals": [
            clustered_interval(report["rows"], "bm25", after, metric)
            for after in ("combined", "guarded")
            for metric in ("hit_at_5", "recall_at_5", "mrr_at_5")
        ],
        "explicit_calendar_in_question_posthoc": {
            p: aggregate([r for r in explicit_date if r["profile"] == p])
            for p in report["profiles"]
        },
        "examples": examples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("external/locomo/locomo10.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.dataset, args.output)
    write_json(args.output / "audit.json", result)
    for item in result["clustered_intervals"]:
        print(item)
    print(result["explicit_calendar_in_question_posthoc"])


if __name__ == "__main__":
    main()

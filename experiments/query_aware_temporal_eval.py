"""Experimental query-aware temporal retrieval for HaluMem.

State-at-time questions use strict temporal filtering.
Transition/retrospective questions keep four temporal results and allow
one contrastive candidate from outside the interpreted time slice.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from additional_benchmark_eval import (
    BM25,
    MemoryPoint,
    evidence_metrics,
    memory_time,
    normalize,
    question_time,
)


TRANSITION_MARKERS = (
    "before ",
    "after ",
    "increase",
    "decrease",
    "changed",
    "shift",
    "transition",
    "still",
    "begin",
    "started",
    "decide",
    "decided",
)


def query_group(question: str) -> str:
    lowered = question.lower()
    if any(marker in lowered for marker in TRANSITION_MARKERS):
        return "transition_or_retrospective"
    return "state_at_time"


def query_aware_top5(
    question: str,
    search: BM25,
    active: set[int],
) -> list[int]:
    """Strict temporal retrieval, except one contrast slot for transition queries."""

    temporal = search.top(question, 5, active)

    if query_group(question) == "state_at_time":
        return temporal

    temporal4 = temporal[:4]

    flat = search.top(question, 20)

    contrast = next(
        (
            document_id
            for document_id in flat
            if document_id not in active and document_id not in temporal4
        ),
        None,
    )

    if contrast is None:
        return temporal

    return temporal4 + [contrast]


def main() -> None:
    path = ROOT / "outputs/benchmarks/halumem-medium.jsonl"

    if not path.exists():
        raise FileNotFoundError(
            "Run experiments/download_additional_benchmarks.py first."
        )

    rows = []

    with path.open(encoding="utf-8") as stream:
        for line in stream:
            user = json.loads(line)

            points: list[MemoryPoint] = []
            by_text: dict[str, list[int]] = defaultdict(list)

            for session_index, session in enumerate(user["sessions"]):

                for memory in session.get("memory_points", []):
                    for original in memory.get("original_memories", []):
                        candidates = by_text.get(normalize(original), [])

                        if candidates:
                            update_time = memory_time(memory["timestamp"])

                            old_id = next(
                                (
                                    item
                                    for item in reversed(candidates)
                                    if points[item].valid_to is None
                                ),
                                None,
                            )

                            if old_id is not None:
                                points[old_id].valid_to = update_time

                    point_id = len(points)

                    points.append(
                        MemoryPoint(
                            memory["memory_content"],
                            memory_time(memory["timestamp"]),
                        )
                    )

                    by_text[normalize(memory["memory_content"])].append(point_id)

                if not session.get("questions"):
                    continue

                search = BM25([point.text for point in points])

                for question_index, question in enumerate(session["questions"]):

                    evidence = {
                        normalize(item["memory_content"])
                        for item in question["evidence"]
                    }

                    if not evidence:
                        continue

                    target_time = question_time(
                        question["question"],
                        session["end_time"],
                    )

                    active = {
                        index
                        for index, point in enumerate(points)
                        if point.active_at(target_time)
                    }

                    flat = search.top(question["question"], 5)
                    temporal = search.top(question["question"], 5, active)

                    query_aware = query_aware_top5(
                        question["question"],
                        search,
                        active,
                    )

                    flat_hit, flat_recall, flat_stale = evidence_metrics(
                        flat, points, evidence, target_time
                    )

                    temporal_hit, temporal_recall, temporal_stale = evidence_metrics(
                        temporal, points, evidence, target_time
                    )

                    qa_hit, qa_recall, qa_stale = evidence_metrics(
                        query_aware, points, evidence, target_time
                    )

                    rows.append(
                        {
                            "type": question["question_type"],
                            "query_group": query_group(question["question"]),
                            "flat_hit": flat_hit,
                            "temporal_hit": temporal_hit,
                            "qa_hit": qa_hit,
                            "flat_recall": flat_recall,
                            "temporal_recall": temporal_recall,
                            "qa_recall": qa_recall,
                            "flat_stale": flat_stale,
                            "temporal_stale": temporal_stale,
                            "qa_stale": qa_stale,
                        }
                    )

    def summarize(group):
        n = len(group)
        return {
            "n": n,
            "flat_hit5": sum(r["flat_hit"] for r in group) / n,
            "temporal_hit5": sum(r["temporal_hit"] for r in group) / n,
            "query_aware_hit5": sum(r["qa_hit"] for r in group) / n,
            "flat_recall5": sum(r["flat_recall"] for r in group) / n,
            "temporal_recall5": sum(r["temporal_recall"] for r in group) / n,
            "query_aware_recall5": sum(r["qa_recall"] for r in group) / n,
            "flat_stale_slots": sum(r["flat_stale"] for r in group),
            "temporal_stale_slots": sum(r["temporal_stale"] for r in group),
            "query_aware_stale_slots": sum(r["qa_stale"] for r in group),
            "query_aware_vs_temporal_wins": sum(
                r["qa_hit"] and not r["temporal_hit"] for r in group
            ),
            "query_aware_vs_temporal_losses": sum(
                r["temporal_hit"] and not r["qa_hit"] for r in group
            ),
        }

    evidence_rows = rows

    report = {
        "overall": summarize(evidence_rows),
        "memory_conflict": summarize(
            [r for r in evidence_rows if r["type"] == "Memory Conflict"]
        ),
        "transition_or_retrospective": summarize(
            [
                r
                for r in evidence_rows
                if r["query_group"] == "transition_or_retrospective"
            ]
        ),
        "state_at_time": summarize(
            [r for r in evidence_rows if r["query_group"] == "state_at_time"]
        ),
        "query_groups": dict(Counter(r["query_group"] for r in evidence_rows)),
    }

    output = ROOT / "outputs/query-aware-temporal.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()

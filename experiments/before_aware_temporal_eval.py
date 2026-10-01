"""Direction-aware temporal retrieval for HaluMem.

Strict temporal retrieval is preserved by default.

For explicit "before" / "after" questions, one out-of-slice candidate may
replace the fifth temporal result only when:

1. its temporal direction is compatible with the question;
2. it ranks above the fifth temporal result in global BM25 ranking.

This is intentionally conservative: the goal is to recover useful
contrastive evidence without broadly relaxing temporal validity.
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


def query_direction(question: str) -> str:
    lowered = question.lower()

    if "before " in lowered:
        return "before"

    # "after" questions remain under strict temporal filtering.
    # The previous experiment showed no retrieval benefit from
    # relaxing the temporal boundary for this direction.
    return "strict"


def direction_compatible(
    point: MemoryPoint,
    target_time: float,
    direction: str,
) -> bool:
    """Check whether an out-of-slice fact has the useful temporal direction."""

    if direction == "before":
        # Later evidence can establish that something had not yet happened
        # before the queried date.
        return point.valid_from > target_time

    if direction == "after":
        # Earlier evidence can establish that something happened before,
        # rather than after, the queried date.
        return point.valid_from < target_time

    return False


def direction_aware_top5(
    question: str,
    search: BM25,
    points: list[MemoryPoint],
    active: set[int],
    target_time: float,
) -> list[int]:

    temporal = search.top(question, 5, active)
    direction = query_direction(question)

    if direction == "strict":
        return temporal

    # Wider global ranking is used only to find a contrastive candidate.
    flat_pool = search.top(question, 50)
    rank = {
        document_id: position
        for position, document_id in enumerate(flat_pool)
    }

    candidate = next(
        (
            document_id
            for document_id in flat_pool
            if document_id not in active
            and direction_compatible(
                points[document_id],
                target_time,
                direction,
            )
        ),
        None,
    )

    if candidate is None:
        return temporal

    # If strict temporal retrieval contains fewer than five items,
    # adding the contrastive candidate does not displace valid evidence.
    if len(temporal) < 5:
        return (temporal + [candidate])[:5]

    fifth_temporal = temporal[4]

    candidate_rank = rank.get(candidate, 10**9)
    fifth_rank = rank.get(fifth_temporal, 10**9)

    # Replace only when BM25 itself ranks the external candidate higher.
    if candidate_rank < fifth_rank:
        return temporal[:4] + [candidate]

    return temporal


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

            for session in user["sessions"]:

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

                    by_text[
                        normalize(memory["memory_content"])
                    ].append(point_id)

                if not session.get("questions"):
                    continue

                search = BM25([point.text for point in points])

                for question in session["questions"]:

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

                    flat = search.top(
                        question["question"],
                        5,
                    )

                    temporal = search.top(
                        question["question"],
                        5,
                        active,
                    )

                    direction_aware = direction_aware_top5(
                        question["question"],
                        search,
                        points,
                        active,
                        target_time,
                    )

                    flat_hit, flat_recall, flat_stale = evidence_metrics(
                        flat,
                        points,
                        evidence,
                        target_time,
                    )

                    temporal_hit, temporal_recall, temporal_stale = evidence_metrics(
                        temporal,
                        points,
                        evidence,
                        target_time,
                    )

                    direction_hit, direction_recall, direction_stale = evidence_metrics(
                        direction_aware,
                        points,
                        evidence,
                        target_time,
                    )

                    rows.append(
                        {
                            "type": question["question_type"],
                            "direction": query_direction(
                                question["question"]
                            ),
                            "flat_hit": flat_hit,
                            "temporal_hit": temporal_hit,
                            "direction_hit": direction_hit,
                            "flat_recall": flat_recall,
                            "temporal_recall": temporal_recall,
                            "direction_recall": direction_recall,
                            "flat_stale": flat_stale,
                            "temporal_stale": temporal_stale,
                            "direction_stale": direction_stale,
                        }
                    )

    def summarize(group):
        n = len(group)

        if n == 0:
            return {
                "n": 0,
            }

        return {
            "n": n,

            "flat_hit5":
                sum(r["flat_hit"] for r in group) / n,

            "temporal_hit5":
                sum(r["temporal_hit"] for r in group) / n,

            "direction_aware_hit5":
                sum(r["direction_hit"] for r in group) / n,

            "flat_recall5":
                sum(r["flat_recall"] for r in group) / n,

            "temporal_recall5":
                sum(r["temporal_recall"] for r in group) / n,

            "direction_aware_recall5":
                sum(r["direction_recall"] for r in group) / n,

            "flat_stale_slots":
                sum(r["flat_stale"] for r in group),

            "temporal_stale_slots":
                sum(r["temporal_stale"] for r in group),

            "direction_aware_stale_slots":
                sum(r["direction_stale"] for r in group),

            "direction_vs_temporal_wins":
                sum(
                    r["direction_hit"]
                    and not r["temporal_hit"]
                    for r in group
                ),

            "direction_vs_temporal_losses":
                sum(
                    r["temporal_hit"]
                    and not r["direction_hit"]
                    for r in group
                ),
        }

    report = {
        "overall": summarize(rows),

        "memory_conflict": summarize(
            [
                r for r in rows
                if r["type"] == "Memory Conflict"
            ]
        ),

        "before_questions": summarize(
            [
                r for r in rows
                if r["direction"] == "before"
            ]
        ),

        "after_questions": summarize(
            [
                r for r in rows
                if r["direction"] == "after"
            ]
        ),

        "strict_questions": summarize(
            [
                r for r in rows
                if r["direction"] == "strict"
            ]
        ),

        "query_directions": dict(
            Counter(r["direction"] for r in rows)
        ),
    }

    output = ROOT / "outputs/before-aware-temporal.json"

    output.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()

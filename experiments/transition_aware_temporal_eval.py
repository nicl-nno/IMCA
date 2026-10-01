"""Transition-aware temporal retrieval for HaluMem.

Strict temporal retrieval is preserved by default.
For transition/retrospective questions, one additional candidate is allowed
only when it participates in an explicit update/replacement relation.
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


def transition_aware_top5(
    question: str,
    search: BM25,
    active: set[int],
    update_neighbors: dict[int, set[int]],
) -> list[int]:

    temporal = search.top(question, 5, active)

    if query_group(question) == "state_at_time":
        return temporal

    # Keep four strict temporal results.
    base = temporal[:4]

    # Candidates outside the current temporal slice.
    flat = search.top(question, 50)

    # Only allow a candidate if it is explicitly connected
    # to a fact through an update/replacement relation.
    linked_candidates = []

    for document_id in flat:
        if document_id in active:
            continue

        neighbors = update_neighbors.get(document_id, set())

        # Prefer candidates whose old/new partner is active now.
        if neighbors & active:
            linked_candidates.append(document_id)

    if not linked_candidates:
        return temporal

    return base + [linked_candidates[0]]


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

            # Bidirectional relation old <-> new.
            update_neighbors: dict[int, set[int]] = defaultdict(set)

            for session_index, session in enumerate(user["sessions"]):

                for memory in session.get("memory_points", []):

                    linked_old_ids = []

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
                                linked_old_ids.append(old_id)

                    new_id = len(points)

                    points.append(
                        MemoryPoint(
                            memory["memory_content"],
                            memory_time(memory["timestamp"]),
                        )
                    )

                    by_text[
                        normalize(memory["memory_content"])
                    ].append(new_id)

                    for old_id in linked_old_ids:
                        update_neighbors[old_id].add(new_id)
                        update_neighbors[new_id].add(old_id)

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

                    transition = transition_aware_top5(
                        question["question"],
                        search,
                        active,
                        update_neighbors,
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

                    transition_hit, transition_recall, transition_stale = evidence_metrics(
                        transition,
                        points,
                        evidence,
                        target_time,
                    )

                    rows.append(
                        {
                            "type": question["question_type"],
                            "query_group": query_group(question["question"]),
                            "flat_hit": flat_hit,
                            "temporal_hit": temporal_hit,
                            "transition_hit": transition_hit,
                            "flat_recall": flat_recall,
                            "temporal_recall": temporal_recall,
                            "transition_recall": transition_recall,
                            "flat_stale": flat_stale,
                            "temporal_stale": temporal_stale,
                            "transition_stale": transition_stale,
                        }
                    )

    def summarize(group):
        n = len(group)

        return {
            "n": n,
            "flat_hit5": sum(r["flat_hit"] for r in group) / n,
            "temporal_hit5": sum(r["temporal_hit"] for r in group) / n,
            "transition_hit5": sum(r["transition_hit"] for r in group) / n,

            "flat_recall5": sum(r["flat_recall"] for r in group) / n,
            "temporal_recall5": sum(r["temporal_recall"] for r in group) / n,
            "transition_recall5": sum(r["transition_recall"] for r in group) / n,

            "flat_stale_slots": sum(r["flat_stale"] for r in group),
            "temporal_stale_slots": sum(r["temporal_stale"] for r in group),
            "transition_stale_slots": sum(r["transition_stale"] for r in group),

            "transition_vs_temporal_wins": sum(
                r["transition_hit"] and not r["temporal_hit"]
                for r in group
            ),

            "transition_vs_temporal_losses": sum(
                r["temporal_hit"] and not r["transition_hit"]
                for r in group
            ),
        }

    report = {
        "overall": summarize(rows),

        "memory_conflict": summarize(
            [r for r in rows if r["type"] == "Memory Conflict"]
        ),

        "transition_or_retrospective": summarize(
            [
                r for r in rows
                if r["query_group"] == "transition_or_retrospective"
            ]
        ),

        "state_at_time": summarize(
            [
                r for r in rows
                if r["query_group"] == "state_at_time"
            ]
        ),

        "query_groups": dict(
            Counter(r["query_group"] for r in rows)
        ),
    }

    output = ROOT / "outputs/transition-aware-temporal.json"

    output.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()

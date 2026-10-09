"""Export HaluMem consistency cases with retrieval outputs for AutoJudge."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from additional_benchmark_eval import (
    BM25,
    MemoryPoint,
    memory_time,
    normalize,
    question_time,
)

from query_aware_temporal_eval import query_aware_top5
from transition_aware_temporal_eval import transition_aware_top5

# before_aware_temporal_eval was derived from the direction-aware experiment.
# The function name remains direction_aware_top5, but in this version the
# policy relaxes filtering only for explicit "before" questions.
from before_aware_temporal_eval import (
    direction_aware_top5 as before_aware_top5,
)


CASES_INPUT = ROOT / "results/consistency_error_cases.csv"
BENCHMARK_INPUT = ROOT / "outputs/benchmarks/halumem-medium.jsonl"
OUTPUT = ROOT / "results/autojudge_consistency_cases.jsonl"


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
    }


def get_user_id(user: dict) -> str:
    """Handle possible HaluMem user-id field variants."""

    for key in (
        "user_id",
        "user",
        "id",
        "uuid",
    ):
        value = user.get(key)
        if value is not None:
            return str(value)

    raise KeyError(
        f"Could not determine user id. Available keys: {list(user.keys())}"
    )


def serialize_point(
    point_id: int,
    points: list[MemoryPoint],
    target_time: float,
    rank: int,
) -> dict:

    point = points[point_id]

    return {
        "rank": rank,
        "memory_id": point_id,
        "text": point.text,
        "valid_from": point.valid_from,
        "valid_to": point.valid_to,
        "active_at_question_time": point.active_at(target_time),
    }


def serialize_ranking(
    ranking: list[int],
    points: list[MemoryPoint],
    target_time: float,
) -> list[dict]:

    return [
        serialize_point(
            point_id=document_id,
            points=points,
            target_time=target_time,
            rank=rank,
        )
        for rank, document_id in enumerate(ranking, start=1)
    ]


def load_target_cases() -> dict[tuple[str, int, int], dict]:

    targets = {}

    with CASES_INPUT.open(
        encoding="utf-8",
        newline="",
    ) as stream:

        reader = csv.DictReader(stream)

        for index, row in enumerate(reader, start=1):

            key = (
                str(row["user"]),
                int(row["session"]),
                int(row["question_index"]),
            )

            targets[key] = {
                "case_id": f"halumem-memory-conflict-{index:03d}",
                "csv": row,
            }

    return targets


def main() -> None:

    if not CASES_INPUT.exists():
        raise FileNotFoundError(CASES_INPUT)

    if not BENCHMARK_INPUT.exists():
        raise FileNotFoundError(BENCHMARK_INPUT)

    targets = load_target_cases()
    exported: list[dict] = []

    with BENCHMARK_INPUT.open(encoding="utf-8") as stream:

        for line in stream:

            user = json.loads(line)
            user_id = get_user_id(user)

            # Skip users that do not contain any of the 27 target cases.
            if not any(key[0] == user_id for key in targets):
                continue

            points: list[MemoryPoint] = []
            by_text: dict[str, list[int]] = defaultdict(list)

            # Required by the explicit-update transition-aware policy.
            update_neighbors: dict[int, set[int]] = defaultdict(set)

            for session_index, session in enumerate(user["sessions"]):

                for memory in session.get("memory_points", []):

                    linked_old_ids = []

                    for original in memory.get("original_memories", []):

                        candidates = by_text.get(
                            normalize(original),
                            [],
                        )

                        if not candidates:
                            continue

                        update_time = memory_time(
                            memory["timestamp"]
                        )

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

                questions = session.get("questions", [])

                if not questions:
                    continue

                # This matches the evaluation setup used in the existing
                # HaluMem experiments: retrieval operates on memory available
                # up to the current session.
                search = BM25(
                    [point.text for point in points]
                )

                for question_index, question in enumerate(questions):

                    key = (
                        user_id,
                        session_index,
                        question_index,
                    )

                    if key not in targets:
                        continue

                    target = targets[key]
                    row = target["csv"]

                    question_text = question["question"]

                    target_time = question_time(
                        question_text,
                        session["end_time"],
                    )

                    active = {
                        index
                        for index, point in enumerate(points)
                        if point.active_at(target_time)
                    }

                    flat = search.top(
                        question_text,
                        5,
                    )

                    strict_temporal = search.top(
                        question_text,
                        5,
                        active,
                    )

                    query_aware = query_aware_top5(
                        question_text,
                        search,
                        active,
                    )

                    transition_aware = transition_aware_top5(
                        question_text,
                        search,
                        active,
                        update_neighbors,
                    )

                    before_aware = before_aware_top5(
                        question_text,
                        search,
                        points,
                        active,
                        target_time,
                    )

                    evidence = [
                        item["memory_content"]
                        for item in question.get("evidence", [])
                    ]

                    case = {
                        "case_id": target["case_id"],

                        "benchmark": "HaluMem-Medium",
                        "subset": "Memory Conflict",

                        "source": {
                            "user": user_id,
                            "session": session_index,
                            "question_index": question_index,
                        },

                        "question": question_text,
                        "question_time": target_time,

                        "reference_evidence": evidence,

                        "diagnostic_signals": {
                            "query_group": row.get("query_group"),

                            "evidence_after_question_time": parse_bool(
                                row.get(
                                    "evidence_after_question_time",
                                    ""
                                )
                            ),

                            "evidence_expired": parse_bool(
                                row.get(
                                    "evidence_expired",
                                    ""
                                )
                            ),

                            "zero_length_interval": parse_bool(
                                row.get(
                                    "zero_length_interval",
                                    ""
                                )
                            ),
                        },

                        "retrieval_outputs": {
                            "flat_bm25": serialize_ranking(
                                flat,
                                points,
                                target_time,
                            ),

                            "strict_temporal": serialize_ranking(
                                strict_temporal,
                                points,
                                target_time,
                            ),

                            "query_aware": serialize_ranking(
                                query_aware,
                                points,
                                target_time,
                            ),

                            "transition_aware": serialize_ranking(
                                transition_aware,
                                points,
                                target_time,
                            ),

                            "before_aware": serialize_ranking(
                                before_aware,
                                points,
                                target_time,
                            ),
                        },

                        "judge_task": {
                            "goal": (
                                "Evaluate whether the retrieved memory context "
                                "contains a true contradiction, a legitimate "
                                "temporal update, useful out-of-slice evidence, "
                                "harmful stale evidence, missing required "
                                "evidence, or insufficient information."
                            ),

                            "taxonomy": [
                                "consistent",
                                "true_conflict",
                                "temporal_update",
                                "stale_but_relevant",
                                "stale_and_harmful",
                                "missing_required_evidence",
                                "insufficient_information",
                            ],

                            "output_schema": {
                                "consistency_status": (
                                    "consistent | conflicting | underdetermined"
                                ),
                                "conflict_type": (
                                    "none | true_conflict | temporal_update"
                                ),
                                "out_of_slice_evidence": (
                                    "none | relevant | harmful"
                                ),
                                "missing_required_evidence": "boolean",
                                "supports_answer": "boolean",
                                "confidence": "float",
                                "reason": "string",
                            },
                        },
                    }

                    exported.append(case)

    exported.sort(
        key=lambda item: item["case_id"]
    )

    expected = len(targets)

    if len(exported) != expected:

        found_keys = {
            (
                case["source"]["user"],
                case["source"]["session"],
                case["source"]["question_index"],
            )
            for case in exported
        }

        missing = [
            key
            for key in targets
            if key not in found_keys
        ]

        raise RuntimeError(
            f"Expected {expected} cases, exported {len(exported)}. "
            f"Missing keys: {missing}"
        )

    with OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as stream:

        for case in exported:

            stream.write(
                json.dumps(
                    case,
                    ensure_ascii=False,
                )
                + "\n"
            )

    print(f"Target cases: {expected}")
    print(f"Exported cases: {len(exported)}")
    print(f"Retrieval policies per case: 5")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()

"""Build one judge trace per HaluMem case and retrieval policy."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "results/autojudge_consistency_cases.jsonl"
OUTPUT = ROOT / "results/autojudge_traces.jsonl"


TAXONOMY = [
    "consistent",
    "true_conflict",
    "temporal_update",
    "stale_but_relevant",
    "stale_and_harmful",
    "missing_required_evidence",
    "insufficient_information",
]


OUTPUT_SCHEMA = {
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
}


def build_history(
    case: dict,
    policy: str,
    items: list[dict],
) -> list[dict]:
    """Represent one retrieval output as an evaluation trace."""

    history = [
        {
            "step": "question",
            "content": case["question"],
            "question_time": case["question_time"],
        },
        {
            "step": "retrieval_policy",
            "content": policy,
        },
    ]

    for item in items:
        history.append(
            {
                "step": "retrieved_memory",
                "rank": item["rank"],
                "memory_id": item["memory_id"],
                "content": item["text"],
                "valid_from": item["valid_from"],
                "valid_to": item["valid_to"],
                "active_at_question_time": (
                    item["active_at_question_time"]
                ),
            }
        )

    return history


def main() -> None:

    if not INPUT.exists():
        raise FileNotFoundError(INPUT)

    traces = []

    with INPUT.open(encoding="utf-8") as stream:

        for line in stream:

            case = json.loads(line)

            for policy, items in case[
                "retrieval_outputs"
            ].items():

                trace = {
                    "trace_id": (
                        f'{case["case_id"]}__{policy}'
                    ),

                    "case_id": case["case_id"],

                    "benchmark": case["benchmark"],
                    "subset": case["subset"],

                    "retrieval_policy": policy,

                    "query": case["question"],

                    "history_for_evaluating": build_history(
                        case,
                        policy,
                        items,
                    ),

                    "reference_evidence": (
                        case["reference_evidence"]
                    ),

                    "diagnostic_signals": (
                        case["diagnostic_signals"]
                    ),

                    "evaluation": {
                        "goal": (
                            "Evaluate whether the retrieved "
                            "memory context is temporally and "
                            "semantically consistent and whether "
                            "it contains the evidence required "
                            "to answer the query."
                        ),

                        "taxonomy": TAXONOMY,

                        "output_schema": OUTPUT_SCHEMA,
                    },
                }

                traces.append(trace)

    traces.sort(
        key=lambda item: (
            item["case_id"],
            item["retrieval_policy"],
        )
    )

    with OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as stream:

        for trace in traces:

            stream.write(
                json.dumps(
                    trace,
                    ensure_ascii=False,
                )
                + "\n"
            )

    print(f"Source cases: {len(traces) // 5}")
    print(f"Retrieval policies: 5")
    print(f"Generated traces: {len(traces)}")
    print(f"Saved: {OUTPUT}")

    if len(traces) != 135:
        raise RuntimeError(
            f"Expected 135 traces, got {len(traces)}"
        )


if __name__ == "__main__":
    main()

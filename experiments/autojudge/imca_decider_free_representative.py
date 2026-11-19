import json
import os
import time
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


MODEL = "perplexity/pplx-decider-v1.3:free"
API_URL = "https://openrouter.ai/api/alpha/decisions"

TRACES_PATH = Path("results/autojudge_traces.jsonl")
JEV_PATH = Path("results/autojudge_representative_jev_v2.json")
OUT_PATH = Path(
    "results/autojudge_representative_decider_free.json"
)

API_KEY = os.environ.get("OPENROUTER_API_KEY")

if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is not set")


def load_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def timestamp_to_date(value):
    if value is None:
        return None

    return datetime.fromtimestamp(
        value,
        tz=timezone.utc,
    ).strftime("%Y-%m-%d")


def retrieved_memories(trace):
    rows = []

    for item in trace["history_for_evaluating"]:
        if item.get("step") != "retrieved_memory":
            continue

        rows.append({
            "rank": item.get("rank"),
            "memory_id": item.get("memory_id"),
            "content": item.get("content"),
            "valid_from_date": timestamp_to_date(
                item.get("valid_from")
            ),
            "valid_to_date": timestamp_to_date(
                item.get("valid_to")
            ),
            "active_at_question_time":
                item.get("active_at_question_time"),
        })

    return rows


def question_date(trace):
    question = next(
        item
        for item in trace["history_for_evaluating"]
        if item.get("step") == "question"
    )

    return timestamp_to_date(
        question.get("question_time")
    )


def build_consistency_state(trace):
    return {
        "task": (
            "Evaluate ONLY the retrieved memories below. "
            "Assess their temporal and semantic consistency "
            "and determine whether memories outside the "
            "strict temporal slice are useful or harmful "
            "for the query."
        ),

        "query": trace["query"],

        "question_date": question_date(trace),

        "retrieved_memories":
            retrieved_memories(trace),

        "rules": [
            (
                "Use the supplied calendar dates directly."
            ),
            (
                "active_at_question_time is authoritative "
                "for deciding whether a retrieved memory "
                "lies inside or outside the strict temporal "
                "slice."
            ),
            (
                "A memory outside the strict temporal slice "
                "is not automatically harmful. It may be "
                "useful for retrospective or transition "
                "reasoning."
            ),
            (
                "A legitimate change of state across "
                "different time periods is a temporal_update, "
                "not a true_conflict."
            ),
            (
                "A true_conflict requires incompatible claims "
                "about the same relevant state during "
                "overlapping relevant time."
            ),
            (
                "Judge only from the query, temporal metadata "
                "and retrieved memories. No benchmark "
                "reference evidence is available."
            ),
        ],
    }


def build_evidence_state(trace):
    return {
        "task": (
            "Evaluate whether benchmark reference evidence "
            "is represented in the retrieved memories and "
            "whether the correct answer can be inferred from "
            "retrieved memories."
        ),

        "query": trace["query"],

        "question_date": question_date(trace),

        "retrieved_memories":
            retrieved_memories(trace),

        "reference_evidence": trace.get(
            "reference_evidence",
            [],
        ),

        "rules": [
            (
                "Reference evidence is supplied only to "
                "identify what benchmark evidence is expected."
            ),
            (
                "Reference evidence MUST NOT be treated as if "
                "it had been retrieved by the memory system."
            ),
            (
                "For reference_evidence_present, compare "
                "semantic meaning rather than exact wording."
            ),
            (
                "For answer_inferable, use ONLY retrieved "
                "memories, their dates and temporal metadata "
                "as evidence."
            ),
            (
                "answer_inferable may be true even if exact "
                "benchmark reference evidence is absent, if "
                "the answer follows reliably from other "
                "retrieved facts."
            ),
            (
                "If multiple plausible answers remain, "
                "answer_inferable must be false."
            ),
        ],
    }


CONSISTENCY_QUESTIONS = {
    "consistency_status": {
        "type": "choice",
        "instructions": (
            "Classify the consistency of the retrieved "
            "memories with respect to the query and relevant "
            "time."
        ),
        "criteria": {
            "consistent": (
                "The memories can be interpreted coherently "
                "without an incompatible same-time claim."
            ),
            "conflicting": (
                "There are incompatible claims about the same "
                "state during overlapping relevant time."
            ),
            "underdetermined": (
                "There is not enough information to determine "
                "whether the memories are consistent or "
                "conflicting."
            ),
        },
    },

    "conflict_type": {
        "type": "choice",
        "instructions": (
            "Classify the relationship between differing "
            "claims."
        ),
        "criteria": {
            "none": (
                "There is no relevant disagreement."
            ),
            "true_conflict": (
                "There are incompatible claims about the same "
                "state for overlapping relevant time."
            ),
            "temporal_update": (
                "Different claims describe successive "
                "legitimate states at different times."
            ),
        },
    },

    "out_of_slice_evidence": {
        "type": "choice",
        "instructions": (
            "Evaluate ONLY retrieved memories where "
            "active_at_question_time=false. If there are "
            "none, choose none."
        ),
        "criteria": {
            "none": (
                "There are no retrieved out-of-slice "
                "memories."
            ),
            "relevant": (
                "At least one out-of-slice memory is useful "
                "or necessary for answering or interpreting "
                "the query."
            ),
            "harmful": (
                "At least one out-of-slice memory is "
                "misleading or introduces harmful stale "
                "information."
            ),
        },
    },
}


EVIDENCE_QUESTIONS = {
    "reference_evidence_present": {
        "type": "noul",
        "instructions": (
            "Does the retrieved context semantically contain "
            "the benchmark reference evidence needed for "
            "this query? Judge ONLY retrieved_memories. "
            "Do not count reference_evidence itself as "
            "retrieved."
        ),
    },

    "answer_inferable": {
        "type": "noul",
        "instructions": (
            "Can the correct answer to the query be reliably "
            "determined from retrieved_memories and their "
            "temporal metadata alone?"
        ),
    },
}


def call_decider(state, questions):
    payload = {
        "model": MODEL,
        "state": state,
        "questions": questions,
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization":
                f"Bearer {API_KEY}",
            "Content-Type":
                "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=120,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def bool_from_noul(answer, threshold=0.5):
    p = answer["noul"]
    return p >= threshold, p


# Use exactly the same 25 traces that were
# evaluated in the representative Jev experiment.
jev_results = json.loads(
    JEV_PATH.read_text(encoding="utf-8")
)

target_trace_ids = [
    row["trace_id"]
    for row in jev_results
]

if len(target_trace_ids) != 25:
    raise RuntimeError(
        f"Expected 25 representative traces, "
        f"got {len(target_trace_ids)}"
    )


all_traces = {
    row["trace_id"]: row
    for row in load_jsonl(TRACES_PATH)
}


existing = []

if OUT_PATH.exists():
    existing = json.loads(
        OUT_PATH.read_text(encoding="utf-8")
    )

completed = {
    row["trace_id"]
    for row in existing
}

results = list(existing)

print("Model:", MODEL)
print("Target traces:", len(target_trace_ids))
print("Already completed:", len(completed))


for i, trace_id in enumerate(
    target_trace_ids,
    start=1,
):
    if trace_id in completed:
        print(
            f"[{i}/{len(target_trace_ids)}] "
            f"SKIP {trace_id}"
        )
        continue

    trace = all_traces[trace_id]

    print(
        f"[{i}/{len(target_trace_ids)}] "
        f"{trace_id}",
        flush=True,
    )

    # Request 1:
    # blinded consistency evaluation.
    raw_consistency = call_decider(
        build_consistency_state(trace),
        CONSISTENCY_QUESTIONS,
    )

    time.sleep(3.2)

    # Request 2:
    # reference evidence / answer inference.
    raw_evidence = call_decider(
        build_evidence_state(trace),
        EVIDENCE_QUESTIONS,
    )

    consistency_answers = (
        raw_consistency["answers"]
    )

    evidence_answers = (
        raw_evidence["answers"]
    )

    evidence_present, evidence_p = (
        bool_from_noul(
            evidence_answers[
                "reference_evidence_present"
            ]
        )
    )

    answer_inferable, inferable_p = (
        bool_from_noul(
            evidence_answers[
                "answer_inferable"
            ]
        )
    )

    if evidence_present and answer_inferable:
        support_type = (
            "direct_or_reference_supported"
        )

    elif (
        not evidence_present
        and answer_inferable
    ):
        support_type = "indirect_inference"

    elif (
        evidence_present
        and not answer_inferable
    ):
        support_type = (
            "evidence_present_but_insufficient"
        )

    else:
        support_type = "insufficient_context"

    result = {
        "trace_id": trace["trace_id"],
        "case_id": trace["case_id"],
        "retrieval_policy":
            trace["retrieval_policy"],
        "query": trace["query"],

        "model": MODEL,

        "verdict": {
            "consistency_status":
                consistency_answers[
                    "consistency_status"
                ]["choice"],

            "conflict_type":
                consistency_answers[
                    "conflict_type"
                ]["choice"],

            "out_of_slice_evidence":
                consistency_answers[
                    "out_of_slice_evidence"
                ]["choice"],

            "reference_evidence_present":
                evidence_present,

            "answer_inferable":
                answer_inferable,

            "support_type":
                support_type,
        },

        "probabilities": {
            "consistency_status":
                consistency_answers[
                    "consistency_status"
                ].get("probabilities"),

            "conflict_type":
                consistency_answers[
                    "conflict_type"
                ].get("probabilities"),

            "out_of_slice_evidence":
                consistency_answers[
                    "out_of_slice_evidence"
                ].get("probabilities"),

            "reference_evidence_present_yes":
                evidence_p,

            "answer_inferable_yes":
                inferable_p,
        },

        "request_ids": {
            "consistency":
                raw_consistency.get("id"),
            "evidence":
                raw_evidence.get("id"),
        },
    }

    results.append(result)

    OUT_PATH.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Keep below the free 20 requests/minute cap.
    time.sleep(3.2)


print()
print("Saved:", OUT_PATH)
print(
    "Completed:",
    len(results),
    "/",
    len(target_trace_ids),
)


print("\nSUMMARY BY POLICY")

for policy in sorted({
    row["retrieval_policy"]
    for row in results
}):
    rows = [
        row
        for row in results
        if row["retrieval_policy"] == policy
    ]

    print()
    print(policy)
    print("  n:", len(rows))

    print(
        "  consistency:",
        dict(
            Counter(
                row["verdict"][
                    "consistency_status"
                ]
                for row in rows
            )
        ),
    )

    print(
        "  conflict_type:",
        dict(
            Counter(
                row["verdict"][
                    "conflict_type"
                ]
                for row in rows
            )
        ),
    )

    print(
        "  out_of_slice:",
        dict(
            Counter(
                row["verdict"][
                    "out_of_slice_evidence"
                ]
                for row in rows
            )
        ),
    )

    print(
        "  reference_evidence_present:",
        sum(
            row["verdict"][
                "reference_evidence_present"
            ]
            for row in rows
        ),
        "/",
        len(rows),
    )

    print(
        "  answer_inferable:",
        sum(
            row["verdict"][
                "answer_inferable"
            ]
            for row in rows
        ),
        "/",
        len(rows),
    )

import json
import os
import time
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


MODEL = "typesafe/jev-1.14"
API_URL = "https://openrouter.ai/api/alpha/decisions"

TRACES_PATH = Path("results/autojudge_traces.jsonl")
OUT_PATH = Path("results/autojudge_consistency_full_jev_v4.json")

API_KEY = os.environ.get("OPENROUTER_API_KEY")

if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is not set")


def load_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
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
    memories = []

    for item in trace["history_for_evaluating"]:
        if item.get("step") != "retrieved_memory":
            continue

        memories.append({
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

    return memories


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
            "Assess their temporal and semantic consistency and determine "
            "whether memories outside the strict temporal slice are useful "
            "or harmful for the query."
        ),

        "query": trace["query"],

        "question_date": question_date(trace),

        "retrieved_memories": retrieved_memories(trace),

        "rules": [
            (
                "Use the supplied calendar dates directly."
            ),
            (
                "active_at_question_time is authoritative for deciding "
                "whether a retrieved memory lies inside or outside the "
                "strict temporal slice."
            ),
            (
                "A memory outside the strict temporal slice is not "
                "automatically harmful. It may be useful for retrospective "
                "or transition reasoning."
            ),
            (
                "A legitimate change of state across different time "
                "periods is a temporal_update, not a true_conflict."
            ),
            (
                "A true_conflict requires incompatible claims about the "
                "same relevant state during overlapping relevant time."
            ),
            (
                "Judge only from the query, temporal metadata and retrieved "
                "memories supplied here. No benchmark reference answer or "
                "reference evidence is available for this evaluation."
            ),
        ],
    }


def build_evidence_state(trace):
    return {
        "task": (
            "Evaluate whether benchmark reference evidence is represented "
            "in the retrieved memories and whether the correct answer can "
            "be inferred from retrieved memories."
        ),

        "query": trace["query"],

        "question_date": question_date(trace),

        "retrieved_memories": retrieved_memories(trace),

        "reference_evidence": trace.get(
            "reference_evidence",
            [],
        ),

        "rules": [
            (
                "Reference evidence is supplied only to identify what "
                "benchmark evidence is expected."
            ),
            (
                "Reference evidence MUST NOT be treated as if it had been "
                "retrieved by the memory system."
            ),
            (
                "For reference_evidence_present, compare semantic meaning "
                "rather than exact wording."
            ),
            (
                "For answer_inferable, use ONLY retrieved memories, their "
                "dates and temporal metadata as evidence."
            ),
            (
                "answer_inferable may be true even if benchmark reference "
                "evidence is absent, if the answer follows reliably from "
                "other retrieved facts."
            ),
            (
                "If multiple plausible answers remain, answer_inferable "
                "must be false."
            ),
        ],
    }


CONSISTENCY_QUESTIONS = {
    "consistency_status": {
        "type": "choice",
        "instructions": (
            "Classify the consistency of the retrieved memories with "
            "respect to the query and relevant time."
        ),
        "criteria": {
            "consistent": (
                "The memories can be interpreted coherently without an "
                "incompatible same-time claim."
            ),
            "conflicting": (
                "There are incompatible claims about the same state "
                "during overlapping relevant time."
            ),
            "underdetermined": (
                "There is not enough information to determine whether "
                "the memories are consistent or conflicting."
            ),
        },
    },

    "conflict_type": {
        "type": "choice",
        "instructions": (
            "Classify the relationship between differing claims."
        ),
        "criteria": {
            "none": (
                "There is no relevant disagreement."
            ),
            "true_conflict": (
                "There are incompatible claims about the same state "
                "for overlapping relevant time."
            ),
            "temporal_update": (
                "Different claims describe successive legitimate states "
                "at different times."
            ),
        },
    },

    "out_of_slice_evidence": {
        "type": "choice",
        "instructions": (
            "Evaluate ONLY retrieved memories where "
            "active_at_question_time=false. "
            "If there are none, choose none."
        ),
        "criteria": {
            "none": (
                "There are no retrieved out-of-slice memories."
            ),
            "relevant": (
                "At least one out-of-slice memory is useful or necessary "
                "for answering or interpreting the query."
            ),
            "harmful": (
                "At least one out-of-slice memory is misleading or "
                "introduces harmful stale information."
            ),
        },
    },
}


EVIDENCE_QUESTIONS = {
    "reference_evidence_present": {
        "type": "noul",
        "instructions": (
            "Does the retrieved context semantically contain the benchmark "
            "reference evidence needed for this query? Judge ONLY "
            "retrieved_memories. Do not count reference_evidence itself "
            "as retrieved."
        ),
    },

    "answer_inferable": {
        "type": "noul",
        "instructions": (
            "Can the correct answer to the query be reliably determined "
            "from retrieved_memories and their temporal metadata alone?"
        ),
    },
}


def call_jev(state, questions, retries=5):
    payload = {
        "model": MODEL,
        "state": state,
        "questions": questions,
    }

    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=120,
            ) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.HTTPError:
            raise

        except (
            urllib.error.URLError,
            TimeoutError,
        ) as e:
            print(
                f"Network error "
                f"(attempt {attempt}/{retries}): {e}",
                flush=True,
            )

            if attempt == retries:
                raise

            time.sleep(10 * attempt)


def bool_from_noul(answer, threshold=0.5):
    probability_yes = answer["noul"]

    return (
        probability_yes >= threshold,
        probability_yes,
    )


all_traces = load_jsonl(TRACES_PATH)

if len(all_traces) != 135:
    raise RuntimeError(
        f"Expected 135 traces, got {len(all_traces)}"
    )


existing = []

if OUT_PATH.exists():
    existing = json.loads(
        OUT_PATH.read_text(encoding="utf-8")
    )

completed = {
    item["trace_id"]
    for item in existing
}

results = list(existing)

print("Target traces:", len(all_traces))
print("Already completed:", len(completed))


for i, trace in enumerate(
    all_traces,
    start=1,
):
    trace_id = trace["trace_id"]

    if trace_id in completed:
        print(
            f"[{i}/{len(all_traces)}] "
            f"SKIP {trace_id}"
        )
        continue

    print(
        f"[{i}/{len(all_traces)}] "
        f"{trace_id}"
    )

    try:
        raw_consistency = call_jev(
            build_consistency_state(trace),
            CONSISTENCY_QUESTIONS,
        )

        time.sleep(1)

        raw_evidence = call_jev(
            build_evidence_state(trace),
            EVIDENCE_QUESTIONS,
        )

    except urllib.error.HTTPError as e:
        body = e.read().decode(
            "utf-8",
            errors="replace",
        )

        print(
            "HTTP ERROR:",
            e.code,
            body,
        )

        raise

    consistency_answers = raw_consistency["answers"]
    evidence_answers = raw_evidence["answers"]

    evidence_present, evidence_p = bool_from_noul(
        evidence_answers[
            "reference_evidence_present"
        ]
    )

    answer_inferable, inferable_p = bool_from_noul(
        evidence_answers[
            "answer_inferable"
        ]
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

        "models": {
            "consistency":
                raw_consistency.get(
                    "model",
                    MODEL,
                ),

            "evidence":
                raw_evidence.get(
                    "model",
                    MODEL,
                ),
        },

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

        "usage": {
            "consistency":
                raw_consistency.get("usage"),

            "evidence":
                raw_evidence.get("usage"),
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

    time.sleep(1)


print()
print("Saved:", OUT_PATH)
print(
    "Completed:",
    len(results),
    "/",
    len(all_traces),
)


print("\nSUMMARY BY POLICY")

for policy in sorted({
    item["retrieval_policy"]
    for item in results
}):
    rows = [
        item
        for item in results
        if item["retrieval_policy"] == policy
    ]

    consistency = Counter(
        item["verdict"]["consistency_status"]
        for item in rows
    )

    conflicts = Counter(
        item["verdict"]["conflict_type"]
        for item in rows
    )

    out_of_slice = Counter(
        item["verdict"]["out_of_slice_evidence"]
        for item in rows
    )

    reference_present = sum(
        item["verdict"][
            "reference_evidence_present"
        ]
        for item in rows
    )

    inferable = sum(
        item["verdict"]["answer_inferable"]
        for item in rows
    )

    indirect = sum(
        item["verdict"]["support_type"]
        == "indirect_inference"
        for item in rows
    )

    print()
    print(policy)
    print("  n:", len(rows))
    print(
        "  consistency:",
        dict(consistency),
    )
    print(
        "  conflict_type:",
        dict(conflicts),
    )
    print(
        "  out_of_slice:",
        dict(out_of_slice),
    )
    print(
        "  reference_evidence_present:",
        f"{reference_present}/{len(rows)}",
    )
    print(
        "  answer_inferable:",
        f"{inferable}/{len(rows)}",
    )
    print(
        "  indirect_inference:",
        indirect,
    )

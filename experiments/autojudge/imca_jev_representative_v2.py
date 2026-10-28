import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

MODEL = "typesafe/jev-1.14"
API_URL = "https://openrouter.ai/api/alpha/decisions"

TRACES_PATH = Path("results/autojudge_traces.jsonl")
GLM_PATH = Path("results/autojudge_representative_glm.json")
OUT_PATH = Path("results/autojudge_representative_jev_v2.json")

API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is not set")


def load_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def timestamp_to_date(value):
    if value is None:
        return None

    return datetime.fromtimestamp(
        value,
        tz=timezone.utc
    ).strftime("%Y-%m-%d")


def build_state(trace):
    question = next(
        x for x in trace["history_for_evaluating"]
        if x.get("step") == "question"
    )

    memories = []

    for item in trace["history_for_evaluating"]:
        if item.get("step") != "retrieved_memory":
            continue

        memories.append({
            "rank": item.get("rank"),
            "memory_id": item.get("memory_id"),
            "content": item.get("content"),

            # Normalized human-readable dates
            "valid_from_date": timestamp_to_date(
                item.get("valid_from")
            ),
            "valid_to_date": timestamp_to_date(
                item.get("valid_to")
            ),

            # Already computed by our deterministic code
            "active_at_question_time":
                item.get("active_at_question_time"),
        })

    return {
        "task": (
            "Evaluate ONLY the retrieved memories below. "
            "Determine whether they are temporally and semantically "
            "consistent and whether they contain enough evidence "
            "to answer the query."
        ),

        "query": trace["query"],

        "question_date": timestamp_to_date(
            question.get("question_time")
        ),

        "retrieved_memories": memories,

        "reference_evidence": trace.get(
            "reference_evidence",
            []
        ),

        "rules": [
            (
                "Use the supplied calendar dates directly. "
                "Do not infer or convert Unix timestamps."
            ),
            (
                "The field active_at_question_time is authoritative "
                "for deciding whether a retrieved memory lies inside "
                "or outside the strict temporal slice."
            ),
            (
                "If every retrieved memory has "
                "active_at_question_time=true, then "
                "out_of_slice_evidence MUST be none."
            ),
            (
                "A memory with active_at_question_time=false may still "
                "be relevant if it helps answer a retrospective or "
                "transition question."
            ),
            (
                "For missing_required_evidence, compare the semantic "
                "content of retrieved memories with reference_evidence. "
                "Exact wording is not required."
            ),
            (
                "If a retrieved memory semantically contains the "
                "reference evidence needed to answer the query, "
                "missing_required_evidence must be false."
            ),
            (
                "supports_answer should be true only when the retrieved "
                "memories contain enough information to determine the "
                "correct answer to the query."
            ),
            (
                "A legitimate change of state across different time "
                "periods is a temporal_update, not a true_conflict."
            ),
            (
                "A true_conflict requires incompatible claims about "
                "the same relevant state during overlapping time."
            ),
        ],

        "definitions": {
            "consistent": (
                "The retrieved memories can be interpreted together "
                "without incompatible claims about the same state "
                "and relevant time."
            ),
            "true_conflict": (
                "Two or more retrieved memories make incompatible "
                "claims about the same state for overlapping relevant "
                "time periods."
            ),
            "temporal_update": (
                "Different values describe a legitimate change of "
                "state across different time periods."
            ),
            "out_of_slice_relevant": (
                "A memory outside the strict temporal slice is still "
                "useful or necessary for answering the query."
            ),
            "out_of_slice_harmful": (
                "A memory outside the strict temporal slice is stale "
                "or misleading for the query."
            ),
            "missing_required_evidence": (
                "Information needed to determine the correct answer "
                "is present in reference_evidence but is not represented "
                "semantically in the retrieved memories."
            ),
            "supports_answer": (
                "The retrieved memories contain enough evidence to "
                "determine the correct answer."
            ),
        },
    }


QUESTIONS = {
    "consistency_status": {
        "type": "choice",
        "instructions": (
            "Classify the consistency of the retrieved memories "
            "with respect to the query and relevant time."
        ),
        "criteria": {
            "consistent": (
                "The memories can be interpreted coherently without "
                "an incompatible same-time claim."
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
            "Classify the relationship between differing claims. "
            "Use temporal_update for legitimate state change over time."
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
                "The different claims describe successive states at "
                "different times."
            ),
        },
    },

    "out_of_slice_evidence": {
        "type": "choice",
        "instructions": (
            "Evaluate ONLY memories where "
            "active_at_question_time=false. "
            "If no such retrieved memory exists, choose none."
        ),
        "criteria": {
            "none": (
                "There are no retrieved memories with "
                "active_at_question_time=false."
            ),
            "relevant": (
                "At least one out-of-slice memory is useful or necessary "
                "for answering the query."
            ),
            "harmful": (
                "At least one out-of-slice memory is misleading or "
                "introduces harmful stale information."
            ),
        },
    },

    "missing_required_evidence": {
        "type": "noul",
        "instructions": (
            "Is evidence required to determine the correct answer "
            "missing from the retrieved memories? "
            "Compare retrieved memories semantically with the supplied "
            "reference_evidence. If a retrieved memory expresses the "
            "required reference fact, answer no."
        ),
    },

    "supports_answer": {
        "type": "noul",
        "instructions": (
            "Do the retrieved memories contain enough temporal and "
            "semantic evidence to determine the correct answer to the "
            "query?"
        ),
    },
}


def call_jev(state):
    payload = {
        "model": MODEL,
        "state": state,
        "questions": QUESTIONS,
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=120
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def bool_from_noul(answer, threshold=0.5):
    probability_yes = answer["noul"]
    return probability_yes >= threshold, probability_yes


glm_results = json.loads(GLM_PATH.read_text())

target_trace_ids = [
    x["trace_id"]
    for x in glm_results
]

all_traces = {
    x["trace_id"]: x
    for x in load_jsonl(TRACES_PATH)
}


existing = []

if OUT_PATH.exists():
    existing = json.loads(
        OUT_PATH.read_text()
    )

completed = {
    x["trace_id"]
    for x in existing
}

results = list(existing)

print("Target traces:", len(target_trace_ids))
print("Already completed:", len(completed))


for i, trace_id in enumerate(
    target_trace_ids,
    start=1
):
    if trace_id in completed:
        print(
            f"[{i}/{len(target_trace_ids)}] "
            f"SKIP {trace_id}"
        )
        continue

    trace = all_traces[trace_id]
    state = build_state(trace)

    print(
        f"[{i}/{len(target_trace_ids)}] "
        f"{trace_id}"
    )

    try:
        raw = call_jev(state)

    except urllib.error.HTTPError as e:
        body = e.read().decode(
            "utf-8",
            errors="replace"
        )

        print(
            "HTTP ERROR:",
            e.code,
            body
        )
        raise

    answers = raw["answers"]

    missing_bool, missing_p = bool_from_noul(
        answers["missing_required_evidence"]
    )

    supports_bool, supports_p = bool_from_noul(
        answers["supports_answer"]
    )

    result = {
        "trace_id": trace["trace_id"],
        "case_id": trace["case_id"],
        "retrieval_policy":
            trace["retrieval_policy"],
        "query": trace["query"],
        "model": raw.get(
            "model",
            MODEL
        ),

        "verdict": {
            "consistency_status":
                answers["consistency_status"]["choice"],

            "conflict_type":
                answers["conflict_type"]["choice"],

            "out_of_slice_evidence":
                answers["out_of_slice_evidence"]["choice"],

            "missing_required_evidence":
                missing_bool,

            "supports_answer":
                supports_bool,
        },

        "probabilities": {
            "consistency_status":
                answers[
                    "consistency_status"
                ].get("probabilities"),

            "conflict_type":
                answers[
                    "conflict_type"
                ].get("probabilities"),

            "out_of_slice_evidence":
                answers[
                    "out_of_slice_evidence"
                ].get("probabilities"),

            "missing_required_evidence_yes":
                missing_p,

            "supports_answer_yes":
                supports_p,
        },

        "usage": raw.get("usage"),
        "request_id": raw.get("id"),
    }

    results.append(result)

    OUT_PATH.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2
        )
    )

    time.sleep(1)


print(
    "\nSaved:",
    OUT_PATH
)

print(
    "Completed:",
    len(results),
    "/",
    len(target_trace_ids)
)


print("\nSUPPORTS_ANSWER SUMMARY")

for policy in sorted({
    x["retrieval_policy"]
    for x in results
}):
    rows = [
        x
        for x in results
        if x["retrieval_policy"] == policy
    ]

    supported = sum(
        x["verdict"]["supports_answer"]
        for x in rows
    )

    print(
        f"{policy:20s} "
        f"{supported}/{len(rows)}"
    )

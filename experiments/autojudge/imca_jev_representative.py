import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

MODEL = "typesafe/jev-1.14"
API_URL = "https://openrouter.ai/api/alpha/decisions"

TRACES_PATH = Path("results/autojudge_traces.jsonl")
GLM_PATH = Path("results/autojudge_representative_glm.json")
OUT_PATH = Path("results/autojudge_representative_jev.json")

API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is not set")


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_state(trace):
    memories = []

    for item in trace["history_for_evaluating"]:
        if item.get("step") == "retrieved_memory":
            memories.append({
                "rank": item.get("rank"),
                "memory_id": item.get("memory_id"),
                "content": item.get("content"),
                "valid_from": item.get("valid_from"),
                "valid_to": item.get("valid_to"),
                "active_at_question_time": item.get("active_at_question_time"),
            })

    question = next(
        x for x in trace["history_for_evaluating"]
        if x.get("step") == "question"
    )

    return {
        "task": (
            "Evaluate the retrieved memory context for temporal and semantic "
            "consistency and determine whether it contains enough evidence "
            "to answer the query."
        ),
        "query": trace["query"],
        "question_time": question.get("question_time"),
        "retrieved_memories": memories,
        "reference_evidence": trace.get("reference_evidence", []),
        "diagnostic_signals": trace.get("diagnostic_signals", {}),
        "definitions": {
            "true_conflict": (
                "Two or more retrieved memories make incompatible claims "
                "about the same state for an overlapping relevant time period."
            ),
            "temporal_update": (
                "Different values describe a legitimate change of state "
                "across different time periods rather than a contradiction."
            ),
            "out_of_slice_relevant": (
                "A memory outside the strict temporal slice is still useful "
                "or necessary for answering the query."
            ),
            "out_of_slice_harmful": (
                "A memory outside the strict temporal slice is misleading, "
                "stale, or introduces harmful conflict for answering the query."
            ),
            "missing_required_evidence": (
                "Evidence required to determine the answer exists in the "
                "reference evidence but is absent from retrieved memories."
            ),
            "supports_answer": (
                "The retrieved memories contain enough information to determine "
                "the correct answer to the query."
            ),
        },
    }


QUESTIONS = {
    "consistency_status": {
        "type": "choice",
        "instructions": (
            "Classify the semantic and temporal consistency of the retrieved "
            "memories with respect to the query."
        ),
        "criteria": {
            "consistent": (
                "The retrieved memories do not contain incompatible claims "
                "that prevent a coherent interpretation."
            ),
            "conflicting": (
                "The retrieved memories contain incompatible claims about the "
                "same relevant state or time period."
            ),
            "underdetermined": (
                "The retrieved information is insufficient to determine whether "
                "the apparent differences are consistent or conflicting."
            ),
        },
    },
    "conflict_type": {
        "type": "choice",
        "instructions": (
            "If there is an apparent disagreement among retrieved memories, "
            "classify what kind it is."
        ),
        "criteria": {
            "none": (
                "There is no relevant disagreement between retrieved memories."
            ),
            "true_conflict": (
                "Retrieved memories make incompatible claims about the same "
                "state during an overlapping relevant time period."
            ),
            "temporal_update": (
                "Different claims represent a legitimate change of state across "
                "different time periods rather than a true contradiction."
            ),
        },
    },
    "out_of_slice_evidence": {
        "type": "choice",
        "instructions": (
            "Evaluate retrieved memories that are outside the strict temporal "
            "slice of the query."
        ),
        "criteria": {
            "none": (
                "No relevant out-of-slice memory is present."
            ),
            "relevant": (
                "Out-of-slice information is useful or necessary for answering "
                "the query."
            ),
            "harmful": (
                "Out-of-slice information is stale, misleading, or introduces "
                "harmful conflict for the query."
            ),
        },
    },
    "missing_required_evidence": {
        "type": "noul",
        "instructions": (
            "Is evidence required to determine the correct answer missing from "
            "the retrieved memories, given the supplied reference evidence?"
        ),
    },
    "supports_answer": {
        "type": "noul",
        "instructions": (
            "Do the retrieved memories contain enough evidence to determine "
            "the correct answer to the query?"
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

    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def bool_from_noul(answer, threshold=0.5):
    p = answer["noul"]
    return p >= threshold, p


glm_results = json.loads(GLM_PATH.read_text())
target_trace_ids = [x["trace_id"] for x in glm_results]

all_traces = {
    x["trace_id"]: x
    for x in load_jsonl(TRACES_PATH)
}

existing = []
if OUT_PATH.exists():
    existing = json.loads(OUT_PATH.read_text())

completed = {x["trace_id"] for x in existing}

print("Target traces:", len(target_trace_ids))
print("Already completed:", len(completed))

results = list(existing)

for i, trace_id in enumerate(target_trace_ids, start=1):
    if trace_id in completed:
        print(f"[{i}/{len(target_trace_ids)}] SKIP {trace_id}")
        continue

    trace = all_traces[trace_id]
    state = build_state(trace)

    print(f"[{i}/{len(target_trace_ids)}] {trace_id}")

    try:
        raw = call_jev(state)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print("HTTP ERROR:", e.code, body)
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
        "retrieval_policy": trace["retrieval_policy"],
        "query": trace["query"],
        "model": raw.get("model", MODEL),
        "verdict": {
            "consistency_status":
                answers["consistency_status"]["choice"],
            "conflict_type":
                answers["conflict_type"]["choice"],
            "out_of_slice_evidence":
                answers["out_of_slice_evidence"]["choice"],
            "missing_required_evidence": missing_bool,
            "supports_answer": supports_bool,
        },
        "probabilities": {
            "consistency_status":
                answers["consistency_status"].get("probabilities"),
            "conflict_type":
                answers["conflict_type"].get("probabilities"),
            "out_of_slice_evidence":
                answers["out_of_slice_evidence"].get("probabilities"),
            "missing_required_evidence_yes": missing_p,
            "supports_answer_yes": supports_p,
        },
        "confidence": {
            "consistency_status":
                answers["consistency_status"].get("confidence"),
            "conflict_type":
                answers["conflict_type"].get("confidence"),
            "out_of_slice_evidence":
                answers["out_of_slice_evidence"].get("confidence"),
        },
        "usage": raw.get("usage"),
        "request_id": raw.get("id"),
    }

    results.append(result)

    OUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2)
    )

    time.sleep(1)

print("\nSaved:", OUT_PATH)
print("Completed:", len(results), "/", len(target_trace_ids))

print("\nSUPPORTS_ANSWER SUMMARY")
for policy in sorted({x["retrieval_policy"] for x in results}):
    rows = [x for x in results if x["retrieval_policy"] == policy]
    supported = sum(
        x["verdict"]["supports_answer"]
        for x in rows
    )
    print(f"{policy:20s} {supported}/{len(rows)}")

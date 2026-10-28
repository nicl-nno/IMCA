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
OUT_PATH = Path("results/autojudge_evidence_vs_inference_jev.json")

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
            "valid_from_date": timestamp_to_date(
                item.get("valid_from")
            ),
            "valid_to_date": timestamp_to_date(
                item.get("valid_to")
            ),
            "active_at_question_time":
                item.get("active_at_question_time"),
        })

    return {
        "query": trace["query"],

        "question_date": timestamp_to_date(
            question.get("question_time")
        ),

        "retrieved_memories": memories,

        "reference_evidence": trace.get(
            "reference_evidence",
            []
        ),

        "evaluation_rules": [
            (
                "Keep two concepts separate: whether benchmark "
                "reference evidence is present in retrieved memories, "
                "and whether the correct answer can be inferred from "
                "retrieved memories."
            ),
            (
                "Reference evidence may be used to understand what "
                "fact the benchmark expects, but it MUST NOT be treated "
                "as if it had been retrieved by the memory system."
            ),
            (
                "For reference_evidence_present, compare semantic "
                "meaning rather than exact wording."
            ),
            (
                "For answer_inferable, use ONLY retrieved memories, "
                "their dates, and temporal metadata as evidence."
            ),
            (
                "answer_inferable may be true even when "
                "reference_evidence_present is false, if other retrieved "
                "facts logically and temporally determine the answer."
            ),
            (
                "Do not require an explicit sentence containing the "
                "answer when the answer follows reliably from temporal "
                "or semantic relations in retrieved memories."
            ),
            (
                "If the retrieved context allows multiple plausible "
                "answers, answer_inferable should be false."
            ),
        ],
    }


QUESTIONS = {
    "reference_evidence_present": {
        "type": "noul",
        "instructions": (
            "Does the retrieved context contain the benchmark reference "
            "evidence needed for this query, allowing semantic paraphrases? "
            "Judge ONLY whether the required benchmark evidence is represented "
            "in retrieved_memories. Do not count reference_evidence itself "
            "as retrieved evidence."
        ),
    },

    "answer_inferable": {
        "type": "noul",
        "instructions": (
            "Can the correct answer to the query be reliably determined "
            "from retrieved_memories and their temporal metadata alone? "
            "The answer may be inferred indirectly. reference_evidence may "
            "help identify the benchmark's expected fact, but it must not "
            "be used as evidence available to the agent."
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
    p = answer["noul"]
    return p >= threshold, p


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

    print(
        f"[{i}/{len(target_trace_ids)}] "
        f"{trace_id}"
    )

    try:
        raw = call_jev(
            build_state(trace)
        )

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

    evidence_present, evidence_p = bool_from_noul(
        answers["reference_evidence_present"]
    )

    answer_inferable, inferable_p = bool_from_noul(
        answers["answer_inferable"]
    )

    if evidence_present and answer_inferable:
        support_type = "direct_or_reference_supported"

    elif not evidence_present and answer_inferable:
        support_type = "indirect_inference"

    elif evidence_present and not answer_inferable:
        support_type = "evidence_present_but_insufficient"

    else:
        support_type = "insufficient_context"

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

        "evaluation": {
            "reference_evidence_present":
                evidence_present,
            "answer_inferable":
                answer_inferable,
            "support_type":
                support_type,
        },

        "probabilities": {
            "reference_evidence_present_yes":
                evidence_p,
            "answer_inferable_yes":
                inferable_p,
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


print("\nSUMMARY BY POLICY")

policies = sorted({
    x["retrieval_policy"]
    for x in results
})

for policy in policies:
    rows = [
        x for x in results
        if x["retrieval_policy"] == policy
    ]

    ref = sum(
        x["evaluation"]["reference_evidence_present"]
        for x in rows
    )

    infer = sum(
        x["evaluation"]["answer_inferable"]
        for x in rows
    )

    indirect = sum(
        x["evaluation"]["support_type"]
        == "indirect_inference"
        for x in rows
    )

    print(
        f"{policy:20s} "
        f"reference={ref}/{len(rows)} "
        f"inferable={infer}/{len(rows)} "
        f"indirect={indirect}"
    )


print("\nINDIRECT INFERENCE CASES")

for x in results:
    if (
        x["evaluation"]["support_type"]
        == "indirect_inference"
    ):
        print(
            x["trace_id"],
            "| ref_p =",
            x["probabilities"][
                "reference_evidence_present_yes"
            ],
            "| infer_p =",
            x["probabilities"][
                "answer_inferable_yes"
            ],
        )

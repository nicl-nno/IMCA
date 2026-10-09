import asyncio
import json
import re
from pathlib import Path

from autojudge.agent_pool import AgentPool
from autojudge.pipeline.node import AgentNode
from autojudge.meta_agents.graph_gen import get_parallel_graph
from autojudge.pipeline import PipelineBuilder


TRACE_FILE = Path(
    "/home/nichi/projects/IMCA/results/autojudge_traces.jsonl"
)

OUTPUT_FILE = Path(
    "/home/nichi/projects/IMCA/results/autojudge_case001_fixed_judges_v2.json"
)

CASE_PREFIX = "halumem-memory-conflict-001__"


CONSISTENCY_INSTRUCTIONS = """
You are the CONSISTENCY_JUDGE.

Evaluate ONLY the retrieved memory items supplied in the task.

Determine whether the retrieved facts contain a genuine semantic contradiction.

A true conflict requires incompatible claims about the same relevant
entity, property/event, scope, and time.

Important:
- Judge contradictions ONLY among retrieved memory items.
- The query is a question, not a factual assertion and cannot itself conflict
  with retrieved evidence.
- Reference evidence is benchmark metadata, NOT part of retrieved memory and
  must never be counted as a retrieved conflict.
- Different events are not automatically contradictory.
- "Sabbatical" and "retirement" are different events.
- A fact that merely fails to answer the question is not a contradiction.
- Do not invent facts.

Return a concise assessment for the final aggregator.
"""


TEMPORAL_INSTRUCTIONS = """
You are the TEMPORAL_JUDGE.

Evaluate temporal relations among the retrieved memory items.

Use ONLY temporal metadata attached to retrieved memory items:
- question_time
- valid_from
- valid_to
- active_at_question_time

Reference evidence is benchmark metadata and must not be treated as a
retrieved memory item.

Distinguish:
1. genuine same-time contradiction,
2. legitimate temporal update/change,
3. facts outside the strict question-time slice.

A later or earlier fact is not automatically harmful or contradictory.
A temporal change across different periods should normally be classified
as a temporal update, not a true conflict.

Do not invent missing events.

Return a concise assessment for the final aggregator.
"""


EVIDENCE_INSTRUCTIONS = """
You are the EVIDENCE_JUDGE.

Evaluate whether the retrieved memory context contains enough evidence
to answer the query reliably.

Use the supplied reference_evidence ONLY as benchmark guidance for deciding
whether the retrieved context contains the evidence needed to answer.

Do not treat reference_evidence as if it had been retrieved.

Determine:
- whether required evidence is present,
- whether critical evidence is missing,
- whether the retrieved context supports an answer to the question.

Important:
- supports_answer=true means the retrieved context is sufficient to determine
  the answer, whether the correct answer is YES or NO.
- Evidence may therefore support either a positive or negative answer.
- A later fact may still be necessary for a retrospective comparison.
- Do not require an explicit affirmative statement when temporal evidence
  can validly establish a negative answer.
- Do not invent facts.

Return a concise assessment for the final aggregator.
"""


OUT_OF_SLICE_INSTRUCTIONS = """
You are the OUT_OF_SLICE_JUDGE.

Focus specifically on retrieved items whose
active_at_question_time is false.

Classify out-of-slice evidence semantically:

- none:
  no out-of-slice items are retrieved.

- relevant:
  at least one out-of-slice item is useful or necessary for answering
  the question, for temporal comparison, retrospective reasoning,
  transition detection, or establishing that an event occurred later.

- harmful:
  out-of-slice evidence is irrelevant or misleading and may cause
  an incorrect interpretation.

Do NOT classify evidence as harmful merely because it is outside
the strict temporal slice.

Use ONLY the retrieved items and their temporal metadata for this
classification.

Reference evidence must NOT be classified as out-of-slice evidence because it
was not retrieved.

If every retrieved item has active_at_question_time=true, return "none".

Return a concise assessment for the final aggregator.
"""


FINAL_INSTRUCTIONS = """
You are the FINAL_AGGREGATOR.

Combine the assessments of the fixed specialist judges.

Evaluate the retrieved memory context, not the retrieval method itself.

Use this taxonomy:

consistency_status:
- consistent
- conflicting
- underdetermined

conflict_type:
- none
- true_conflict
- temporal_update

out_of_slice_evidence:
- none
- relevant
- harmful

Rules:
- Evaluate consistency among RETRIEVED memories only.
- The query is a question, not a factual assertion.
- Reference evidence is benchmark metadata, not retrieved evidence.
  It may be used only to assess whether required evidence is present.
  It must never itself create a retrieved conflict or count as out-of-slice.
- Different events are not automatically a true conflict.
- Temporal changes across different periods should not be mislabeled
  as same-time contradictions.
- Out-of-slice evidence can be relevant.
- Missing evidence and contradiction are different problems.
- supports_answer=true means the retrieved context is sufficient to determine
  the answer, including a negative answer.
- Do not invent facts.

Return ONLY one valid JSON object, without Markdown fences:

{
  "consistency_status": "consistent | conflicting | underdetermined",
  "conflict_type": "none | true_conflict | temporal_update",
  "out_of_slice_evidence": "none | relevant | harmful",
  "missing_required_evidence": true,
  "supports_answer": true,
  "confidence": 0.0,
  "reason": "short evidence-grounded explanation"
}
"""


def make_fixed_pool():
    agents = [
        AgentNode(
            name="CONSISTENCY_JUDGE",
            instructions=CONSISTENCY_INSTRUCTIONS,
            use_tools=False,
        ),
        AgentNode(
            name="TEMPORAL_JUDGE",
            instructions=TEMPORAL_INSTRUCTIONS,
            use_tools=False,
        ),
        AgentNode(
            name="EVIDENCE_JUDGE",
            instructions=EVIDENCE_INSTRUCTIONS,
            use_tools=False,
        ),
        AgentNode(
            name="OUT_OF_SLICE_JUDGE",
            instructions=OUT_OF_SLICE_INSTRUCTIONS,
            use_tools=False,
        ),
        AgentNode(
            name="FINAL_AGGREGATOR",
            instructions=FINAL_INSTRUCTIONS,
            use_tools=False,
        ),
    ]

    return AgentPool(agents)


def load_case_traces():
    traces = []

    with TRACE_FILE.open(encoding="utf-8") as f:
        for line in f:
            trace = json.loads(line)

            if trace["trace_id"].startswith(CASE_PREFIX):
                traces.append(trace)

    if len(traces) != 5:
        raise RuntimeError(
            f"Expected 5 traces for case 001, found {len(traces)}"
        )

    return sorted(
        traces,
        key=lambda x: x["retrieval_policy"],
    )


def parse_json_verdict(value):
    if isinstance(value, dict):
        return value

    text = str(value).strip()

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if not match:
        return {
            "_parse_error": True,
            "_raw": text,
        }

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {
            "_parse_error": True,
            "_raw": text,
        }


async def evaluate(trace):
    # IMPORTANT:
    # retrieval_policy is intentionally NOT given to the judges.
    judge_input = {
        "query": trace["query"],
        "history_for_evaluating": trace["history_for_evaluating"],
        "reference_evidence": trace["reference_evidence"],
        "diagnostic_signals": trace.get("diagnostic_signals", {}),
    }

    # Fresh pool with identical instructions for every policy.
    pool = make_fixed_pool()

    graph = get_parallel_graph(pool)

    pipeline = (
        PipelineBuilder()
        .create_from_pool(pool, graph)
        .build()
    )

    verdict_raw = await pipeline.ainvoke(judge_input)
    verdict = parse_json_verdict(verdict_raw)

    return {
        "trace_id": trace["trace_id"],
        "retrieval_policy": trace["retrieval_policy"],
        "query": trace["query"],
        "verdict": verdict,
        "verdict_raw": str(verdict_raw),
    }


async def main():
    traces = load_case_traces()

    # Resume previous successful evaluations if the output file exists.
    if OUTPUT_FILE.exists():
        try:
            results = json.loads(
                OUTPUT_FILE.read_text(encoding="utf-8")
            )
        except Exception:
            results = []
    else:
        results = []

    completed = {
        result["retrieval_policy"]
        for result in results
        if "retrieval_policy" in result
    }

    print("Fixed evaluator")
    print("Case:", CASE_PREFIX)
    print("Policies:", len(traces))
    print("Already completed:", sorted(completed))
    print()

    for i, trace in enumerate(traces, start=1):
        policy = trace["retrieval_policy"]

        if policy in completed:
            print("=" * 80)
            print(f"{i}/{len(traces)}  {policy}  [SKIP: already completed]")
            print("=" * 80)
            continue

        print("=" * 80)
        print(f"{i}/{len(traces)}  {policy}")
        print("=" * 80)

        max_attempts = 4

        for attempt in range(1, max_attempts + 1):
            try:
                result = await evaluate(trace)
                results.append(result)
                completed.add(policy)

                # Save immediately after every successful policy.
                OUTPUT_FILE.write_text(
                    json.dumps(
                        results,
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                print(
                    json.dumps(
                        result["verdict"],
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                print()
                print("Checkpoint saved:", OUTPUT_FILE)
                print()
                break

            except RuntimeError as exc:
                message = str(exc)

                retryable = (
                    "in_flight_budget_exhausted" in message
                    or "Retry-After" in message
                )

                if retryable and attempt < max_attempts:
                    wait_seconds = 130

                    print()
                    print(
                        f"Temporary OpenRouter in-flight limit "
                        f"(attempt {attempt}/{max_attempts})."
                    )
                    print(
                        f"Waiting {wait_seconds} seconds before retrying "
                        f"{policy}..."
                    )
                    print()

                    await asyncio.sleep(wait_seconds)
                    continue

                raise

        # Small gap before starting the next policy.
        if policy != traces[-1]["retrieval_policy"]:
            print("Waiting 20 seconds before next policy...")
            await asyncio.sleep(20)

    # Stable ordering in the saved result.
    results.sort(key=lambda x: x["retrieval_policy"])

    OUTPUT_FILE.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)

    for result in results:
        v = result["verdict"]

        print()
        print("POLICY:", result["retrieval_policy"])
        print(" consistency:", v.get("consistency_status"))
        print(" conflict:", v.get("conflict_type"))
        print(" out-of-slice:", v.get("out_of_slice_evidence"))
        print(" missing:", v.get("missing_required_evidence"))
        print(" supports:", v.get("supports_answer"))
        print(" confidence:", v.get("confidence"))

    print()
    print("Completed:", len(results), "/", len(traces))
    print("Saved:", OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
from pathlib import Path

from autojudge.meta_agents import PoolGenerator
from autojudge.meta_agents.graph_gen import get_parallel_graph
from autojudge.meta_agents.prompts import examples_no_tools
from autojudge.pipeline import PipelineBuilder


TRACE_FILE = Path(
    "/home/nichi/projects/IMCA/results/autojudge_traces.jsonl"
)

OUTPUT_FILE = Path(
    "/home/nichi/projects/IMCA/results/autojudge_case001_verdicts.json"
)

CASE_PREFIX = "halumem-memory-conflict-001__"


TAXONOMY = """
1. consistent
   Retrieved facts are mutually compatible for the question.

2. true_conflict
   Retrieved facts make incompatible claims about the same entity,
   property, scope, and relevant time.

3. temporal_update
   Apparently different facts describe legitimate states at different times.

4. stale_but_relevant
   A fact is outside the strict query-time slice but is still necessary
   as historical or contrastive evidence for answering the question.

5. stale_and_harmful
   A fact is outside the query-time slice, is not needed for answering,
   and may mislead the answer.

6. missing_required_evidence
   The retrieved context is missing evidence required for a reliable answer.

7. insufficient_information
   The available retrieved context is not sufficient to determine the
   temporal or consistency relation confidently.
"""


OUTPUT_SCHEMA = """
Return ONLY a valid JSON object:
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

    return traces


async def evaluate_trace(trace):
    judge_input = {
        "query": trace["query"],
        "history_for_evaluating": trace["history_for_evaluating"],
    }

    print()
    print("=" * 80)
    print("TRACE:", trace["trace_id"])
    print("POLICY:", trace["retrieval_policy"])
    print("=" * 80)

    pool_gen = PoolGenerator(
        output_schema=OUTPUT_SCHEMA,
        taxonomy=TAXONOMY,
        examples=examples_no_tools,
    )

    pool = await pool_gen.create_pool(judge_input)

    graph = get_parallel_graph(pool)

    pipeline = (
        PipelineBuilder()
        .create_from_pool(pool, graph)
        .build()
    )

    verdict = await pipeline.ainvoke(judge_input)

    return {
        "trace_id": trace["trace_id"],
        "retrieval_policy": trace["retrieval_policy"],
        "query": trace["query"],
        "verdict_raw": verdict,
    }


async def main():
    traces = load_case_traces()

    results = []

    for i, trace in enumerate(traces, start=1):
        print(f"\nRunning {i}/{len(traces)}")
        result = await evaluate_trace(trace)
        results.append(result)

    OUTPUT_FILE.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print("DONE")
    print("Saved:", OUTPUT_FILE)
    print("=" * 80)

    for result in results:
        print()
        print("POLICY:", result["retrieval_policy"])
        print("VERDICT:")
        print(result["verdict_raw"])


if __name__ == "__main__":
    asyncio.run(main())

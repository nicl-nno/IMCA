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

TARGET_TRACE = "halumem-memory-conflict-001__query_aware"


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


def load_trace():
    with TRACE_FILE.open(encoding="utf-8") as f:
        for line in f:
            trace = json.loads(line)
            if trace["trace_id"] == TARGET_TRACE:
                return trace

    raise RuntimeError(f"Trace not found: {TARGET_TRACE}")


async def main():
    trace = load_trace()

    judge_input = {
        "query": trace["query"],
        "history_for_evaluating": trace["history_for_evaluating"],
    }

    print("TRACE:", trace["trace_id"])
    print("QUESTION:", trace["query"])
    print()

    pool_gen = PoolGenerator(
        output_schema=OUTPUT_SCHEMA,
        taxonomy=TAXONOMY,
        examples=examples_no_tools,
    )

    print("Generating judge pool...")
    pool = await pool_gen.create_pool(judge_input)

    print("\nJudge pool generated.")

    graph = get_parallel_graph(pool)

    pipeline = (
        PipelineBuilder()
        .create_from_pool(pool, graph)
        .build()
    )

    print("\nEvaluation graph:")
    print(pipeline.to_mermaid_lr())

    print("\nRunning AutoJudge...")

    verdict = await pipeline.ainvoke(judge_input)

    print("\nFINAL VERDICT:")
    print(verdict)


if __name__ == "__main__":
    asyncio.run(main())

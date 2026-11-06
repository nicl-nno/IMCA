# Source-memory evaluation protocol

## Research question and comparisons

Does repository memory help a coding agent fix bugs under a fixed budget, and can retrieval-error explanations improve how the agent uses that memory?

| Comparison | Testable claim | Measurement | Current position |
| --- | --- | --- | --- |
| Memory versus no memory | Either memory method increases the fraction of repaired tasks. | Paired task outcomes under the same budget. | Two development cases; complete paired estimates are unavailable. |
| IMCA versus Codebase-Memory | IMCA repairs more tasks than Codebase-Memory under the same budget. | Tasks repaired only by each method, ties and unknown outcomes. | Both methods produced passing development patches; held-out evaluation is pending. |
| Search-first versus optional memory | Requiring an initial lookup improves repair outcomes. | Repair outcomes; actual search-and-read use as a separate check. | Prompt calibration on Django; a held-out policy comparison is pending. |
| Explanation-guided search | Choosing the next search from an explanation improves repair outcomes over ordinary repeated search. | Paired outcomes with the same remaining budget. | Planned. The choice rule must not use correct answers or reference fixes. |

The earlier 425-task LongMemCode comparison measures retrieval and remains separate from the repair experiments in this package.

## Fixed conditions

Compare one OpenCode 1.3.5 client with GLM-5.3-Flash in three conditions: without memory, with IMCA and with Codebase-Memory. Within a task, use the same source snapshot, shared user prompt, ordinary task tools and budget. Memory-specific tools differ by condition.

Each reported development block permits one original attempt per condition, 20 model request attempts and 900 seconds, including waits and tool use. The response cap is 8,192 tokens; the configured context setting is 32,768. This is not a measured equal input-token budget. Failed request attempts consume their reserved slots. Preserve all interruptions and budget-limit outcomes.

Both memory systems describe the starting source. IMCA uses its pinned structural routes with BM25 fallback and no supplied dense channel. Codebase-Memory uses the pinned v0.12.1 native fast mode with semantic indexing disabled. Identical input views do not imply identical internal indices: explicitly record built-in native exclusions while retaining every common input file. Unexpected omissions remain validation errors.

Use fresh task and client state. Freeze saved outputs and stop agent processes before reading benchmark test patches or expected test lists. For the held-out block, this applies to all original planned slots before scoring. Reference implementation patches are not used. The shared user prompts and source pins for the two development tasks are included in the evidence.

## Evaluation and reporting

Apply the saved patch and execute the task tests through the pinned evaluator. Also run the same tests on unchanged production source. An observed repair requires an original failing test, passing task tests after the patch, and no newly failing task tests.

Keep dataset test groups and measured test transitions separately. Missing or skipped required test results are evaluation issues. A transport interruption without a patch has an unknown repair outcome. A passing patch saved before interruption is reported as a passing artifact with an interrupted run.

Retain all five held-out cases, including preparation failures. Report the planned denominator, the complete paired subset and unknown outcomes separately. Development repetitions remain grouped by task. Request counts and time are descriptive secondary measurements.

Requests used the pinned image's Python 2.7 environment and a local HTTP/HTTPS test service; harness metadata specifies Python 3.9. The reported Requests results describe that recorded development runtime. The evaluator package is SWE-bench 4.1.0.

## Reproduction of the published analysis

The attached script recomputes the summary and table from included test outcomes, canonical evaluated patches and run metadata. Full agent execution additionally requires the task images, runtime services and model access. The package provides analysis reproduction, rather than a standalone agent launcher.

From the repository root:

```bash
python3 experiments/summarize_memory_repair_checks.py --check
python3 experiments/summarize_memory_repair_checks.py --table
python3 -m unittest discover -s experiments -p 'test_summarize_memory_repair_checks.py'
```

The code uses the Python standard library. Evidence checksums are in `experiments/memory_repair_evidence/manifest.json`. Project licenses accompany the patch artifacts.

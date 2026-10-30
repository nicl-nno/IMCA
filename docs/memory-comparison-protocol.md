# Comparison plan and conditions

## Research question

Does repository memory help a coding agent resolve more issues under the same budget, and can explanations of retrieval failures improve its use of memory?

Current-source retrieval and the use of previous repairs are evaluated separately.

## Questions and hypotheses

| ID | Claim | Experiment and status |
| --- | --- | --- |
| R1 | In the selected configurations, IMCA has a higher mean retrieval score than the Codebase-Memory structural-query adapter. | The 425-task LongMemCode comparison is complete. It provides descriptive development evidence, not a general superiority claim. |
| H1 | Memory access increases the fraction of resolved issues relative to an agent without memory under the same budget. | The first Sphinx pilot is complete. All three conditions produced no repair. The hypothesis is not yet supported. |
| H2 | A required first memory lookup increases resolution relative to optional memory access. | A separate comparison within each memory system is planned. |
| H3 | Choosing the next search using a retrieval-failure explanation increases resolution relative to repeated search with the same budget. | Planned. The selection rule must not use the task's correct answer. |

## Retrieval comparison

Use all 425 LongMemCode tasks and the same 44-file FastAPI source snapshot. Each result list is limited to five items.

IMCA uses structural retrieval and a lexical fallback without recorded dense rankings. Codebase-Memory supplies a real fast-mode index queried through a fixed structural adapter. Its candidates are sorted by qualified name before selecting the first five. BM25 uses question text.

Identifier-mapping rules do not use expected answers. Predictions are saved before scoring. Evaluation follows the original LongMemCode rules.

Retain every task, including repeated inputs and partial scores. The 425 tasks contain 328 distinct query-and-question inputs and must not be treated as fully independent observations. Report an equally weighted distinct-input result alongside the original metrics.

Candidate sets for all 228 distinct native queries were checked through the Codebase-Memory interface. Result ordering is applied by the adapter rather than taken from the raw native response.

## Agent pilot

Use `sphinx-doc__sphinx-8035` from SWE-bench Verified. Compare the same OpenCode 1.3.5 client and GLM-5.3-flash model in three conditions: without memory, with IMCA and with Codebase-Memory.

Each attempt receives fresh client state and a fresh container with the same starting code. The container has no network or host-file access. Ordinary file-reading, text-search, editing and local-test tools are shared across conditions.

Both memory systems index the same 182 Python files. Their indices describe the starting source and are not updated after agent edits. Memory access is optional, and actual tool use is recorded.

Allow one attempt per condition, at most ten model requests and 600 seconds. Configure ten client steps, a 2,048-token response cap and a minimum 30-second request interval. Failed requests and waiting consume the allowance. The response cap includes model reasoning tokens.

## Output freeze and evaluation

Stop client and task processes before collecting the repair. Compute the patch relative to the prepared starting container state, excluding pre-existing environment-setup changes.

Freeze all three outputs before the evaluator accesses the test patch and expected-test lists. Do not use the reference implementation patch.

For nonempty patches, evaluate in fresh containers using the original SWE-bench 4.1.0 scoring and log parser. Record the Windows text-transfer and offline-install adapters separately. Retain an empty patch as no submitted repair, without executing repair tests.

Record the task outcome, request count, provider-reported tokens, tool calls, elapsed time and stopping conditions. Missing usage is not zero. Preserve every attempt and prohibit automatic repair repeats.

## Next step

Test revised limits on development tasks first and apply the same settings to every condition. A main comparison requires a separate preselected task set. One pilot issue cannot establish a general memory advantage.

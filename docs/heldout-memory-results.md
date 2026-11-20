# Held-out source-memory repair comparison

## Setup

Five SWE-bench Verified tasks were selected from repositories not used for local development. Source preparation succeeded for Matplotlib, Pytest and Astropy. SymPy and scikit-learn exceeded the fixed source-indexing timeout and remain in the planned task inventory; they were not replaced.

Each prepared task had one original attempt in each condition: no memory, IMCA and Codebase-Memory. The model was GLM 5.3 Flash. Within each task, the source snapshot, main prompt, ordinary task tools and budget rules were identical. Each attempt allowed at most 20 forwarded requests and 900 seconds. The nine attempts used 151 forwarded requests, including provider rate-limit responses. No repair attempt was repeated.

IMCA used structural retrieval with BM25 fallback and no dense ranking. Codebase-Memory used native fast mode with semantic indexing disabled. Memory described the starting source only.

## Results

| Task | No memory | IMCA | Codebase-Memory |
|---|---|---|---|
| Matplotlib 24026 | Passed | Passed | Passed |
| Pytest 7236 | Empty patch | Passed | Passed |
| Astropy 8872 | Passed saved patch; interrupted run | Passed | Passed |
| SymPy 20438 | Not run | Not run | Not run |
| scikit-learn 10297 | Not run | Not run | Not run |

Passed means that the frozen patch passed all required and preserved benchmark tests. The evaluated test lists contained 766 tests for Matplotlib, 52 for Pytest and 81 for Astropy. Original-source controls failed the required tests and passed the preserved tests. All eight nonempty patches fixed those failures without introducing a failure in these test lists.

The evaluation used SWE-bench 4.1.0 test patches and grading in pinned task images. It reused the agent's prepared Python environment and worktree imports. Astropy used the NumPy 1.23.5 compatibility fixture fixed before the model runs, equally for original and patched source. This is an evaluation with declared runtime adapters. Benchmark test patches and lists were accessed after all nine outputs were frozen and all fifteen planned condition slots were accounted for, including six unavailable preparation slots. The reference implementation patches were not read.

## Interpretation

On the two tasks with three uninterrupted attempts, IMCA and Codebase-Memory each produced two passing repairs; the baseline produced one. Neither memory system repaired a task that the other failed to repair.

The Pytest baseline exhausted the 8,192-token output limit in its first completion and called no tools. Its empty patch is retained as observed, but this single case does not establish that memory caused the difference. The Astropy baseline received a provider rate-limit failure; its saved patch passed, while its interrupted run remains separate from the uninterrupted comparison.

These results establish working comparisons and verified repairs on a small held-out subset. They do not establish a general advantage of either memory system.

## Reproduce the analysis

The accompanying script verifies the evidence checksums and patch bytes, then recomputes the table and the uninterrupted paired subset from per-test observations. The evidence includes the shared prompts, runtime pins, original-source controls and frozen predictions. This package reproduces the analysis of the recorded runs; fresh model execution requires the separate experimental harness.

```bash
uv run --frozen python experiments/summarize_heldout_memory.py
uv run --frozen python -m pytest -q experiments/test_summarize_heldout_memory.py
```

Third-party patch excerpts and issue descriptions retain their original content. Repository license texts and source locations are included in the evidence directory.

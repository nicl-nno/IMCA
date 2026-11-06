# Memory-assisted code repair: development results

Five saved patches from two development tasks passed their task tests. Both memory-assisted Requests patches fixed a failure reproduced on unchanged source. Transport interruptions prevent a complete three-condition comparison.

The comparison uses GLM-5.3-Flash through OpenCode 1.3.5, with the same source, shared user prompt and ordinary task tools within each task. Each condition has one original attempt in the reported block, at most 20 model request attempts and 900 seconds. Memory conditions search and read a returned source result before ordinary task actions.

IMCA uses structural retrieval with BM25 fallback. Codebase-Memory uses native v0.12.1 fast mode with semantic indexing disabled.

## Development checks

| Task | Condition | Saved patch tests | Run outcome | Request attempts |
| --- | --- | --- | --- | --- |
| django__django-12193 | No memory | 12/12 | Finished | 17 |
| django__django-12193 | IMCA | 12/12 | Transport interruption | 12 |
| django__django-12193 | Codebase-Memory | 12/12 | Request limit | 20 |
| psf__requests-1724 | No memory | No patch | Transport interruption | 4 |
| psf__requests-1724 | IMCA | 85/85 | Finished | 12 |
| psf__requests-1724 | Codebase-Memory | 85/85 | Finished | 15 |

These are saved-patch test results, not a six-attempt success rate. The Requests baseline has an unknown repair outcome after interruption. Earlier Django calibration runs repeat the same task and do not add independent cases.

Both memory methods used search and source-reading tools on both tasks. In Requests, IMCA used about 406 seconds and Codebase-Memory about 468 seconds. Individual runs do not establish a general efficiency advantage.

The Requests unchanged-source control reproduced one failing Unicode-method test. Both memory-assisted patches fixed it without newly failing task tests. The image used Python 2.7, while evaluator metadata specifies Python 3.9. In this runtime, six tests labelled fail-to-pass already passed, and the actual failure was labelled pass-to-pass. Original labels and observed outcomes are retained separately. The Django unchanged-source control remains pending.

## Held-out preparation snapshot

All five originally selected tasks remain in the plan. Pytest indices and three agent connections have been checked. Both Astropy indices are ready: IMCA covers 767 common Python input files, while Codebase-Memory fast mode indexes 766 and records one built-in test-helper exclusion. Both methods receive all 767 input files.

SymPy exceeded the fixed one-hour preparation limit and remains incomplete. Scikit-learn requires restoration of image file permissions before indexing; Matplotlib preparation is pending. This snapshot contains no held-out agent repair results.

The attached analysis reproduces this table from frozen test outcomes, canonical evaluated patches and run metadata. The next evaluation requires completed runtime checks, fixed-budget attempts and unchanged-source controls.

See [the evaluation protocol](memory-agent-evaluation-protocol.md) and the evidence under `experiments/memory_repair_evidence/`.

# AutoJudge consistency v4 — partial run

## Goal

Evaluate temporal and semantic consistency of retrieval outputs while separating:

- consistency evaluation;
- reference-evidence presence;
- answer inferability.

The consistency judge is blinded to benchmark reference evidence and retrieval-policy identity.

## Setup

- Benchmark subset: 27 selected HaluMem-Medium Memory Conflict error cases.
- Retrieval policies: 5.
- Total contexts: 135.
- Judge: `typesafe/jev-1.14`.
- Two independent judge calls per context:
  1. consistency:
     - consistency_status;
     - conflict_type;
     - out_of_slice_evidence;
  2. evidence/inference:
     - reference_evidence_present;
     - answer_inferable.

## Current status

Completed contexts: 79 / 135.

The run stopped on:

`halumem-memory-conflict-016__transition_aware`

because the OpenRouter API returned:

`HTTP 402 Payment Required / Insufficient credits`.

The partial results are preserved and must not be interpreted as the final benchmark-wide semantic comparison because the run ended according to case order rather than random or stratified sampling.

## Files

- Evaluator:
  `experiments/autojudge/imca_jev_consistency_full_v4.py`
- Partial results:
  `results/autojudge_consistency_full_jev_v4.json`

## Interpretation boundary

The 79 completed contexts may be used for debugging and qualitative inspection, but the main policy-level semantic conclusions should rely on either:

- a completed run with the same judge;
- or a separately validated free-model evaluation protocol.

Results produced by another judge must not be merged directly with this Jev run as if they were one homogeneous evaluation.

# Contrastive Retrieval Interpretability

## Research question

**RQ:** Can contrastive score decomposition explain ranking failures that are not recoverable through signal ablation?

## Motivation

IMCA already records per-signal ranking contributions and supports replay with ranking signals disabled. This makes retrieval behavior inspectable, but ablation answers a counterfactual question:

> What changes if one or more signals are removed?

That is useful for sensitivity analysis, but it does not directly explain why one candidate outranked another in the observed run.

This work adds a complementary contrastive explanation:

> Which retrieval signals account for the score margin between two candidates?

## Method

For two candidates from the same retrieval run, the contrastive certificate decomposes their pairwise score margin across the retrieval signals already recorded by IMCA:

- `structural_order`
- `bm25`
- `edge_frequency`
- `graph_degree`
- `id_overlap`

For candidates \(A\) and \(B\), the certificate reconstructs:

\[
score(A) - score(B)
\]

as the sum of the corresponding per-signal contribution differences.

An **exact contrastive certificate** is one where the reconstructed margin matches the observed score margin within numerical tolerance.

The certificate itself is label-free: it only requires two candidate IDs from an existing retrieval trace.

`boundary_certificate` applies the same analysis at the selection boundary, for example rank 5 versus rank 6, without using benchmark labels.

Gold targets are used only during benchmark evaluation to identify ranking-loss cases.

## Evaluation protocol

The evaluation uses the existing 425-task code benchmark and the same historical recorded retrieval inputs used by the IMCA reproduction pipeline.

A target is classified as:

- `retrieved` if it appears within the required top-k;
- `candidate_missing` if it never enters the candidate set;
- `ranking_loss` if it is present in the candidate set but ranked below the required cutoff.

For each ranking-loss target, the evaluation measures three different properties:

1. whether removing a single active signal recovers the target;
2. whether removing any subset of active signals recovers the target;
3. whether the observed target-versus-boundary score margin has an exact contrastive decomposition.

These are intentionally different diagnostics. Ablation measures outcome sensitivity; contrastive decomposition measures explanatory fidelity to the observed ranking.

## Results

At target level:

| Measure | Result |
| --- | ---: |
| Retrieved targets | 442 |
| Candidate-missing targets | 195 |
| Ranking-loss targets | 187 |
| Recovered by single-signal ablation | 27 / 187 (14.4%) |
| Recovered by any subset ablation | 56 / 187 (29.9%) |
| Exact contrastive certificates | 180 / 187 (96.3%) |
| Exact certificates on subset-ablation-resistant targets | 124 |

The main observation is not that contrastive decomposition "beats" ablation on the same metric. The two mechanisms answer different questions.

Instead, the result shows that many ranking losses remain unchanged under signal-removal interventions, while their observed pairwise ranking margin can still be explained exactly from the original retrieval trace.

In particular, 124 ranking-loss targets that are not recovered by any tested subset ablation still receive exact contrastive certificates.

The remaining 7 ranking-loss targets do not expose the per-signal decomposition required for exact reconstruction.

## Example

For `cross_module_sibling-007`, the target

```text
fastapi `fastapi.datastructures`/DefaultPlaceholder#__init__().
```

is ranked below the boundary candidate

```text
fastapi `fastapi.datastructures`/UploadFile#seek().
```

The observed pairwise score margin is:

```text
boundary - target = 0.134565
```

The certificate decomposes the margin as:

```text
bm25              +0.166667
structural_order  +0.015517
graph_degree      -0.047619
----------------------------
total             +0.134565
```

BM25 and structural order favor the boundary candidate, while graph degree favors the target. Their contributions reconstruct the observed margin exactly.

This provides a more specific explanation than saying that a signal is globally important or that removing a signal changes the final top-k.

## Interpretation

Signal ablation remains useful for counterfactual sensitivity analysis. It can show whether an outcome changes when a retrieval channel is removed.

Contrastive certificates answer a different diagnostic question: why did one candidate outrank another in the run that actually occurred?

This makes the two mechanisms complementary:

- ablation studies intervention sensitivity;
- contrastive decomposition explains the observed ranking margin.

The current result is therefore an evaluation of **explanatory coverage and faithfulness inside IMCA**, not a claim of causal responsibility for individual retrieval errors.

## Limitations

The benchmark evaluation uses gold targets to select ranking-loss examples. The certificate itself does not require gold labels.

Candidate-generation failures are outside the scope of pairwise ranking certificates because the missing target is not present in the candidate set.

Fallback routes without per-signal score decomposition cannot currently produce exact certificates.

The current evaluation measures whether the numerical ranking explanation is faithful to the recorded scoring process. It does not yet measure whether developers find the explanation useful or faster to interpret.

## Implementation

The implementation introduces:

```text
python/contrastive_inspection.py
```

with:

- `contrastive_certificate(run, higher_id, lower_id)`
- `boundary_certificate(run, limit=5)`

The benchmark evaluation is implemented in:

```text
experiments/evaluate_contrastive_interpretability.py
```

Tests are provided in:

```text
python/test_contrastive_inspection.py
```

## Reproduction

Run:

```bash
uv run python experiments/evaluate_contrastive_interpretability.py
uv run pytest
```

The evaluation writes:

```text
outputs/contrastive_interpretability_eval.json
```

The full test suite currently passes with 63 tests.

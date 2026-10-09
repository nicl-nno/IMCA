# Continuous one-signal weight interval audit

## Purpose and scope

This experiment extends the fixed-grid ranking-recoverability audit to a continuous multiplier range. It asks whether a ranking-loss target can be returned to its required result cutoff by changing the weight of exactly one existing ranking signal.

The evaluation uses the frozen LongMemCode reference run containing 425 tasks. There are 187 ranking-loss task-target pairs across 72 tasks: the explicit benchmark target is present in the candidate set, but its reference rank is below the task's required cutoff. These are task-target pairs, not 187 distinct symbols. A symbol occurring in two tasks counts twice.

The analysis concerns ranking only. It does not repair candidate generation, evaluate the quality of contrastive explanations, or select a deployable weighting policy. Benchmark labels identify the targets and assess interventions after reranking; the reported reachability counts are therefore diagnostic oracle results, not contrastive-method performance claims.

## Frozen intervention

For each task, consider each originally nonzero signal among `structural_order`, `bm25`, `edge_frequency`, `graph_degree`, and `id_overlap`. Multiply that signal's stored score contribution by a scalar `alpha` in the closed interval `[0, 4]`. A multiplier of 1 reproduces the baseline; 0 removes that signal's contribution.

Keep the candidate set, per-signal ranks, all other signal weights and contributions, and the original corpus-order tie-breaking unchanged. Reuse the recorded dense ordering rather than recomputing embeddings. The required cutoff is 1 for an exact-symbol task, the declared `k` for an in-top-k task, and 5 otherwise; this implementation supports cutoffs from 1 to 5.

Seven ranking-loss pairs use fallback routes without per-signal contributions. The intervention is undefined for those pairs. They remain in the original 187-pair scope and are reported separately; 180 pairs are analyzable. Undefined fallback cases must not be interpreted as proofs of non-reachability.

## Analytical procedure

For candidate `c` and the selected signal, let `B_c` be the baseline score reconstructed by the actual floating-point replay sum, and let `m_c` be the stored contribution of that signal. Define the analytical score line:

```text
S_c(alpha) = B_c + (alpha - 1) * m_c
```

Convert the binary floating-point values `B_c` and `m_c` to exact rational numbers before solving intersections. For target `t` and another candidate `d`, a nonparallel pair has the threshold:

```text
alpha* = 1 + (B_d - B_t) / (m_t - m_d)
```

Solve every target-versus-candidate equality. Keep all distinct thresholds in `[0, 4]`, add both domain endpoints, and report coincident lines separately. Evaluate one rational midpoint in every resulting open interval and evaluate every threshold and endpoint separately. Apply the original corpus-order tie-break at equality. The target rank is constant inside each such open interval.

Target-only boundaries do not imply that the full candidate order is constant. To assess task score and retention of other correct targets, use the union of boundaries between every explicit benchmark evidence target present in the candidate set and every other candidate. Evaluate the resulting task-level outcome intervals and points separately.

## Outcome definitions

- **Oracle reachability:** at least one signal and multiplier places the target at or above the task's required cutoff.
- **Post-hoc safe recovery:** the target is recovered, the benchmark task score does not decrease relative to the reference score, and no other originally retrieved explicit benchmark target moves beyond the required cutoff. Score comparison uses a tolerance of `1e-12`.
- **Individual task reachability:** each ranking-loss target has some successful intervention, possibly a different one for each target.
- **Joint task reachability:** one signal and one multiplier recover all ranking-loss targets of the task at once. Safe joint recovery additionally satisfies the post-hoc score and retention conditions.

Safety is evaluated after reranking using benchmark labels. It is not a label-free guarantee. Target-level oracle actions must not be combined as though they constituted one shared task-level intervention.

## Results of the recorded run

The fixed grid `{0, 0.25, 0.5, 2, 4}` reproduces the previous audit's counts exactly, including the 425-task scope, 187 ranking-loss pairs, 72 affected tasks, and seven fallback pairs.

| Outcome, counted as task-target pairs | Fixed grid | Continuous interval analysis |
| --- | ---: | ---: |
| Oracle-reachable targets | 30 | 32 |
| Targets with a post-hoc safe recovery | 18 | 22 |

All four counts refer to the same original 187-pair scope. The continuous analysis adds two reachable pairs and four pairs with a safe recovery. No target is reachable only at a mathematical tie point.

The two newly reachable pairs concern the same `Contact#` symbol in two different tasks. Decreasing `graph_degree` restores the target inside a narrow interval missed by the fixed grid. Two further pairs were already reachable on the grid, but their safe recovery options occur between grid points.

Of the 72 affected tasks, 53 have multiple ranking-loss targets. Twenty-seven tasks have at least one individually reachable target. All ranking-loss targets are individually reachable in three tasks; a joint intervention also exists in three tasks, and a post-hoc safe joint intervention exists in one task.

## Replay validation and numerical limitations

First, reconstruct all 425 reference top-5 results through the repository's replay implementation. The recorded run matches all 425.

Independently rerank modified routes through the actual replay function at all applicable fixed-grid points, at the baseline multiplier, and at selected representable open-interval witnesses. Compare both the top-5 list and the full candidate order with the analytical ranking at the same binary floating-point multiplier. Deduplicate checks by task, signal, and multiplier.

The recorded run contains 2,003 distinct replay checks: all 2,003 top-5 comparisons and all 2,003 full-order comparisons match, with zero mismatches. Actual replay witnesses reproduce the 32 reachable and 22 safely reachable target counts.

The rational score lines are anchored to the replay-equivalent floating-point baseline score at `alpha = 1`. They are not a proof that every possible floating-point reranking operation follows exact real arithmetic. Mathematical tie multipliers may not be representable as binary floats, and extremely narrow intervals may contain no representable multiplier. The JSON preserves exact rational thresholds and distinguishes analytical results from replay witnesses. The 2,003 checks validate selected interventions, not every real multiplier or every exact tie point.

## Reproduction

Run from the repository root with the project's frozen dependency environment. Required inputs are `data/code/tasks.json`, `documents.json`, `projection.json`, `recorded_dense_order.json`, the `data/code/source/` corpus, and `results/code_reference.json`. The script uses the repository's `CodeSearch`, `retrieval_inspection.replay`, `retrieval_inspection.evidence_ids`, and `code_metrics.score_expected` implementations.

If available, provide the previous generated `outputs/ranking_recoverability_audit.json` as the baseline audit. If that file is absent, the script checks the built-in expected baseline counts instead; it does not reconstruct the previous audit's complete JSON.

Use a separate output directory to preserve prior generated results:

```bash
uv run --frozen python experiments/audit_continuous_weight_intervals.py --output-dir outputs/continuous_weight_interval_reproduction --baseline-audit outputs/ranking_recoverability_audit.json
```

This writes `continuous_weight_interval_audit.json` with task-level and target-level records, exact thresholds, intervals, tie points, recovery witnesses, and replay comparisons, plus `continuous_weight_interval_summary.json` with aggregate counts, baseline comparison, and limitations. Existing inputs and previous output directories are not modified. Generated JSON files are not part of the research code commit.

Run the dedicated tests explicitly, then the standard project suite:

```bash
uv run --frozen python -m pytest -q experiments/test_audit_continuous_weight_intervals.py
uv run --frozen python -m pytest -q
```

The recorded implementation run passed 10 dedicated test cases and 63 tests in the standard suite. The dedicated tests cover simultaneous crossings, original tie-breaking, coincident lines, representable interval samples, modified-route replay, displacement of another retrieved target, missing fallback signals, and invalid multipliers. The standard suite does not collect the experiment tests by default, so its 63-test count must not be described as including the new tests.

## Interpretation and next step

The fixed grid misses some narrow recovery and safe-recovery regions, but extending the search to the continuous domain changes the target counts only from 30 to 32 and from 18 to 22. This measures the available one-signal interventions under frozen ranking conditions; it does not establish that an explanation method can choose them without labels.

A separate follow-up experiment should test whether contrastive explanations help select useful weight changes without using the desired answer to choose the intervention. Candidate-missing cases require a distinct candidate-generation analysis.

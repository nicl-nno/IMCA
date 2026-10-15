# Local boundary prediction: fixed-grid results

Protocol: [local-boundary-prediction-fixed-grid-v1](local-boundary-prediction-protocol.md).

Status: Valid diagnostic run on development data.

## Research question and experiment-grid cell

This experiment addresses plan-H2: does outranking the original cutoff candidate correctly predict recovery of a specified lost code element after changing one signal weight?

The local rule predicts recovery when the target outranks the candidate originally at the required cutoff. Actual recovery is determined independently by full-candidate replay: the target must enter the required top-k.

The completed cell is **local-versus-full recovery prediction / frozen LongMemCode FastAPI development data / fixed grid**.

## Scope and controls

| Quantity | Result |
| --- | ---: |
| Original tasks and reference top-5 matches | 425 / 425 |
| Ranking-loss task-target pairs | 187 |
| Tasks containing ranking-loss pairs | 72 |
| Eligible task-target pairs | 180 |
| Unsupported fallback pairs | 7 |
| Tasks containing eligible pairs | 65 |
| Unique task-signal-multiplier grid actions | 1,105 |
| Target-action comparisons reusing those actions | 3,270 |

The seven unsupported fallback pairs lack per-signal score decomposition and are excluded from prediction-error rates.

The tested multipliers were exactly `{0, 0.25, 0.5, 2, 4}`. Multiplier 1 was a separate control. Candidates, signal ranks, other contributions, recorded dense order, and original tie-breaking remained fixed.

All frozen baseline counts matched, including 442 originally retrieved pairs, 195 candidate-missing pairs, and 30 grid-reachable ranking-loss pairs. Baseline controls comprised 221 task-signal checks and 654 pair checks. There were zero baseline or grid mismatches in full ordering, top-5 ordering, or the relative ordering of the target and original boundary candidate.

## Main descriptive results

| Pair-level outcome on the declared grid | Count |
| --- | ---: |
| At least one false-positive recovery prediction | 71 / 180 |
| At least one false-negative recovery prediction | 10 / 180 |
| Both error types under different actions | 1 / 180 |
| At least one error of either type | 80 / 180 (44.4%) |

The union is `71 + 10 - 1 = 80`; the two error-type counts are not disjoint. The 44.4% figure is the fraction of eligible task-target pairs with an error under at least one tested action, not the fraction of all action predictions that are wrong.

At least one disagreement occurred in 39 of the 65 tasks with eligible pairs (60.0%). The equal-task average of within-task eligible-pair disagreement fractions was 40.6%; this is a different aggregation from the pair-level 44.4%. Unsupported tasks and pairs are not counted as correct negatives.

Across the 3,270 target-action comparisons, the confusion counts were 88 true positives, 111 false positives, 22 false negatives, and 3,049 true negatives. These counts are descriptive repeated-action diagnostics, not independent observations or an inferential sample size.

The local rule predicted at least one recovery for 82 pairs, while full replay found a recovery for 30 pairs. Their difference is not the number of false-positive pairs: predictions must be compared for the same action, and one pair can have multiple outcomes under different actions.

## Deterministically selected examples

Each example is the first witness of its error type in the protocol's deterministic ordering. Both use cutoff 5.

| Case | Intervention | Target rank, before to after | Original boundary candidate, rank before to after | Local prediction | Actual recovery |
| --- | --- | --- | --- | --- | --- |
| `call_site_enumeration-000`, `serialize_response()` | Disable `graph_degree` | 11 to 7 | `APIRouter.post()`, 5 to 23 | Yes | No |
| `callers_of_symbol-014`, `Cookie()` | Disable `graph_degree` | 6 to 5 | `Query()`, 5 to 2 | No | Yes |

In the first case, the target overtakes the original boundary candidate but remains outside top-5. In the second case, the target reaches top-5 without overtaking the original boundary candidate. Thus the tested pairwise criterion is neither sufficient nor necessary for top-5 recovery on these examples.

## Interpretation and limits

The result supports plan-H2 for the tested local rule on this dataset and grid. The comparison's failure is not caused by numerical disagreement in the recorded pairwise score calculation: the relative pair ordering is reproduced correctly, while membership in the cutoff also depends on other candidates.

This does not imply that contrastive score decompositions are numerically wrong, or that every local explanation method fails at this rate. It evaluates one explicitly defined recovery predictor, not the quality or usefulness of all contrastive explanations.

No action was selected as a recommendation and no safety score was evaluated. The run does not establish H4, developer usability, or improvement in downstream agent answers. It does not describe every real multiplier in `[0, 4]`, and the original inspected development data are not an independent test set. Related targets, tasks, and repeated code elements can be dependent; no population-wide significance claim is made.

## Traceability and next steps

Base repository revision: `5a6f6c0291de846e70d04980115046fb9739ca38`, branch `liza/interpretability-baseline`, Python 3.13.15. The executed audit script and inputs are identified separately by SHA-256 hashes in the full audit JSON.

Reproduction command (use a new output directory):

```bash
uv run --frozen python experiments/audit_local_boundary_prediction.py --output-dir outputs/local_boundary_prediction_run
```

Outputs: `local_boundary_prediction_audit.json` and `local_boundary_prediction_summary.json`. The command uses an example output directory; each repeat requires a new directory because existing outputs are not overwritten.

Dedicated experiment tests passed 25 tests and 7 subtests in WSL. The standard project suite separately passed 63 tests and does not collect the dedicated experiment tests by default. Test commands are listed in the protocol.

Next steps are separately specified H2 evaluations of intermediate multipliers and new data. H4 requires a separate one-action selection comparison with matched action sets and post-hoc safety evaluation.

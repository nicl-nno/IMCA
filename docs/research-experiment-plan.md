# IMCA retrieval interpretability: hypotheses and experiment plan

Status: Working research plan, not a frozen execution protocol. Completed analyses and proposed experiments are distinguished below. The scope is retrieval interpretability, not the entire IMCA research programme.

## 1. Research question

The starting question is whether contrastive score decomposition can explain ranking failures that are not recoverable through signal ablation. The action-selection follow-up is:

**Can recorded retrieval-signal contributions provide faithful explanations of ranking failures and support the selection of a single-signal weight change that recovers a specified missing result without degrading other correct results?**

An explanation compares a required code element, such as a function, method, or class, with competing candidates. Explanatory fidelity, existence of a feasible intervention, and success of a selected intervention are separate outcomes. None alone establishes developer usability or downstream code-agent task success.

## 2. Scope and controls

The existing development data are the frozen FastAPI subset of LongMemCode: 425 tasks and 187 ranking-loss task-target pairs across 72 tasks. A ranking-loss target is present in the candidate set but outside its task-specific result cutoff. These are not 187 distinct code elements or independent observations.

The feasibility intervention changes one originally active signal weight by a multiplier in `[0, 4]`. Candidates, per-signal ranks, other weights, recorded dense order, and corpus-order tie-breaking remain fixed. The fixed-grid reference uses `{0, 0.25, 0.5, 2, 4}`. The primary H4 comparison uses this same finite grid for both information conditions; continuous-domain policy performance is a separate secondary experiment.

Seven pairs use fallback routes without per-signal score decomposition. Overall coverage includes these unsupported pairs, with eligible-only results reported separately for the other 180 pairs. Unsupported status is not proof of infeasibility. Candidate-missing failures are a separate stage and cannot be repaired while the candidate set is fixed.

The existing 425 tasks have already informed development. A later split of these inspected data must not be presented as an untouched test set.

## 3. Hypotheses, tests, and present status

### H1. Explanatory coverage beyond ablation recovery

There are ranking-loss targets for which no tested subset ablation restores the target, but the recorded target-versus-boundary score margin still admits an exact contrastive decomposition.

Test: Cross-tabulate recovery under ablation and numerical fidelity of the contrastive explanation on the same original target population. The criterion is a nonempty set of ablation-resistant targets with faithful decompositions; report its size and unsupported cases.

Status: Retrospective evidence exists. Single-signal ablation recovered 27 pairs, subset ablation recovered 56, exact certificates were obtained for 180, and 124 pairs had exact certificates without recovery under any tested subset ablation. This supports explanatory coverage, not semantic causal attribution or superior repair performance. Exactness of a recorded additive decomposition is expected and is not itself a novel empirical advantage.

### H2. The original boundary candidate is insufficient for recovery prediction

For some tasks and allowed multipliers, outranking the original cutoff candidate does not correctly determine whether the target enters the required top-k, because other candidates also change position.

Test: Define the local predictor as the target outranking the original cutoff candidate, including the original tie-break. Compare that prediction with full-candidate ranking over target-versus-candidate intervals and representable boundary checks. Use controlled counterexamples and the eligible benchmark traces.

Metrics: Number and fraction of eligible task-target pairs with at least one replay-confirmed false-positive or false-negative prediction; unsupported coverage. Specify a common witness-generation rule before testing and report ties separately. Do not count interval samples as independent observations or report sample-level error rates without a common sampling denominator. Synthetic counterexamples establish non-sufficiency in general, while benchmark counts measure its relevance to these data. Full-model versus floating-point replay discrepancies belong to numerical control C0 and must be distinguished from local-predictor errors.

Status: The first fixed-grid stage completed under protocol `local-boundary-prediction-fixed-grid-v1`. Replay-confirmed disagreements occurred in 80 of 180 eligible pairs (44.4%): 71 pairs had at least one false positive, 10 at least one false negative, and one had both. Disagreements affected 39 of 65 eligible tasks. All reference and numerical controls passed. This supports the tested local rule's insufficiency on the frozen grid; intermediate multiplier regimes, new data, and H4 one-action selection remain untested. An exact original pairwise margin does not itself test recovery prediction.

### H3. Continuous search can expose opportunities missed by the fixed grid

Some recovery or safe-recovery regions lie between the five fixed multipliers.

Test: Compare feasibility in `[0, 4]` with the fixed grid under identical frozen conditions. The criterion is a strictly positive count of additional reachable or safely reachable pairs, with actual replay witnesses.

Status: Retrospective evidence exists on the original data: 30 versus 32 reachable pairs and 18 versus 22 safely reachable pairs. All 32 and 22 counts have replay witnesses. This is an oracle feasibility finding, not prospective evidence or one-action method performance. Replication on new data remains planned.

### H4. Full-candidate information improves conditional one-action selection

A predeclared policy using all candidate scores selects a safe recovery more often than a policy using only the target-versus-original-boundary comparison, when both choose from the same finite intervention set. This tests the algorithmic value of broader diagnostic information, not developer comprehension or the persuasiveness of an explanation format.

Test: Each policy returns exactly one action or an explicit abstention for each original task-target pair. Apply the selected action through actual replay and evaluate recovery and safety afterward. The primary comparison is full-candidate versus local-pair prediction on the shared fixed grid, with a common action-selection rule. Contribution-only, single-signal-ablation, and continuous-domain policies are secondary references; they do not all use the same effective search procedure.

Primary metric: Task-macro Safe Recovery@1, defined in Section 6. Secondary metrics: Target-micro Safe Recovery@1 and Recovery@1, displacement of previously retrieved correct targets, and computational cost. A positive paired task-macro difference is the proposed effect; a 95% confidence interval wholly above zero on genuinely new data is the proposed confirmatory criterion. An interval spanning zero is inconclusive, not proof of equality. A minimum practically meaningful effect and the test-set sampling and size must be fixed before the confirmatory run, using development or pilot evidence rather than new test outcomes.

Status: Not tested. This is the main prospective comparison. The current audit finds safe feasibility for 18 original pairs on the shared grid and 22 in the continuous analytical domain, with replay witnesses. These are target-level oracle counts under the stated frozen conditions, not task-macro method scores or universal recovery bounds. The limited number of feasible safe outcomes motivates a sample-size and uncertainty assessment before a confirmatory study.

## 4. Experiment grid

| Experiment block | Existing development data | New tasks or repositories |
| --- | --- | --- |
| Observed score-margin explanation, H1 | Completed descriptive study: 180 exact certificates, including 124 subset-ablation-resistant pairs | Replication planned |
| Local versus full recovery prediction, H2 | Fixed-grid stage completed: disagreements in 80/180 eligible pairs and 39/65 eligible tasks; intermediate regimes pending | Replication planned |
| One-signal oracle feasibility, H3 | Completed: fixed grid 30/18; continuous domain 32/22 | Replication planned |
| One selected action on a shared grid, H4 | Matched-action-set policy comparison pending | Main confirmatory comparison after policy and sampling freeze |
| Selected action with continuous search | Secondary coverage/cost study pending; not an isolated explanation-format comparison | Secondary replication planned |
| Candidate-generation diagnosis | 195 candidate-missing pairs identified; no corresponding repair method evaluated | Separate future study |

The continuous-interval audit belongs to the **one-signal oracle-feasibility / existing-development-data** cell. Its replay checks also contribute to correctness control C0; it did not itself test H2 or H4. The separate fixed-grid run adds the **H2 fixed-grid prediction / existing-development-data** result. It does not complete continuous-regime H2 evaluation or H4.

## 5. Comparison protocol for H4

All policies use the same underlying trace, the identifier of the specified lost target, and the cutoff. This is target-informed conditional diagnosis of a known missing result, not fully label-free diagnosis or autonomous retrieval without a supplied target. Other benchmark relevance labels and post-intervention benchmark scores are unavailable during selection.

For the primary comparison, both conditions may choose any originally active signal and any multiplier in `{0, 0.25, 0.5, 2, 4}`. The local condition computes only the target-versus-original-boundary ordering for each action; the full condition predicts the target's actual cutoff membership using all candidate scores. Neither condition is restricted to multiplier zero. Both use the same candidate-action list and action tie-breaks. Their numerical computation costs can still differ and must be measured.

The proposed policy set is:

| Policy | Proposed selection rule |
| --- | --- |
| No intervention | Keep the original ranking as a reference. |
| Raw-contribution heuristic | Disable the active signal with the largest contribution to the original boundary candidate; use fixed signal order for ties. |
| Local contrastive, primary | Evaluate the target-versus-original-boundary ordering at each shared-grid action and select one predicted-success action. |
| Single-signal ablation | Replay each active signal at multiplier zero and choose one target-recovering action, if any. |
| Fixed-grid replay search, control | Replay the shared-grid actions and select according to the same target-success and tie-break rule; this checks the full-candidate predictor. |
| Full-candidate prediction, primary | Predict target cutoff membership at each shared-grid action using all candidate scores, without other relevance labels. |
| Full-candidate interval diagnosis, secondary | Derive target recovery regions without other relevance labels and choose one predeclared representable action in the continuous domain. |

For the primary comparison, a predicted-success action is selected by smallest `abs(alpha - 1)`, then fixed signal order `structural_order`, `bm25`, `edge_frequency`, `graph_degree`, `id_overlap`, then alpha. If no action is predicted successful, the policy abstains. The local and full conditions and the replay control use this identical rule. The rule is proposed, not yet implemented or validated, and requires versioning and freezing before the comparative run.

Full-candidate prediction and exhaustive replay on the same grid with the same selection rule should choose the same action when reconstruction is correct. That agreement is an implementation control, not evidence that analytical diagnosis outperforms replay search. Their costs may differ.

For the secondary continuous experiment, finalize and version the witness construction and abstention rule before running. Smallest change over an open real interval need not be attained, so do not leave the rule as an unspecified continuous minimization. Define a finite set of representable interior or boundary-neighbor actions, preserve exact interval records, and distinguish an exact mathematical tie from its floating-point neighbors. Do not round mathematical endpoints silently.

The full diagnostic selector must have a separate label-restricted code path. Do not select from the current audit's `best_safe_witness` or label-derived benchmark-outcome partitions: those are oracle audit outputs. Construct selection candidates from permitted trace information, and use full benchmark labels only in the evaluator.

Methods have different search procedures and costs. Report candidate comparisons, replay evaluations, and elapsed time. Do not claim equal-cost comparison or attribute an observed advantage solely to explanation format when search coverage also differs. Subset ablation is historical context, not a primary comparator under the one-signal constraint, because it can remove multiple signals.

## 6. Evaluation and correctness controls

- Target-micro Recovery@1: fraction of original pairs whose single selected action places the target within its cutoff. Abstentions are not recoveries.
- A safe recovery requires recovery with no benchmark-score regression and no loss of another originally retrieved explicit required target. Safety is assessed post hoc; retain the score tolerance of `1e-12`.
- For task-macro Safe Recovery@1, compute the safe-recovery fraction within each affected task using all its original ranking-loss targets, then average those fractions with equal task weights. This is the primary H4 endpoint; target-micro safe-recovery counts and rates are secondary.
- Report the original 187-pair and 72-task population, eligible-only results, and unsupported coverage. Unsupported policies abstain; this counts as no recovery for the overall pipeline metric, not as proof of infeasibility. Do not restrict the primary comparison to oracle-reachable pairs.
- Use paired task-cluster bootstrap intervals, resampling tasks with all their targets and both methods together. Do not bootstrap the 2,003 numerical checks as independent data. Report results by query operation, initial target rank, and target multiplicity. Task clustering addresses within-task dependence, not all dependence between related tasks or repositories; report per-repository results on new data and define any additional clustering before analysis.
- Individual per-target actions are not a joint task repair. Evaluate a common task-level action separately before making joint-recovery claims.
- Correctness control C0: reproduce all 425 reference top-5 lists; check controlled crossings, simultaneous ties, coincident lines, zero contributions, and negative cases. The existing 2,003 replay comparisons match top-5 and full order, but do not validate every real multiplier or every exact mathematical tie. Rational lines are anchored to replay-equivalent floating-point baseline scores.
- Additional domain sensitivity checks `[0, 2]` and `[0, 8]` are planned, not completed. The current audit is hard-coded to `[0, 4]`; sensitivity runs require a separately versioned parameterization or implementation change and renewed numerical validation.

## 7. Execution order and deliverables

1. Finalize the hypothesis scope, matched-action primary comparison, primary task-macro endpoint, and minimum practically meaningful effect. H1 and H3 are retrospective findings; H2 extension and replication and the H4 comparison remain prospective.
2. Freeze the policy definitions and label-access contract; the H2 fixed-grid stage is complete, while intermediate-regime comparisons and additional controls require separately specified follow-ups.
3. Implement separate selectors and a shared evaluator; run the original data as an explicitly exploratory development comparison. Preserve all original pairs and negative cases.
4. Use development or pilot results to assess feasibility and required sample size, then freeze code, policies, sampling, and analysis before evaluating genuinely new tasks or repositories. Do not claim held-out validation from the already inspected original set. Report inconclusive comparisons honestly if safe outcomes are too sparse.
5. Record each experiment's grid cell, hypothesis, dataset, policy revision, input hashes, commands, selected actions, raw outcomes, summary metrics, uncertainty, and limitations. Keep generated outputs separate from immutable inputs and prior results.
6. Design candidate-generation diagnosis as a separate study.

## Existing evidence

- [Published contrastive explanation study](https://github.com/nicl-nno/IMCA/blob/liza/interpretability-baseline/docs/contrastive-interpretability.md)
- [Published continuous weight interval audit](https://github.com/nicl-nno/IMCA/blob/5a6f6c0291de846e70d04980115046fb9739ca38/docs/continuous-weight-interval-protocol-amendment.md)

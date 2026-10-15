# Local boundary prediction: fixed-grid protocol

Protocol ID: `local-boundary-prediction-fixed-grid-v1`.

Status: Pre-run specification for the fixed-grid H2 diagnostic experiment on development data. Results are reported separately.

## Research question and grid cell

The retrieval-interpretability strand asks whether recorded signal contributions can explain ranking failures and support useful ranking interventions. This experiment addresses plan-H2: can comparing a lost target only with the original cutoff candidate correctly determine whether the target is recovered after a weight change?

Its experiment-grid cell is **local-versus-full recovery prediction / original frozen development data / fixed multipliers**. It is distinct from the continuous-domain feasibility audit and the H4 one-action policy comparison.

## Frozen data and intervention

Use all 425 original LongMemCode FastAPI tasks and their recorded dense order. Identify ranking-loss task-target pairs using the frozen repository replay and explicit benchmark evidence. Expected scope: 187 pairs across 72 tasks, of which 180 expose scored signals and seven are unsupported fallback pairs. Repeated code elements in different tasks count as different pairs; multiple targets in one task are not independent observations.

For every originally active signal among `structural_order`, `bm25`, `edge_frequency`, `graph_degree`, and `id_overlap`, test exactly `{0, 0.25, 0.5, 2, 4}`. Multiply only that signal's stored contribution and weight. Keep all candidates, per-signal ranks, other contributions, recorded dense input, and original tie-breaking unchanged. Multiplier 1 is a separate baseline control, not an additional point in the primary grid.

The cutoff is 1 for an exact-symbol task, the specified `k` for an in-top-k task, and 5 otherwise. Supported cutoffs are 1 through 5.

## Local prediction and actual reference

For each task, fix the identity of the candidate at the required cutoff in the original baseline ordering. Do not replace this identity with the new boundary candidate after an intervention.

The local predictor declares recovery if the target outranks this original boundary candidate after the intervention. Compute the two candidates' scores from stored contributions with ordinary floating-point arithmetic in the original summation order. Apply corpus-order tie-breaking and stable original candidate order if needed.

Independently apply the intervention to a copied route and call the repository's actual `retrieval_inspection.replay`. Actual recovery means the target's new rank is within the required cutoff.

- False positive: the local predictor declares recovery, but actual rank remains beyond the cutoff.
- False negative: the local predictor declares no recovery, but actual rank is within the cutoff.
- A pair may exhibit both error types under different actions. Do not add the pair counts as though they were disjoint, or derive them by subtracting aggregate reachability counts.

All methods are target-informed: benchmark labels identify the lost element. This experiment evaluates recovery prediction, not action selection or safety.

## Metrics and interpretation

Primary descriptive results are the number and fraction of eligible task-target pairs with at least one replay-confirmed false positive, false negative, or either disagreement on the declared grid. Report the seven unsupported cases separately, without treating their predictions as correct negatives or proofs of infeasibility.

Also report affected-task counts, task-level records, and the equal-task average of each eligible task's within-task eligible-pair disagreement fraction. Tasks with no eligible pairs have undefined disagreement fractions and are excluded from that eligible-only average, with their coverage reported explicitly.

Action-level confusion counts are secondary diagnostic counts, not independent observations or an inferential sample size. Do not bootstrap action checks as independent data. This first run makes no population-wide significance or new-repository generalization claim.

A replay-confirmed counterexample establishes that the local criterion is not universally sufficient on these data. No grid counterexample does not establish correctness for every multiplier in `[0, 4]`; interval analysis remains a separate follow-up. Report whichever outcome occurs without changing the grid after inspecting results.

Examples are selected deterministically: at most one witness per task-target pair per error type, ordered by task ID, target ID, fixed signal order, and multiplier; show the first five distinct pairs per type. All action records remain available in JSON.

## Numerical and baseline controls

Reproduce all 425 reference top-5 lists before interpreting the new comparison. Check full candidate order and top-5 reconstruction on every unique grid task-signal action and at multiplier 1. For each target-action comparison, check that the locally computed pair ordering matches the two candidates' relative ordering in actual replay. This separates local-cutoff prediction failures from score or tie-breaking implementation failures.

Expected frozen baseline controls are 442 retrieved pairs, 195 candidate-missing pairs, 187 ranking-loss pairs, 72 affected tasks, 180 eligible pairs, seven unsupported pairs, 30 grid-reachable pairs, and 1,105 unique grid task-signal actions. The main program marks the report invalid and exits nonzero if these counts drift or numerical checks fail. An invalid report is diagnostic output, not a valid H2 result.

Grid replay is shared across all lost targets of a task. Each unique task-signal-multiplier action is counted once, even when reused for multiple targets. Multiplier-1 baseline checks are counted separately from grid actions.

## Implementation and reproduction

Implementation and tests:

- `experiments/audit_local_boundary_prediction.py`
- `experiments/test_audit_local_boundary_prediction.py`

The audit uses the repository's retrieval implementation for the replay reference.

Run the dedicated tests from the repository root:

```bash
uv run --frozen python -m pytest -q experiments/test_audit_local_boundary_prediction.py
```

Run the audit into a new output directory:

```bash
uv run --frozen python experiments/audit_local_boundary_prediction.py --output-dir outputs/local_boundary_prediction_run
```

Then run the standard project suite:

```bash
uv run --frozen python -m pytest -q
```

The audit requires a new output directory and does not overwrite previous results. It writes `local_boundary_prediction_audit.json` with task, target, action, example, and SHA-256 provenance records, and `local_boundary_prediction_summary.json` with the compact report. Run metadata records the base Git HEAD, Python version, and input and implementation hashes.

Synthetic tests demonstrate mechanisms and validate implementation only; they do not measure error frequency on LongMemCode.

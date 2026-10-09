from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = ("structural_order", "bm25", "edge_frequency", "graph_degree", "id_overlap")
FIXED_GRID = (0.0, 0.25, 0.5, 2.0, 4.0)
ALPHA_MIN = Fraction(0, 1)
ALPHA_MAX = Fraction(4, 1)
EPS = 1e-12
EXPECTED_BASELINE = {
    "total_tasks": 425,
    "ranking_loss_targets": 187,
    "distinct_tasks_with_ranking_loss": 72,
    "ranking_loss_targets_without_scored_signals": 7,
    "ranking_loss_targets_recovered_any": 30,
    "ranking_loss_targets_recovered_safe": 18,
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def cutoff(expected):
    kind = expected.get("kind")
    if kind == "exact_symbol":
        return 1
    if kind == "in_top_k":
        return int(expected.get("k", 5))
    return 5


def active_signals(candidates):
    return [
        name for name in CHANNELS
        if any(row.get("signals", {}).get(name, {}).get("weight", 0.0) != 0 for row in candidates)
    ]


def as_fraction(value):
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value, 1)
    return Fraction.from_float(float(value))


def alpha_record(value):
    value = as_fraction(value)
    with localcontext() as context:
        context.prec = 30
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return {
        "value": float(value),
        "exact": f"{value.numerator}/{value.denominator}",
        "decimal": format(decimal, ".24g"),
    }


def candidate_lines(candidates, signal):
    if signal not in CHANNELS:
        raise ValueError("invalid signal")
    lines = {}
    for candidate in candidates:
        signals = candidate.get("signals", {})
        slope = as_fraction(signals.get(signal, {}).get("contribution", 0.0))
        baseline_score = sum(value.get("contribution", 0.0) for value in signals.values())
        intercept = as_fraction(baseline_score) - slope
        lines[candidate["id"]] = (intercept, slope)
    return lines


def rank_from_lines(candidates, lines, alpha):
    alpha = as_fraction(alpha)
    rows = []
    for candidate in candidates:
        intercept, slope = lines[candidate["id"]]
        rows.append((candidate["id"], intercept + slope * alpha, candidate["corpus_order"]))
    rows.sort(key=lambda row: (-row[1], row[2]))
    ids = [row[0] for row in rows]
    return {
        "ids": ids,
        "top5": ids[:5],
        "ranks": {candidate_id: position for position, candidate_id in enumerate(ids, 1)},
    }


def pair_crossing(lines, first_id, second_id):
    first_intercept, first_slope = lines[first_id]
    second_intercept, second_slope = lines[second_id]
    slope_delta = first_slope - second_slope
    intercept_delta = second_intercept - first_intercept
    if slope_delta == 0:
        return "coincident" if intercept_delta == 0 else None
    return intercept_delta / slope_delta


def interval_sample(left, right):
    if not left < right:
        raise ValueError("empty interval")
    return (left + right) / 2


def representable_interval_sample(left, right):
    middle = interval_sample(left, right)
    value = float(middle)
    exact = Fraction.from_float(value)
    if left < exact < right:
        return value
    value = math.nextafter(float(left), float(right))
    exact = Fraction.from_float(value)
    if left < exact < right:
        return value
    value = math.nextafter(float(right), float(left))
    exact = Fraction.from_float(value)
    if left < exact < right:
        return value
    return None


def target_rank_analysis(candidates, target_id, signal, required_cutoff):
    lines = candidate_lines(candidates, signal)
    roots = defaultdict(list)
    coincident = []
    outside = 0
    for candidate in candidates:
        candidate_id = candidate["id"]
        if candidate_id == target_id:
            continue
        crossing = pair_crossing(lines, target_id, candidate_id)
        if crossing == "coincident":
            coincident.append(candidate_id)
        elif crossing is not None:
            if ALPHA_MIN <= crossing <= ALPHA_MAX:
                roots[crossing].append(candidate_id)
            else:
                outside += 1
    boundaries = sorted({ALPHA_MIN, ALPHA_MAX, *roots})
    internal_intervals = []
    intervals = []
    for left, right in zip(boundaries, boundaries[1:]):
        if left == right:
            continue
        sample = interval_sample(left, right)
        ranking = rank_from_lines(candidates, lines, sample)
        row = {
            "left": left,
            "right": right,
            "sample": sample,
            "target_rank": ranking["ranks"][target_id],
            "recovered": ranking["ranks"][target_id] <= required_cutoff,
        }
        internal_intervals.append(row)
        intervals.append({
            "left": alpha_record(left),
            "right": alpha_record(right),
            "sample": alpha_record(sample),
            "target_rank": row["target_rank"],
            "recovered": row["recovered"],
        })
    internal_points = []
    points = []
    for alpha in boundaries:
        ranking = rank_from_lines(candidates, lines, alpha)
        tied = sorted(roots.get(alpha, []))
        point_kind = "tie_threshold" if tied else "domain_endpoint"
        if tied and alpha in {ALPHA_MIN, ALPHA_MAX}:
            point_kind = "endpoint_and_tie_threshold"
        row = {
            "alpha": alpha,
            "target_rank": ranking["ranks"][target_id],
            "recovered": ranking["ranks"][target_id] <= required_cutoff,
            "tied_candidate_ids": tied,
            "point_kind": point_kind,
        }
        internal_points.append(row)
        points.append({
            "alpha": alpha_record(alpha),
            "point_kind": point_kind,
            "tied_candidate_ids": tied,
            "target_rank": row["target_rank"],
            "recovered": row["recovered"],
        })
    thresholds = []
    for alpha in sorted(roots):
        point = next(row for row in internal_points if row["alpha"] == alpha)
        left_interval = next((row for row in internal_intervals if row["right"] == alpha), None)
        right_interval = next((row for row in internal_intervals if row["left"] == alpha), None)
        thresholds.append({
            "alpha": alpha_record(alpha),
            "tied_candidate_ids": sorted(roots[alpha]),
            "target_rank_below": left_interval["target_rank"] if left_interval else None,
            "target_rank_at": point["target_rank"],
            "target_rank_above": right_interval["target_rank"] if right_interval else None,
        })
    return {
        "report": {
            "pair_count": max(len(candidates) - 1, 0),
            "distinct_in_domain_thresholds": len(roots),
            "pair_crossings_outside_domain": outside,
            "coincident_all_alpha_candidate_ids": sorted(coincident),
            "thresholds": thresholds,
            "constant_target_rank_open_intervals": intervals,
            "tie_and_endpoint_points": points,
            "reachable_on_open_interval": any(row["recovered"] for row in internal_intervals),
            "reachable_at_evaluated_point": any(row["recovered"] for row in internal_points),
        },
        "lines": lines,
        "intervals": internal_intervals,
        "points": internal_points,
    }


def benchmark_boundaries(candidates, lines, evidence_target_ids):
    candidate_ids = {candidate["id"] for candidate in candidates}
    boundaries = {ALPHA_MIN, ALPHA_MAX}
    for target_id in evidence_target_ids:
        if target_id not in candidate_ids:
            continue
        for candidate in candidates:
            candidate_id = candidate["id"]
            if candidate_id == target_id:
                continue
            crossing = pair_crossing(lines, target_id, candidate_id)
            if isinstance(crossing, Fraction) and ALPHA_MIN <= crossing <= ALPHA_MAX:
                boundaries.add(crossing)
    return sorted(boundaries)


def exact_state(candidates, lines, alpha, expected, evidence_target_ids, score_expected, kind, left=None, right=None):
    ranking = rank_from_lines(candidates, lines, alpha)
    score = float(score_expected(expected, ranking["top5"])["score"])
    return {
        "kind": kind,
        "alpha": alpha,
        "left": left,
        "right": right,
        "top5": ranking["top5"],
        "evidence_ranks": {target_id: ranking["ranks"].get(target_id) for target_id in evidence_target_ids},
        "score": score,
    }


def task_signal_states(candidates, signal, expected, evidence_target_ids, score_expected):
    lines = candidate_lines(candidates, signal)
    boundaries = benchmark_boundaries(candidates, lines, evidence_target_ids)
    states = []
    for left, right in zip(boundaries, boundaries[1:]):
        if left < right:
            states.append(exact_state(
                candidates, lines, interval_sample(left, right), expected, evidence_target_ids,
                score_expected, "open_interval", left, right,
            ))
    for alpha in boundaries:
        states.append(exact_state(
            candidates, lines, alpha, expected, evidence_target_ids, score_expected, "point",
        ))
    return {
        "lines": lines,
        "boundaries": boundaries,
        "states": states,
        "open_interval_count": max(len(boundaries) - 1, 0),
        "point_count": len(boundaries),
    }


def outcome(state, target_id, required_cutoff, originally_retrieved, baseline_score):
    rank = state["evidence_ranks"].get(target_id)
    recovered = rank is not None and rank <= required_cutoff
    lost = [
        candidate_id for candidate_id in originally_retrieved
        if candidate_id != target_id and (state["evidence_ranks"].get(candidate_id) or math.inf) > required_cutoff
    ]
    nonregressing = state["score"] >= baseline_score - EPS
    return {
        "recovered": recovered,
        "new_rank": rank,
        "benchmark_score": state["score"],
        "score_delta": state["score"] - baseline_score,
        "score_nonregressing": nonregressing,
        "other_originally_retrieved_targets_lost": lost,
        "safe_recovery": recovered and nonregressing and not lost,
    }


def state_witness(signal, state, action_outcome):
    result = {
        "signal": signal,
        "region_kind": state["kind"],
        "alpha": alpha_record(state["alpha"]),
        **action_outcome,
    }
    if state["kind"] == "open_interval":
        result["interval"] = {
            "left": alpha_record(state["left"]),
            "right": alpha_record(state["right"]),
        }
    return result


def witness_key(signal, state, action_outcome):
    return (
        -int(action_outcome["safe_recovery"]),
        -int(action_outcome["score_nonregressing"]),
        0 if state["kind"] == "open_interval" else 1,
        -action_outcome["score_delta"],
        action_outcome["new_rank"] if action_outcome["new_rank"] is not None else math.inf,
        CHANNELS.index(signal),
        abs(float(state["alpha"]) - 1.0),
    )


def replay_with_multiplier(route, signal, alpha, replay):
    if signal not in CHANNELS or not math.isfinite(alpha) or not 0 <= alpha <= 4:
        raise ValueError("invalid ranking intervention")
    candidates = []
    for candidate in route["candidates"]:
        signals = {}
        for name, value in candidate.get("signals", {}).items():
            changed = dict(value)
            if name == signal:
                changed["weight"] = changed.get("weight", 0.0) * alpha
                changed["contribution"] = changed.get("contribution", 0.0) * alpha
            signals[name] = changed
        candidates.append({**candidate, "signals": signals})
    return replay({**route, "candidates": candidates})


def actual_state(run, expected, evidence_target_ids, score_expected):
    ranks = {row["id"]: row["rank"] for row in run["candidates"]}
    return {
        "top5": run["top5"],
        "ids": [row["id"] for row in run["candidates"]],
        "evidence_ranks": {target_id: ranks.get(target_id) for target_id in evidence_target_ids},
        "score": float(score_expected(expected, run["top5"])["score"]),
    }


def validate_replay(route, candidates, signal, alpha, expected, evidence_target_ids, score_expected, replay):
    alpha_float = float(alpha)
    actual_run = replay_with_multiplier(route, signal, alpha_float, replay)
    actual = actual_state(actual_run, expected, evidence_target_ids, score_expected)
    lines = candidate_lines(candidates, signal)
    analytical = rank_from_lines(candidates, lines, Fraction.from_float(alpha_float))
    return {
        "alpha": alpha_float,
        "alpha_hex": alpha_float.hex(),
        "full_order_match": actual["ids"] == analytical["ids"],
        "top5_match": actual["top5"] == analytical["top5"],
        "actual": actual,
        "analytical": analytical,
    }


def target_validation_record(validation, target_id, required_cutoff, originally_retrieved, baseline_score, source):
    actual = validation["actual"]
    analytical = validation["analytical"]
    state = {
        "evidence_ranks": actual["evidence_ranks"],
        "score": actual["score"],
    }
    actual_outcome = outcome(state, target_id, required_cutoff, originally_retrieved, baseline_score)
    return {
        "source": source,
        "alpha": validation["alpha"],
        "alpha_hex": validation["alpha_hex"],
        "target_rank_match": actual["evidence_ranks"].get(target_id) == analytical["ranks"].get(target_id),
        "top5_match": validation["top5_match"],
        "full_order_match": validation["full_order_match"],
        "actual_outcome": actual_outcome,
    }


def best_actions(signal_states, target_id, required_cutoff, originally_retrieved, baseline_score):
    successful = []
    for signal, state in signal_states:
        action_outcome = outcome(state, target_id, required_cutoff, originally_retrieved, baseline_score)
        if action_outcome["recovered"]:
            successful.append((signal, state, action_outcome))
    successful.sort(key=lambda item: witness_key(*item))
    safe = [item for item in successful if item[2]["safe_recovery"]]
    nonregressing = [item for item in successful if item[2]["score_nonregressing"]]
    return {
        "successful": successful,
        "best": state_witness(*successful[0]) if successful else None,
        "best_safe": state_witness(*safe[0]) if safe else None,
        "recovered": bool(successful),
        "safe": bool(safe),
        "nonregressing": bool(nonregressing),
        "open_interval": any(item[1]["kind"] == "open_interval" for item in successful),
        "point": any(item[1]["kind"] == "point" for item in successful),
        "tie_only": bool(successful) and not any(item[1]["kind"] == "open_interval" for item in successful),
    }


def action_kind(alpha):
    if alpha == 0:
        return "disabled"
    return "decreased" if alpha < 1 else "increased"


def task_joint_outcome(state, ranking_loss_targets, required_cutoff, originally_retrieved, baseline_score):
    recovered = [
        target_id for target_id in ranking_loss_targets
        if (state["evidence_ranks"].get(target_id) or math.inf) <= required_cutoff
    ]
    lost = [
        target_id for target_id in originally_retrieved
        if (state["evidence_ranks"].get(target_id) or math.inf) > required_cutoff
    ]
    nonregressing = state["score"] >= baseline_score - EPS
    all_recovered = len(recovered) == len(ranking_loss_targets)
    return {
        "recovered_target_ids": recovered,
        "recovered_target_count": len(recovered),
        "all_ranking_loss_targets_recovered": all_recovered,
        "benchmark_score": state["score"],
        "score_delta": state["score"] - baseline_score,
        "score_nonregressing": nonregressing,
        "originally_retrieved_targets_lost": lost,
        "safe_joint_recovery": all_recovered and nonregressing and not lost,
    }


def joint_witness(signal, state, joint_outcome):
    result = {
        "signal": signal,
        "region_kind": state["kind"],
        "alpha": alpha_record(state["alpha"]),
        **joint_outcome,
    }
    if state["kind"] == "open_interval":
        result["interval"] = {
            "left": alpha_record(state["left"]),
            "right": alpha_record(state["right"]),
        }
    return result


def joint_key(signal, state, value):
    return (
        -int(value["safe_joint_recovery"]),
        -int(value["all_ranking_loss_targets_recovered"]),
        -value["recovered_target_count"],
        -int(value["score_nonregressing"]),
        0 if state["kind"] == "open_interval" else 1,
        -value["score_delta"],
        CHANNELS.index(signal),
        abs(float(state["alpha"]) - 1.0),
    )


def baseline_comparison(summary, baseline_summary):
    generated = {
        "total_tasks": summary["total_tasks"],
        "ranking_loss_targets": summary["ranking_loss_targets"],
        "distinct_tasks_with_ranking_loss": summary["distinct_tasks_with_ranking_loss"],
        "ranking_loss_targets_without_scored_signals": summary["ranking_loss_targets_without_scored_signals"],
        "ranking_loss_targets_recovered_any": summary["fixed_grid"]["target_reachable"],
        "ranking_loss_targets_recovered_safe": summary["fixed_grid"]["target_safe_reachable"],
    }
    expected = {key: baseline_summary.get(key) for key in EXPECTED_BASELINE}
    return {
        "expected": expected,
        "generated": generated,
        "matches": expected == generated,
    }


def summarize(target_rows, task_rows, stages, total_tasks, reference_matches, variant_keys, validation_rows):
    by_op = {}
    for op in sorted({row["query_op"] for row in target_rows}):
        group = [row for row in target_rows if row["query_op"] == op]
        by_op[op] = {
            "ranking_loss_targets": len(group),
            "distinct_tasks": len({row["task_id"] for row in group}),
            "fixed_grid_reachable": sum(row["fixed_grid"]["reachable"] for row in group),
            "fixed_grid_safe_reachable": sum(row["fixed_grid"]["safe_reachable"] for row in group),
            "continuous_oracle_reachable": sum(row["continuous_oracle"]["reachable"] for row in group),
            "continuous_oracle_safe_reachable": sum(row["continuous_oracle"]["safe_reachable"] for row in group),
        }
    continuous_by_signal = {
        signal: sum(
            any(item["signal"] == signal and item["reachable"] for item in row["signals"])
            for row in target_rows
        )
        for signal in CHANNELS
    }
    fixed_by_signal = {
        signal: sum(
            any(action["signal"] == signal for action in row["fixed_grid"]["successful_actions"])
            for row in target_rows
        )
        for signal in CHANNELS
    }
    fixed_reachable = sum(row["fixed_grid"]["reachable"] for row in target_rows)
    fixed_safe = sum(row["fixed_grid"]["safe_reachable"] for row in target_rows)
    continuous_reachable = sum(row["continuous_oracle"]["reachable"] for row in target_rows)
    continuous_safe = sum(row["continuous_oracle"]["safe_reachable"] for row in target_rows)
    replay_reachable = sum(row["continuous_oracle"]["replay_witnessed_reachable"] for row in target_rows)
    replay_safe = sum(row["continuous_oracle"]["replay_witnessed_safe_reachable"] for row in target_rows)
    return {
        "total_tasks": total_tasks,
        "reference_top5_matches": reference_matches,
        "target_stages": dict(stages),
        "ranking_loss_targets": len(target_rows),
        "distinct_tasks_with_ranking_loss": len(task_rows),
        "ranking_loss_targets_without_scored_signals": sum(not row["active_signals"] for row in target_rows),
        "ranking_loss_targets_with_scored_signals": sum(bool(row["active_signals"]) for row in target_rows),
        "fixed_grid": {
            "multipliers": list(FIXED_GRID),
            "target_reachable": fixed_reachable,
            "target_safe_reachable": fixed_safe,
            "target_not_reachable": len(target_rows) - fixed_reachable,
            "unique_task_signal_actions": len(variant_keys),
            "recoverable_by_signal_nonexclusive": fixed_by_signal,
        },
        "continuous_oracle": {
            "alpha_domain": [0.0, 4.0],
            "target_reachable": continuous_reachable,
            "target_safe_reachable": continuous_safe,
            "target_reachable_only_at_tie_point": sum(row["continuous_oracle"]["tie_only"] for row in target_rows),
            "target_replay_witnessed_reachable": replay_reachable,
            "target_replay_witnessed_safe_reachable": replay_safe,
            "continuous_only_vs_fixed_grid": sum(
                row["continuous_oracle"]["reachable"] and not row["fixed_grid"]["reachable"]
                for row in target_rows
            ),
            "continuous_safe_only_vs_fixed_grid": sum(
                row["continuous_oracle"]["safe_reachable"] and not row["fixed_grid"]["safe_reachable"]
                for row in target_rows
            ),
            "recoverable_by_signal_nonexclusive": continuous_by_signal,
        },
        "task_level": {
            "tasks_with_ranking_loss": len(task_rows),
            "tasks_with_multiple_ranking_loss_targets": sum(row["ranking_loss_target_count"] > 1 for row in task_rows),
            "tasks_with_any_individually_reachable_target": sum(row["continuous_oracle"]["any_target_individually_reachable"] for row in task_rows),
            "tasks_with_all_targets_individually_reachable": sum(row["continuous_oracle"]["all_targets_individually_reachable"] for row in task_rows),
            "tasks_with_joint_all_target_action": sum(row["continuous_oracle"]["joint_all_targets_reachable"] for row in task_rows),
            "tasks_with_safe_joint_all_target_action": sum(row["continuous_oracle"]["safe_joint_all_targets_reachable"] for row in task_rows),
        },
        "independent_replay_validation": {
            "unique_samples": len(validation_rows),
            "top5_matches": sum(row["top5_match"] for row in validation_rows),
            "full_order_matches": sum(row["full_order_match"] for row in validation_rows),
            "top5_mismatches": sum(not row["top5_match"] for row in validation_rows),
            "full_order_mismatches": sum(not row["full_order_match"] for row in validation_rows),
        },
        "by_query_op": by_op,
    }


def analyze(tasks, recorded, reference, engine, score_expected, evidence_ids, replay):
    target_rows = []
    task_rows = []
    stages = Counter()
    reference_matches = 0
    variant_keys = set()
    validation_rows = []
    validation_cache = {}

    for task in tasks:
        route = engine.route(task["query"], task["query_text"], dense_order=recorded.get(task["id"]))
        baseline = replay(route)
        if baseline["top5"] != reference.get(task["id"]):
            raise RuntimeError(f"reference ranking mismatch: {task['id']}")
        reference_matches += 1
        required_cutoff = cutoff(task["expected"])
        if not 1 <= required_cutoff <= 5:
            raise ValueError(f"unsupported cutoff for {task['id']}: {required_cutoff}")
        evidence_target_ids = list(dict.fromkeys(evidence_ids(task["expected"])))
        baseline_ranks = {row["id"]: row["rank"] for row in baseline["candidates"]}
        ranking_loss_targets = []
        for target_id in evidence_target_ids:
            rank = baseline_ranks.get(target_id)
            if rank is None:
                stages["candidate_missing"] += 1
            elif rank > required_cutoff:
                ranking_loss_targets.append(target_id)
                stages["ranking_loss"] += 1
            else:
                stages["retrieved"] += 1
        if not ranking_loss_targets:
            continue
        baseline_score = float(score_expected(task["expected"], baseline["top5"])["score"])
        originally_retrieved = [
            target_id for target_id in evidence_target_ids
            if (baseline_ranks.get(target_id) or math.inf) <= required_cutoff
        ]
        signals = [] if route.get("fallback") else active_signals(route["candidates"])
        inactive = [signal for signal in CHANNELS if signal not in signals]
        per_signal_states = {}
        per_signal_grid = {}

        for signal in signals:
            state_data = task_signal_states(
                route["candidates"], signal, task["expected"], evidence_target_ids, score_expected,
            )
            per_signal_states[signal] = state_data
            task_key = (task["id"], signal)

            def validation(alpha):
                alpha_float = float(alpha)
                key = (*task_key, alpha_float.hex())
                if key not in validation_cache:
                    value = validate_replay(
                        route, route["candidates"], signal, alpha_float, task["expected"],
                        evidence_target_ids, score_expected, replay,
                    )
                    validation_cache[key] = value
                    validation_rows.append({
                        "task_id": task["id"],
                        "signal": signal,
                        "alpha": alpha_float,
                        "alpha_hex": alpha_float.hex(),
                        "top5_match": value["top5_match"],
                        "full_order_match": value["full_order_match"],
                    })
                return validation_cache[key]

            baseline_validation = validation(1.0)
            if not baseline_validation["top5_match"]:
                raise RuntimeError(f"analytical reconstruction mismatch: {task['id']} {signal}")
            grid = []
            for alpha in FIXED_GRID:
                checked = validation(alpha)
                state = {
                    "kind": "point",
                    "alpha": as_fraction(alpha),
                    "left": None,
                    "right": None,
                    "top5": checked["actual"]["top5"],
                    "evidence_ranks": checked["actual"]["evidence_ranks"],
                    "score": checked["actual"]["score"],
                }
                grid.append((alpha, state, checked))
                variant_keys.add((task["id"], signal, alpha))
            per_signal_grid[signal] = grid

        task_target_rows = []
        for target_id in ranking_loss_targets:
            signal_reports = []
            continuous_states = []
            fixed_successful = []
            fixed_safe = []
            replay_reachable = False
            replay_safe = False
            replay_best = None
            replay_best_safe = None

            for signal in signals:
                rank_analysis = target_rank_analysis(
                    route["candidates"], target_id, signal, required_cutoff,
                )
                state_data = per_signal_states[signal]
                continuous_states.extend((signal, state) for state in state_data["states"])
                validations = []
                samples = [(1.0, "baseline")]
                for interval in rank_analysis["intervals"]:
                    if interval["recovered"]:
                        sample = representable_interval_sample(interval["left"], interval["right"])
                        if sample is not None:
                            samples.append((sample, "recovered_open_interval"))
                if not any(source == "recovered_open_interval" for _, source in samples) and rank_analysis["intervals"]:
                    first = rank_analysis["intervals"][0]
                    sample = representable_interval_sample(first["left"], first["right"])
                    if sample is not None:
                        samples.append((sample, "first_open_interval"))
                for alpha, state, checked in per_signal_grid[signal]:
                    action_outcome = outcome(
                        state, target_id, required_cutoff, originally_retrieved, baseline_score,
                    )
                    if action_outcome["recovered"]:
                        witness = {
                            "signal": signal,
                            "multiplier": alpha,
                            "kind": action_kind(alpha),
                            **action_outcome,
                        }
                        fixed_successful.append(witness)
                        if action_outcome["safe_recovery"]:
                            fixed_safe.append(witness)
                    samples.append((alpha, "fixed_grid"))
                seen_samples = set()
                for alpha, source in samples:
                    key = float(alpha).hex()
                    if key in seen_samples:
                        continue
                    seen_samples.add(key)
                    checked = validation_cache[(task["id"], signal, key)] if (task["id"], signal, key) in validation_cache else validate_replay(
                        route, route["candidates"], signal, float(alpha), task["expected"],
                        evidence_target_ids, score_expected, replay,
                    )
                    if (task["id"], signal, key) not in validation_cache:
                        validation_cache[(task["id"], signal, key)] = checked
                        validation_rows.append({
                            "task_id": task["id"], "signal": signal, "alpha": float(alpha),
                            "alpha_hex": key, "top5_match": checked["top5_match"],
                            "full_order_match": checked["full_order_match"],
                        })
                    record = target_validation_record(
                        checked, target_id, required_cutoff, originally_retrieved, baseline_score, source,
                    )
                    validations.append(record)
                    actual_outcome = record["actual_outcome"]
                    if actual_outcome["recovered"]:
                        replay_reachable = True
                        replay_witness = {
                            "signal": signal,
                            "alpha": record["alpha"],
                            "source": source,
                            **actual_outcome,
                        }
                        if replay_best is None or (
                            -int(replay_witness["safe_recovery"]),
                            -int(replay_witness["score_nonregressing"]),
                            replay_witness["new_rank"],
                            abs(replay_witness["alpha"] - 1.0),
                        ) < (
                            -int(replay_best["safe_recovery"]),
                            -int(replay_best["score_nonregressing"]),
                            replay_best["new_rank"],
                            abs(replay_best["alpha"] - 1.0),
                        ):
                            replay_best = replay_witness
                    if actual_outcome["safe_recovery"]:
                        replay_safe = True
                        if replay_best_safe is None or (
                            actual_outcome["new_rank"], abs(record["alpha"] - 1.0)
                        ) < (
                            replay_best_safe["new_rank"], abs(replay_best_safe["alpha"] - 1.0)
                        ):
                            replay_best_safe = {
                                "signal": signal,
                                "alpha": record["alpha"],
                                "source": source,
                                **actual_outcome,
                            }
                signal_math = best_actions(
                    [(signal, state) for state in state_data["states"]], target_id,
                    required_cutoff, originally_retrieved, baseline_score,
                )
                signal_reports.append({
                    "signal": signal,
                    "reachable": signal_math["recovered"],
                    "safe_reachable": signal_math["safe"],
                    "score_nonregressing_reachable": signal_math["nonregressing"],
                    "best_recovery_witness": signal_math["best"],
                    "best_safe_witness": signal_math["best_safe"],
                    "benchmark_outcome_partition": {
                        "open_interval_count": state_data["open_interval_count"],
                        "point_count": state_data["point_count"],
                    },
                    "target_rank_partition": rank_analysis["report"],
                    "selected_replay_validations": validations,
                })

            mathematical = best_actions(
                continuous_states, target_id, required_cutoff, originally_retrieved, baseline_score,
            )
            fixed_successful.sort(key=lambda action: (
                -int(action["safe_recovery"]),
                -int(action["score_nonregressing"]),
                -action["score_delta"],
                action["new_rank"],
                CHANNELS.index(action["signal"]),
                FIXED_GRID.index(action["multiplier"]),
            ))
            row = {
                "task_id": task["id"],
                "category": task.get("category"),
                "query_op": task["query"].get("op"),
                "target_id": target_id,
                "cutoff": required_cutoff,
                "baseline_rank": baseline_ranks[target_id],
                "baseline_score": baseline_score,
                "candidate_count": len(route["candidates"]),
                "fallback": bool(route.get("fallback")),
                "analysis_status": "fallback_without_scored_signals" if not signals else "analyzed",
                "active_signals": signals,
                "inactive_signals": inactive,
                "fixed_grid": {
                    "multipliers": list(FIXED_GRID),
                    "reachable": bool(fixed_successful),
                    "safe_reachable": bool(fixed_safe),
                    "successful_actions": fixed_successful,
                    "best_recovery": fixed_successful[0] if fixed_successful else None,
                },
                "continuous_oracle": {
                    "reachable": mathematical["recovered"],
                    "safe_reachable": mathematical["safe"],
                    "score_nonregressing_reachable": mathematical["nonregressing"],
                    "reachable_on_open_interval": mathematical["open_interval"],
                    "reachable_at_evaluated_point": mathematical["point"],
                    "tie_only": mathematical["tie_only"],
                    "best_recovery_witness": mathematical["best"],
                    "best_safe_witness": mathematical["best_safe"],
                    "replay_witnessed_reachable": replay_reachable,
                    "replay_witnessed_safe_reachable": replay_safe,
                    "best_replay_witness": replay_best,
                    "best_safe_replay_witness": replay_best_safe,
                },
                "signals": signal_reports,
            }
            target_rows.append(row)
            task_target_rows.append(row)

        joint_states = [
            (signal, state, task_joint_outcome(
                state, ranking_loss_targets, required_cutoff, originally_retrieved, baseline_score,
            ))
            for signal, state_data in per_signal_states.items()
            for state in state_data["states"]
        ]
        joint_states.sort(key=lambda item: joint_key(*item))
        joint_all = [item for item in joint_states if item[2]["all_ranking_loss_targets_recovered"]]
        joint_safe = [item for item in joint_states if item[2]["safe_joint_recovery"]]
        fixed_joint = []
        for signal, grid in per_signal_grid.items():
            for alpha, state, checked in grid:
                value = task_joint_outcome(
                    state, ranking_loss_targets, required_cutoff, originally_retrieved, baseline_score,
                )
                fixed_joint.append((signal, state, value))
        fixed_joint.sort(key=lambda item: joint_key(*item))
        fixed_joint_all = [item for item in fixed_joint if item[2]["all_ranking_loss_targets_recovered"]]
        fixed_joint_safe = [item for item in fixed_joint if item[2]["safe_joint_recovery"]]
        task_rows.append({
            "task_id": task["id"],
            "category": task.get("category"),
            "query_op": task["query"].get("op"),
            "cutoff": required_cutoff,
            "candidate_count": len(route["candidates"]),
            "fallback": bool(route.get("fallback")),
            "evidence_target_ids": evidence_target_ids,
            "originally_retrieved_target_ids": originally_retrieved,
            "ranking_loss_target_ids": ranking_loss_targets,
            "ranking_loss_target_count": len(ranking_loss_targets),
            "active_signals": signals,
            "fixed_grid": {
                "all_targets_jointly_reachable": bool(fixed_joint_all),
                "safe_all_targets_jointly_reachable": bool(fixed_joint_safe),
                "best_joint_witness": joint_witness(*fixed_joint_all[0]) if fixed_joint_all else None,
                "best_safe_joint_witness": joint_witness(*fixed_joint_safe[0]) if fixed_joint_safe else None,
            },
            "continuous_oracle": {
                "individually_reachable_target_count": sum(row["continuous_oracle"]["reachable"] for row in task_target_rows),
                "any_target_individually_reachable": any(row["continuous_oracle"]["reachable"] for row in task_target_rows),
                "all_targets_individually_reachable": all(row["continuous_oracle"]["reachable"] for row in task_target_rows),
                "joint_all_targets_reachable": bool(joint_all),
                "safe_joint_all_targets_reachable": bool(joint_safe),
                "best_joint_witness": joint_witness(*joint_all[0]) if joint_all else None,
                "best_safe_joint_witness": joint_witness(*joint_safe[0]) if joint_safe else None,
            },
        })

    summary = summarize(
        target_rows, task_rows, stages, len(tasks), reference_matches, variant_keys, validation_rows,
    )
    return {
        "scope": {
            "benchmark": "LongMemCode",
            "selection": "explicit benchmark evidence targets diagnosed as ranking_loss under the frozen reference replay",
            "unit": "task-target pair",
            "intervention": "one original nonzero RRF signal weight multiplied by alpha in [0,4] with all other weights, candidates, signal ranks, and corpus-order tie-breaking fixed",
            "oracle_label_use": "benchmark labels select and assess target-specific interventions after reranking; these counts are diagnostic oracle upper bounds, not contrastive-method performance",
            "safety": "post hoc only: the target is recovered, the task score does not regress, and no other originally retrieved explicit benchmark target falls beyond the task cutoff",
        },
        "summary": summary,
        "tasks": task_rows,
        "targets": target_rows,
        "limitations": [
            "Fallback routes expose no per-signal ranks or contributions, so multiplicative signal analysis is undefined for their ranking-loss targets.",
            "The oracle chooses a signal and alpha using benchmark labels separately for each task-target pair; it is not a deployable global policy or a method evaluation.",
            "Safety is evaluated after reranking with benchmark labels and is not a label-free retrieval guarantee.",
            "Analytical lines are anchored to each candidate's replay-equivalent binary floating-point score at alpha=1 and use exact rational arithmetic thereafter; a mathematical tie alpha may not itself be representable as a binary float.",
            "Open-interval witnesses and the fixed grid are checked independently through the repository replay function; tie-only mathematical witnesses are reported separately.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    parser.add_argument("--baseline-audit", type=Path, default=ROOT / "outputs" / "ranking_recoverability_audit.json")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    sys.path.insert(0, str(ROOT / "python"))
    from code_metrics import score_expected
    from code_search import CodeSearch
    from retrieval_inspection import evidence_ids, replay

    base = ROOT / "data" / "code"
    tasks = read(base / "tasks.json")
    recorded = read(base / "recorded_dense_order.json")["rankings"]
    reference = read(ROOT / "results" / "code_reference.json")["ids"]
    engine = CodeSearch(read(base / "documents.json"), read(base / "projection.json"), base / "source")
    report = analyze(tasks, recorded, reference, engine, score_expected, evidence_ids, replay)
    baseline_summary = EXPECTED_BASELINE
    if args.baseline_audit.exists():
        baseline_summary = read(args.baseline_audit).get("summary", {})
    comparison = baseline_comparison(report["summary"], baseline_summary)
    report["baseline_comparison"] = comparison
    if not comparison["matches"]:
        raise RuntimeError(f"fixed-grid baseline mismatch: {comparison}")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "continuous_weight_interval_audit.json"
    summary_path = output_dir / "continuous_weight_interval_summary.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary_payload = {
        "scope": report["scope"],
        "summary": report["summary"],
        "baseline_comparison": comparison,
        "limitations": report["limitations"],
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary_payload, indent=2, ensure_ascii=False))
    print(f"Saved: {report_path}")
    print(f"Saved: {summary_path}")


if __name__ == "__main__":
    main()

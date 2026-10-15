from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = ("structural_order", "bm25", "edge_frequency", "graph_degree", "id_overlap")
GRID = (0.0, 0.25, 0.5, 2.0, 4.0)
EXPECTED = {
    "total_tasks": 425,
    "retrieved_pairs": 442,
    "candidate_missing_pairs": 195,
    "ranking_loss_pairs": 187,
    "tasks_with_ranking_loss": 72,
    "eligible_pairs": 180,
    "unsupported_pairs": 7,
    "grid_reachable_pairs": 30,
    "unique_grid_actions": 1105,
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def required_cutoff(expected):
    kind = expected.get("kind")
    result = 1 if kind == "exact_symbol" else int(expected.get("k", 5)) if kind == "in_top_k" else 5
    if not 1 <= result <= 5:
        raise ValueError(f"unsupported cutoff: {result}")
    return result


def active_signals(candidates):
    return [name for name in CHANNELS if any(
        row.get("signals", {}).get(name, {}).get("weight", 0.0) != 0.0
        for row in candidates
    )]


def validate_action(signal, alpha):
    if signal not in CHANNELS or not math.isfinite(alpha) or not 0.0 <= alpha <= 4.0:
        raise ValueError("invalid one-signal intervention")


def candidate_score(candidate, signal, alpha):
    validate_action(signal, alpha)
    score = float(sum(
        value.get("contribution", 0.0) * alpha if name == signal else value.get("contribution", 0.0)
        for name, value in candidate.get("signals", {}).items()
    ))
    if not math.isfinite(score):
        raise ValueError(f"non-finite score: {candidate['id']}")
    return score


def candidate_keys(candidates, signal, alpha):
    result = {}
    for position, candidate in enumerate(candidates):
        candidate_id = candidate["id"]
        if candidate_id in result:
            raise ValueError(f"duplicate candidate: {candidate_id}")
        result[candidate_id] = (
            -candidate_score(candidate, signal, alpha), candidate["corpus_order"], position,
        )
    return result


def rerank(route, signal, alpha, replay):
    validate_action(signal, alpha)
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


def ranking_ids(run):
    ids = [row["id"] for row in run["candidates"]]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate candidates in actual replay")
    if run["top5"] != ids[:5]:
        raise ValueError("inconsistent replay top5")
    if any(row["rank"] != rank for rank, row in enumerate(run["candidates"], 1)):
        raise ValueError("inconsistent replay ranks")
    return ids


def check_order(candidates, signal, alpha, actual):
    keys = candidate_keys(candidates, signal, alpha)
    predicted = sorted(keys, key=keys.__getitem__)
    ids = ranking_ids(actual)
    if set(predicted) != set(ids):
        raise ValueError("replay changed the frozen candidate set")
    return {
        "keys": keys,
        "ranks": {candidate_id: rank for rank, candidate_id in enumerate(ids, 1)},
        "full_order_match": predicted == ids,
        "top5_match": predicted[:5] == actual["top5"],
    }


def compare_prediction(checked, target_id, boundary_id, cutoff):
    keys = checked["keys"]
    ranks = checked["ranks"]
    local = bool(keys[target_id] < keys[boundary_id])
    recovered = ranks[target_id] <= cutoff
    classification = (
        "true_positive" if local and recovered else
        "false_positive" if local else
        "false_negative" if recovered else
        "true_negative"
    )
    return {
        "local_predicts_recovery": local,
        "actual_recovered": recovered,
        "classification": classification,
        "target_score": -keys[target_id][0],
        "original_boundary_score": -keys[boundary_id][0],
        "target_new_rank": ranks[target_id],
        "original_boundary_new_rank": ranks[boundary_id],
        "pair_order_match": local == (ranks[target_id] < ranks[boundary_id]),
        "full_order_match": checked["full_order_match"],
        "top5_match": checked["top5_match"],
    }


def make_case(task_id, target_id, boundary_id, baseline_rank, cutoff, signals, reason):
    return {
        "task_id": task_id,
        "target_id": target_id,
        "original_boundary_id": boundary_id,
        "baseline_target_rank": baseline_rank,
        "required_cutoff": cutoff,
        "analysis_status": "analyzed" if signals else reason,
        "signals": signals,
        "actions": [],
    }


def finish_case(case):
    if case["analysis_status"] != "analyzed":
        case.update({
            "has_false_positive": None, "has_false_negative": None,
            "has_disagreement": None, "actual_grid_reachable": None,
            "local_grid_predicted_reachable": None,
        })
        return
    kinds = {row["classification"] for row in case["actions"]}
    case.update({
        "has_false_positive": "false_positive" in kinds,
        "has_false_negative": "false_negative" in kinds,
        "has_disagreement": bool(kinds & {"false_positive", "false_negative"}),
        "actual_grid_reachable": any(row["actual_recovered"] for row in case["actions"]),
        "local_grid_predicted_reachable": any(row["local_predicts_recovery"] for row in case["actions"]),
    })


def summarize(targets, tasks, actions, stages, controls, total_tasks):
    eligible = [row for row in targets if row["analysis_status"] == "analyzed"]
    eligible_tasks = [row for row in tasks if row["eligible_pairs"]]
    confusion = Counter(row["classification"] for case in eligible for row in case["actions"])
    return {
        "total_tasks": total_tasks,
        "target_stages": dict(stages),
        "retrieved_pairs": stages["retrieved"],
        "candidate_missing_pairs": stages["candidate_missing"],
        "ranking_loss_pairs": len(targets),
        "tasks_with_ranking_loss": len(tasks),
        "eligible_pairs": len(eligible),
        "unsupported_pairs": len(targets) - len(eligible),
        "tasks_with_eligible_pairs": len(eligible_tasks),
        "unique_grid_actions": len(actions),
        "grid_target_action_comparisons": sum(len(row["actions"]) for row in eligible),
        "grid_reachable_pairs": sum(row["actual_grid_reachable"] for row in eligible),
        "local_grid_predicted_reachable_pairs": sum(row["local_grid_predicted_reachable"] for row in eligible),
        "pairs_with_false_positive": sum(row["has_false_positive"] for row in eligible),
        "pairs_with_false_negative": sum(row["has_false_negative"] for row in eligible),
        "pairs_with_either_error": sum(row["has_disagreement"] for row in eligible),
        "pairs_with_both_errors": sum(row["has_false_positive"] and row["has_false_negative"] for row in eligible),
        "eligible_pair_disagreement_rate": (
            sum(row["has_disagreement"] for row in eligible) / len(eligible) if eligible else None
        ),
        "eligible_task_macro_disagreement_rate": (
            sum(row["eligible_pair_disagreement_rate"] for row in eligible_tasks) / len(eligible_tasks)
            if eligible_tasks else None
        ),
        "tasks_with_any_disagreement": sum(bool(row["pairs_with_disagreement"]) for row in tasks),
        "action_comparison_counts_not_independent_samples": {
            name: confusion[name] for name in ("true_positive", "false_positive", "false_negative", "true_negative")
        },
        "numerical_controls": dict(controls),
    }


def analyze(tasks, recorded, reference, engine, evidence_ids, replay):
    if len({task["id"] for task in tasks}) != len(tasks):
        raise ValueError("duplicate task identifiers")
    targets = []
    task_rows = []
    action_rows = []
    stages = Counter({"retrieved": 0, "candidate_missing": 0, "ranking_loss": 0})
    controls = Counter({
        "reference_top5_matches": 0, "baseline_signal_checks": 0,
        "baseline_full_order_mismatches": 0, "baseline_top5_mismatches": 0,
        "baseline_pair_checks": 0, "baseline_pair_mismatches": 0,
        "grid_full_order_mismatches": 0, "grid_top5_mismatches": 0,
        "grid_pair_checks": 0, "grid_pair_mismatches": 0,
    })
    for task in tasks:
        task_id = task["id"]
        route = engine.route(task["query"], task["query_text"], dense_order=recorded.get(task_id))
        baseline = replay(route)
        baseline_ids = ranking_ids(baseline)
        if baseline["top5"] != reference.get(task_id):
            raise RuntimeError(f"frozen reference mismatch: {task_id}")
        controls["reference_top5_matches"] += 1
        cutoff = required_cutoff(task["expected"])
        baseline_ranks = {candidate_id: rank for rank, candidate_id in enumerate(baseline_ids, 1)}
        lost = []
        for target_id in dict.fromkeys(evidence_ids(task["expected"])):
            rank = baseline_ranks.get(target_id)
            if rank is None:
                stages["candidate_missing"] += 1
            elif rank > cutoff:
                stages["ranking_loss"] += 1
                lost.append(target_id)
            else:
                stages["retrieved"] += 1
        if not lost:
            continue
        boundary_id = baseline_ids[cutoff - 1]
        signals = [] if route.get("fallback") else active_signals(route["candidates"])
        reason = "fallback_without_signal_decomposition" if route.get("fallback") else "no_active_scored_signals"
        cases = [make_case(
            task_id, target_id, boundary_id, baseline_ranks[target_id], cutoff, signals, reason,
        ) for target_id in lost]
        for signal in signals:
            baseline_check = check_order(route["candidates"], signal, 1.0, baseline)
            controls["baseline_signal_checks"] += 1
            controls["baseline_full_order_mismatches"] += not baseline_check["full_order_match"]
            controls["baseline_top5_mismatches"] += not baseline_check["top5_match"]
            for case in cases:
                checked_pair = compare_prediction(baseline_check, case["target_id"], boundary_id, cutoff)
                controls["baseline_pair_checks"] += 1
                controls["baseline_pair_mismatches"] += not checked_pair["pair_order_match"]
                if checked_pair["actual_recovered"] or checked_pair["local_predicts_recovery"]:
                    raise RuntimeError(f"invalid ranking-loss baseline: {task_id} {case['target_id']}")
            for alpha in GRID:
                actual = rerank(route, signal, alpha, replay)
                checked = check_order(route["candidates"], signal, alpha, actual)
                controls["grid_full_order_mismatches"] += not checked["full_order_match"]
                controls["grid_top5_mismatches"] += not checked["top5_match"]
                action_rows.append({
                    "task_id": task_id, "signal": signal, "alpha": alpha,
                    "alpha_hex": alpha.hex(), "actual_top5": actual["top5"],
                    "full_order_match": checked["full_order_match"], "top5_match": checked["top5_match"],
                })
                for case in cases:
                    row = {
                        "signal": signal, "alpha": alpha, "alpha_hex": alpha.hex(),
                        **compare_prediction(checked, case["target_id"], boundary_id, cutoff),
                    }
                    controls["grid_pair_checks"] += 1
                    controls["grid_pair_mismatches"] += not row["pair_order_match"]
                    case["actions"].append(row)
        for case in cases:
            finish_case(case)
        eligible = [row for row in cases if row["analysis_status"] == "analyzed"]
        task_rows.append({
            "task_id": task_id, "query": task["query"], "required_cutoff": cutoff,
            "baseline_top5": baseline["top5"], "original_boundary_id": boundary_id,
            "candidate_count": len(route["candidates"]), "fallback": bool(route.get("fallback")),
            "ranking_loss_pairs": len(cases), "eligible_pairs": len(eligible),
            "unsupported_pairs": len(cases) - len(eligible), "target_ids": lost,
            "pairs_with_false_positive": sum(row["has_false_positive"] for row in eligible),
            "pairs_with_false_negative": sum(row["has_false_negative"] for row in eligible),
            "pairs_with_disagreement": sum(row["has_disagreement"] for row in eligible),
            "eligible_pair_disagreement_rate": (
                sum(row["has_disagreement"] for row in eligible) / len(eligible) if eligible else None
            ),
        })
        targets.extend(cases)
    summary = summarize(targets, task_rows, action_rows, stages, controls, len(tasks))
    examples = {}
    for kind in ("false_positive", "false_negative"):
        found = [
            {**{name: case[name] for name in (
                "task_id", "target_id", "original_boundary_id", "baseline_target_rank", "required_cutoff",
            )}, **row}
            for case in targets for row in case["actions"]
            if row["classification"] == kind and row["pair_order_match"] and row["full_order_match"]
        ]
        found.sort(key=lambda row: (row["task_id"], row["target_id"], CHANNELS.index(row["signal"]), row["alpha"]))
        distinct = {}
        for row in found:
            distinct.setdefault((row["task_id"], row["target_id"]), row)
        examples[kind] = list(distinct.values())[:5]
    return {
        "scope": {
            "hypothesis": "plan-H2: original-boundary comparison is insufficient on the fixed grid",
            "protocol": "local-boundary-prediction-fixed-grid-v1",
            "benchmark": "LongMemCode FastAPI frozen development set",
            "unit": "task-target pair, with task-level summaries",
            "multipliers": list(GRID), "baseline_multiplier_control": 1.0,
            "local_rule": "target outranks the original cutoff candidate after the same intervention and tie-break",
            "actual_reference": "target rank within cutoff in repository retrieval_inspection.replay",
            "frozen": "candidate set, signal ranks, other contributions, recorded dense order, original tie-breaking",
            "label_use": "benchmark labels identify lost targets; this is target-informed diagnosis",
            "safety_evaluated": False,
            "interpretation": "descriptive prediction comparison, not one-action policy performance or held-out validation",
        },
        "summary": summary, "tasks": task_rows, "targets": targets,
        "grid_actions": action_rows, "examples": examples,
        "limitations": [
            "Only the five declared multipliers are tested; no disagreement does not establish correctness throughout [0,4].",
            "Unsupported fallback pairs have undefined predictions, not evidence of infeasibility or correct negative predictions.",
            "Targets can exhibit both error types under different actions; their counts are not mutually exclusive.",
            "Task-target pairs, query families, and repeated code elements can be dependent; action checks are not independent samples.",
            "Score reconstruction controls use the same floating-point contribution scaling as actual replay, not exact-real interval arithmetic.",
            "This experiment does not select an action, evaluate safe recovery, or measure developer usability.",
        ],
    }


def validate_report(report):
    summary = report["summary"]
    observed = {name: summary[name] for name in EXPECTED}
    report["baseline_comparison"] = {
        "expected": EXPECTED, "observed": observed, "matches": observed == EXPECTED,
    }
    controls = summary["numerical_controls"]
    numeric_ok = all(value == 0 for name, value in controls.items() if name.endswith("mismatches"))
    report["status"] = "valid" if observed == EXPECTED and numeric_ok else "validation_failed"
    return report["status"] == "valid"


def provenance(root):
    files = [
        root / "data" / "code" / name
        for name in ("tasks.json", "documents.json", "projection.json", "recorded_dense_order.json")
    ]
    files.extend([root / "results" / "code_reference.json", Path(__file__).resolve()])
    files.extend(path for path in (
        root / "experiments" / "test_audit_local_boundary_prediction.py",
        root / "docs" / "local-boundary-prediction-protocol.md",
    ) if path.is_file())
    files.extend(path for path in (root / "python").rglob("*.py") if path.is_file())
    files.extend(path for path in (root / "data" / "code" / "source").rglob("*") if path.is_file())
    hashes = {}
    for path in sorted(set(files)):
        relative = path.relative_to(root).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    git = {}
    for name, command in (("head", ["rev-parse", "HEAD"]), ("branch", ["branch", "--show-current"])):
        try:
            run = subprocess.run(["git", *command], cwd=root, capture_output=True, text=True, check=True)
            git[name] = run.stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            git[name] = None
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version, "git": git, "sha256": hashes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "local_boundary_prediction")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        parser.error("output directory already exists; choose a new directory to preserve previous outputs")
    sys.path.insert(0, str(ROOT / "python"))
    from code_search import CodeSearch
    from retrieval_inspection import evidence_ids, replay

    base = ROOT / "data" / "code"
    engine = CodeSearch(read_json(base / "documents.json"), read_json(base / "projection.json"), base / "source")
    report = analyze(
        read_json(base / "tasks.json"), read_json(base / "recorded_dense_order.json")["rankings"],
        read_json(ROOT / "results" / "code_reference.json")["ids"], engine, evidence_ids, replay,
    )
    valid = validate_report(report)
    report["provenance"] = provenance(ROOT)
    payload = {name: report[name] for name in ("status", "scope", "summary", "baseline_comparison", "examples", "limitations")}
    payload["provenance"] = {name: value for name, value in report["provenance"].items() if name != "sha256"}
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, content in (("local_boundary_prediction_audit.json", report), ("local_boundary_prediction_summary.json", payload)):
        with (output_dir / name).open("x", encoding="utf-8") as stream:
            json.dump(content, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    print(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))
    print(f"Saved results: {output_dir}")
    if not valid:
        raise SystemExit("validation failed; saved diagnostic outputs must not be interpreted as a valid H2 result")


if __name__ == "__main__":
    main()

from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("audit_local_boundary_prediction.py")
SPEC = importlib.util.spec_from_file_location("audit_local_boundary_prediction", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def candidate(name, variable, fixed, order):
    return {
        "id": name, "corpus_order": order,
        "signals": {
            "graph_degree": {"weight": 1.0, "contribution": variable},
            "bm25": {"weight": 1.0, "contribution": fixed},
        },
    }


def replay(route):
    rows = []
    for row in route["candidates"]:
        score = row["score"] if route.get("fallback") else sum(
            value["contribution"] for value in row["signals"].values()
        )
        rows.append({**row, "score": score})
    rows.sort(key=lambda row: (-row["score"], row["corpus_order"]))
    return {
        "top5": [row["id"] for row in rows[:5]],
        "candidates": [{**row, "rank": rank} for rank, row in enumerate(rows, 1)],
    }


def false_positive_route():
    return {"candidates": [
        candidate("ahead", 0.0, 10.0, 0),
        candidate("boundary", 9.0, 0.0, 1),
        candidate("target", 6.0, 2.0, 2),
        candidate("overtaker", 0.0, 7.0, 3),
    ]}


def false_negative_route():
    return {"candidates": [
        candidate("ahead", 10.0, 0.0, 0),
        candidate("boundary", 0.0, 9.0, 1),
        candidate("target", 0.0, 8.0, 2),
        candidate("other", 0.0, 7.0, 3),
    ]}


class Engine:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def route(self, query, query_text, dense_order=None):
        self.calls.append((query_text, dense_order))
        return copy.deepcopy(self.routes[query_text])


def task(task_id, targets=None):
    return {
        "id": task_id, "query": {"op": "callers"}, "query_text": task_id,
        "expected": {"kind": "in_top_k", "k": 2, "targets": targets if targets is not None else ["target"]},
    }


def analyze_fixture(routes, tasks=None, counter=None):
    tasks = tasks if tasks is not None else [task(task_id) for task_id in routes]
    engine = Engine(routes)
    reference = {task_id: replay(route)["top5"] for task_id, route in routes.items()}

    def actual_replay(route):
        if counter is not None:
            counter.append(1)
        return replay(route)

    report = AUDIT.analyze(
        tasks, {task_id: ["recorded"] for task_id in routes}, reference, engine,
        lambda expected: expected["targets"], actual_replay,
    )
    return report, engine


class BoundaryPredictionTests(unittest.TestCase):
    def test_outranking_original_boundary_can_fail_to_recover(self):
        route = false_positive_route()
        changed = AUDIT.rerank(route, "graph_degree", 0.5, replay)
        checked = AUDIT.check_order(route["candidates"], "graph_degree", 0.5, changed)
        result = AUDIT.compare_prediction(checked, "target", "boundary", 2)
        self.assertEqual(result["classification"], "false_positive")
        self.assertEqual(result["target_new_rank"], 3)
        self.assertEqual(result["original_boundary_new_rank"], 4)
        self.assertTrue(result["pair_order_match"])
        self.assertTrue(result["full_order_match"])

    def test_recovery_can_occur_without_outranking_original_boundary(self):
        route = false_negative_route()
        changed = AUDIT.rerank(route, "graph_degree", 0.5, replay)
        checked = AUDIT.check_order(route["candidates"], "graph_degree", 0.5, changed)
        result = AUDIT.compare_prediction(checked, "target", "boundary", 2)
        self.assertEqual(result["classification"], "false_negative")
        self.assertEqual(result["target_new_rank"], 2)
        self.assertEqual(result["original_boundary_new_rank"], 1)

    def test_corpus_order_breaks_exact_score_ties(self):
        for target_order, expected in ((0, True), (2, False)):
            with self.subTest(target_order=target_order):
                route = {"candidates": [
                    candidate("boundary", 0.0, 2.0, 1),
                    candidate("target", 2.0, 1.0, target_order),
                ]}
                changed = AUDIT.rerank(route, "graph_degree", 0.5, replay)
                checked = AUDIT.check_order(route["candidates"], "graph_degree", 0.5, changed)
                result = AUDIT.compare_prediction(checked, "target", "boundary", 1)
                self.assertEqual(result["local_predicts_recovery"], expected)
                self.assertEqual(result["actual_recovered"], expected)

    def test_stable_input_order_is_preserved_if_corpus_orders_tie(self):
        route = {"candidates": [candidate("boundary", 0.0, 2.0, 7), candidate("target", 0.0, 2.0, 7)]}
        checked = AUDIT.check_order(route["candidates"], "graph_degree", 0.5, replay(route))
        result = AUDIT.compare_prediction(checked, "target", "boundary", 1)
        self.assertFalse(result["local_predicts_recovery"])
        self.assertTrue(result["pair_order_match"])

    def test_reranking_does_not_mutate_original_trace(self):
        route = false_positive_route()
        original = copy.deepcopy(route)
        AUDIT.rerank(route, "graph_degree", 0.5, replay)
        self.assertEqual(route, original)

    def test_missing_selected_signal_has_zero_contribution(self):
        row = {"id": "only_bm25", "corpus_order": 0, "signals": {"bm25": {"weight": 1.0, "contribution": 2.0}}}
        self.assertEqual(AUDIT.candidate_score(row, "graph_degree", 4.0), 2.0)

    def test_repeated_symbol_across_tasks_counts_twice(self):
        report, engine = analyze_fixture({"first": false_positive_route(), "second": false_positive_route()})
        self.assertEqual(report["summary"]["ranking_loss_pairs"], 2)
        self.assertEqual(report["summary"]["tasks_with_ranking_loss"], 2)
        self.assertEqual(report["summary"]["pairs_with_false_positive"], 2)
        self.assertEqual(engine.calls, [("first", ["recorded"]), ("second", ["recorded"])])

    def test_multiple_targets_share_task_signal_replays(self):
        calls = []
        report, _ = analyze_fixture(
            {"multi": false_positive_route()}, [task("multi", ["target", "overtaker"])], calls,
        )
        self.assertEqual(report["summary"]["ranking_loss_pairs"], 2)
        self.assertEqual(report["summary"]["unique_grid_actions"], 10)
        self.assertEqual(report["summary"]["grid_target_action_comparisons"], 20)
        self.assertEqual(len(calls), 11)

    def test_duplicate_evidence_identifier_is_not_counted_twice(self):
        report, _ = analyze_fixture({"one": false_positive_route()}, [task("one", ["target", "target"])])
        self.assertEqual(report["summary"]["ranking_loss_pairs"], 1)

    def test_fallback_is_unsupported_not_a_correct_negative(self):
        route = {"fallback": True, "candidates": [
            {"id": name, "corpus_order": order, "score": 4.0 - order, "signals": {}}
            for order, name in enumerate(("ahead", "boundary", "target"))
        ]}
        report, _ = analyze_fixture({"fallback": route})
        self.assertEqual(report["summary"]["unsupported_pairs"], 1)
        self.assertEqual(report["summary"]["eligible_pairs"], 0)
        self.assertIsNone(report["summary"]["eligible_pair_disagreement_rate"])
        self.assertIsNone(report["targets"][0]["has_disagreement"])
        self.assertEqual(report["targets"][0]["analysis_status"], "fallback_without_signal_decomposition")

    def test_pair_flags_and_action_counts_are_distinct(self):
        report, _ = analyze_fixture({"one": false_positive_route()})
        summary = report["summary"]
        self.assertEqual(summary["pairs_with_false_positive"], 1)
        self.assertGreaterEqual(summary["action_comparison_counts_not_independent_samples"]["false_positive"], 1)
        self.assertEqual(summary["grid_target_action_comparisons"], 10)
        self.assertEqual(report["scope"]["multipliers"], [0.0, 0.25, 0.5, 2.0, 4.0])
        self.assertNotIn(1.0, [row["alpha"] for row in report["grid_actions"]])

    def test_all_numerical_controls_pass_for_valid_fixture(self):
        report, _ = analyze_fixture({"one": false_positive_route()})
        controls = report["summary"]["numerical_controls"]
        self.assertEqual(controls["reference_top5_matches"], 1)
        self.assertEqual(controls["baseline_signal_checks"], 2)
        self.assertTrue(all(value == 0 for name, value in controls.items() if name.endswith("mismatches")))

    def test_examples_use_distinct_pairs_with_deterministic_order(self):
        report, _ = analyze_fixture({"second": false_positive_route(), "first": false_positive_route()})
        examples = report["examples"]["false_positive"]
        self.assertEqual([row["task_id"] for row in examples], ["first", "second"])
        self.assertTrue(all(row["full_order_match"] and row["pair_order_match"] for row in examples))

    def test_pair_error_types_overlap_without_double_counting_the_union(self):
        report, _ = analyze_fixture({"both": false_positive_route()})
        summary = report["summary"]
        self.assertEqual(summary["pairs_with_false_positive"], 1)
        self.assertEqual(summary["pairs_with_false_negative"], 1)
        self.assertEqual(summary["pairs_with_both_errors"], 1)
        self.assertEqual(summary["pairs_with_either_error"], 1)

    def test_no_disagreement_is_reported_without_an_error(self):
        route = {"candidates": [
            candidate("ahead", 0.0, 10.0, 0), candidate("boundary", 0.0, 9.0, 1),
            candidate("target", 0.0, 8.0, 2), candidate("other", 0.0, 7.0, 3),
        ]}
        report, _ = analyze_fixture({"none": route})
        self.assertEqual(report["summary"]["pairs_with_either_error"], 0)
        self.assertEqual(report["summary"]["eligible_pair_disagreement_rate"], 0.0)
        self.assertEqual(report["examples"], {"false_positive": [], "false_negative": []})

    def test_candidate_generation_loss_is_not_an_h2_case(self):
        report, _ = analyze_fixture({"missing": false_positive_route()}, [task("missing", ["not_a_candidate"])])
        self.assertEqual(report["summary"]["candidate_missing_pairs"], 1)
        self.assertEqual(report["summary"]["ranking_loss_pairs"], 0)
        self.assertEqual(report["summary"]["unique_grid_actions"], 0)

    def test_nonfinite_contribution_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            AUDIT.candidate_score(candidate("bad", float("nan"), 1.0, 0), "graph_degree", 1.0)

    def test_invalid_baseline_reference_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "reference mismatch"):
            AUDIT.analyze([task("one")], {}, {"one": []}, Engine({"one": false_positive_route()}), lambda item: item["targets"], replay)

    def test_duplicate_task_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate task"):
            analyze_fixture({"one": false_positive_route()}, [task("one"), task("one")])

    def test_full_order_control_detects_wrong_replay_order(self):
        route = false_positive_route()
        actual = replay(route)
        rows = actual["candidates"]
        rows[0], rows[3] = rows[3], rows[0]
        actual = {"top5": [row["id"] for row in rows], "candidates": [{**row, "rank": rank} for rank, row in enumerate(rows, 1)]}
        self.assertFalse(AUDIT.check_order(route["candidates"], "graph_degree", 1.0, actual)["full_order_match"])

    def test_validation_failure_is_not_a_valid_hypothesis_result(self):
        report = {"summary": {**AUDIT.EXPECTED, "numerical_controls": {"grid_full_order_mismatches": 1}}}
        self.assertFalse(AUDIT.validate_report(report))
        self.assertEqual(report["status"], "validation_failed")

    def test_frozen_baseline_count_drift_is_detected(self):
        report = {"summary": {**AUDIT.EXPECTED, "ranking_loss_pairs": 188, "numerical_controls": {"grid_full_order_mismatches": 0}}}
        self.assertFalse(AUDIT.validate_report(report))
        self.assertFalse(report["baseline_comparison"]["matches"])

    def test_invalid_interventions_are_rejected(self):
        for signal, alpha in (("invalid", 1.0), ("bm25", -1.0), ("bm25", 4.1), ("bm25", float("nan")), ("bm25", float("inf"))):
            with self.subTest(signal=signal, alpha=alpha), self.assertRaises(ValueError):
                AUDIT.rerank(false_positive_route(), signal, alpha, replay)

    def test_cutoff_contract(self):
        self.assertEqual(AUDIT.required_cutoff({"kind": "exact_symbol"}), 1)
        self.assertEqual(AUDIT.required_cutoff({"kind": "in_top_k", "k": 3}), 3)
        self.assertEqual(AUDIT.required_cutoff({"kind": "other"}), 5)
        with self.assertRaises(ValueError):
            AUDIT.required_cutoff({"kind": "in_top_k", "k": 6})

    def test_existing_output_directory_is_refused_before_loading_data(self):
        completed = subprocess.run(
            [sys.executable, str(MODULE), "--output-dir", str(MODULE.parent)],
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("output directory already exists", completed.stderr)


if __name__ == "__main__":
    unittest.main()

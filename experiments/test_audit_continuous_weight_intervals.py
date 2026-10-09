from __future__ import annotations

import importlib.util
from fractions import Fraction
from pathlib import Path

import pytest

MODULE = Path(__file__).with_name("audit_continuous_weight_intervals.py")
SPEC = importlib.util.spec_from_file_location("audit_continuous_weight_intervals", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def candidates():
    return [
        {
            "id": "ahead",
            "corpus_order": 0,
            "signals": {
                "structural_order": {"weight": 1.0, "contribution": 0.0},
                "bm25": {"weight": 1.0, "contribution": 1.5},
            },
        },
        {
            "id": "target",
            "corpus_order": 2,
            "signals": {
                "structural_order": {"weight": 1.0, "contribution": 1.0},
                "bm25": {"weight": 1.0, "contribution": 0.0},
            },
        },
        {
            "id": "behind",
            "corpus_order": 3,
            "signals": {
                "structural_order": {"weight": 1.0, "contribution": 0.5},
                "bm25": {"weight": 1.0, "contribution": 0.75},
            },
        },
    ]


def replay(route):
    rows = []
    for candidate in route["candidates"]:
        score = sum(value["contribution"] for value in candidate.get("signals", {}).values())
        rows.append({**candidate, "score": score})
    rows.sort(key=lambda row: (-row["score"], row["corpus_order"]))
    top = [row["id"] for row in rows[:5]]
    return {
        "top5": top,
        "candidates": [{**row, "rank": position} for position, row in enumerate(rows, 1)],
    }


def score_expected(expected, returned):
    target = expected["stable_id"]
    return {"score": float(target in returned[: expected.get("k", 5)])}


def test_simultaneous_threshold_and_original_tie_breaking():
    result = AUDIT.target_rank_analysis(candidates(), "target", "structural_order", 2)
    report = result["report"]
    assert report["distinct_in_domain_thresholds"] == 1
    threshold = report["thresholds"][0]
    assert Fraction(threshold["alpha"]["exact"]) == Fraction(3, 2)
    assert threshold["tied_candidate_ids"] == ["ahead", "behind"]
    assert threshold["target_rank_below"] == 3
    assert threshold["target_rank_at"] == 2
    assert threshold["target_rank_above"] == 1
    assert report["reachable_on_open_interval"]


def test_coincident_lines_are_reported_without_fake_thresholds():
    rows = candidates()
    rows.append({
        "id": "coincident",
        "corpus_order": 1,
        "signals": {
            "structural_order": {"weight": 1.0, "contribution": 1.0},
            "bm25": {"weight": 1.0, "contribution": 0.0},
        },
    })
    report = AUDIT.target_rank_analysis(rows, "target", "structural_order", 2)["report"]
    assert report["coincident_all_alpha_candidate_ids"] == ["coincident"]
    assert report["distinct_in_domain_thresholds"] == 1


def test_representable_sample_stays_inside_exact_interval():
    left = Fraction(1, 3)
    right = Fraction(1, 3) + Fraction(1, 10**12)
    sample = AUDIT.representable_interval_sample(left, right)
    assert sample is not None
    assert left < Fraction.from_float(sample) < right


def test_actual_replay_validation_uses_modified_route():
    route = {"candidates": candidates()}
    checked = AUDIT.validate_replay(
        route,
        route["candidates"],
        "structural_order",
        2.0,
        {"kind": "in_top_k", "stable_id": "target", "k": 2},
        ["target"],
        score_expected,
        replay,
    )
    assert checked["top5_match"]
    assert checked["full_order_match"]
    assert checked["actual"]["evidence_ranks"]["target"] == 1


def test_post_hoc_safety_detects_displaced_original_target():
    state = {
        "evidence_ranks": {"target": 1, "kept": 3},
        "score": 1.0,
    }
    result = AUDIT.outcome(state, "target", 2, ["kept"], 0.5)
    assert result["recovered"]
    assert result["score_nonregressing"]
    assert result["other_originally_retrieved_targets_lost"] == ["kept"]
    assert not result["safe_recovery"]


def test_fallback_candidates_have_no_active_signals():
    assert AUDIT.active_signals([
        {"id": "a", "corpus_order": 0, "score": 1.0, "signals": {}},
    ]) == []


@pytest.mark.parametrize("value", [-1.0, 4.0001, float("nan"), float("inf")])
def test_replay_rejects_invalid_multiplier(value):
    with pytest.raises(ValueError):
        AUDIT.replay_with_multiplier({"candidates": candidates()}, "structural_order", value, replay)

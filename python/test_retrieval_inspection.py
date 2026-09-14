import pytest

from retrieval_inspection import diagnose_stages, replay


def test_replay_is_label_free_and_intervention_changes_only_new_run():
    route = {
        "route": "calls",
        "candidates": [
            {"id": "a", "corpus_order": 0, "signals": {"bm25": {"contribution": 0.5}}},
            {"id": "b", "corpus_order": 1, "signals": {"edge_frequency": {"contribution": 0.2}}},
        ],
    }
    original = replay(route, limit=1)
    modified = replay(route, disabled=("bm25",), limit=1)
    assert original["top5"] == ["a"]
    assert modified["top5"] == ["b"]
    assert original["candidate_hash"] == modified["candidate_hash"]
    assert diagnose_stages(original, {"kind": "contains", "required": ["a", "b", "c"]}, []) == [
        {"id": "a", "stage": "reader_drop"},
        {"id": "b", "stage": "ranking_loss"},
        {"id": "c", "stage": "candidate_missing"},
    ]
    with pytest.raises(ValueError):
        diagnose_stages(original, {}, ["invented"])
    with pytest.raises(ValueError):
        replay(route, disabled=("gold",))


def test_exact_symbol_requires_first_position_and_extracts_official_ids():
    run = {"top5": ["other", "wanted"], "candidates": [{"id": "other"}, {"id": "wanted"}]}
    assert diagnose_stages(run, {"kind": "exact_symbol", "stable_id": "wanted"}) == [
        {"id": "wanted", "stage": "ranking_position_loss"}
    ]
    assert diagnose_stages(run, {"kind": "exact_set", "stable_ids": ["wanted"]}) == [
        {"id": "wanted", "stage": "retrieved"}
    ]

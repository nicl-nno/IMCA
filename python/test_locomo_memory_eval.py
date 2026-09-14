import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from locomo_memory_eval import (  # noqa: E402
    aggregate,
    build_manifest,
    exact_gold_date,
    freeze_retrieval,
    normalized_ids,
    score_frozen,
)


def sample():
    return [
        {
            "sample_id": "chat",
            "conversation": {
                "speaker_a": "Alice",
                "speaker_b": "Bob",
                "session_1_date_time": "1:00 pm on 6 January, 2024",
                "session_1": [
                    {"dia_id": "D1:1", "speaker": "Alice", "text": "I bought a bike yesterday."},
                    {"dia_id": "D1:2", "speaker": "Bob", "text": "I like hiking."},
                ],
            },
            "qa": [
                {
                    "question": "When did Alice buy a bike?",
                    "answer": "5 January 2024",
                    "category": 2,
                    "evidence": ["D1:01 D9:9"],
                },
                {
                    "question": "When did Bob buy a bike?",
                    "adversarial_answer": "5 January 2024",
                    "category": 5,
                    "evidence": ["D1:1"],
                },
                {
                    "question": "What does Bob like?",
                    "answer": "Hiking",
                    "category": 4,
                    "evidence": [],
                },
            ],
        }
    ]


def without_timings(rows):
    return [{k: v for k, v in row.items() if k not in {"search_ms", "reader_ms"}} for row in rows]


def test_frozen_retrieval_is_independent_of_labels_and_rescores(tmp_path):
    data = sample()
    before, inventories = freeze_retrieval(data, 2, tmp_path)
    mutated = copy.deepcopy(data)
    for qa in mutated[0]["qa"]:
        qa.update(answer="LEAK_MARKER", evidence=["D9:999"], category=5)
    after, _ = freeze_retrieval(mutated, 2, tmp_path)
    assert without_timings(before) == without_timings(after)
    report = score_frozen(data, before, inventories)
    assert report == score_frozen(data, before, inventories)
    assert report["profiles"]["bm25"]["evidence"]["n"] == 1
    assert report["profiles"]["bm25"]["evidence"]["recall_at_5"] == 0.5
    assert report["profiles"]["bm25"]["calendar_qa"]["correct"] == 1
    assert report["profiles"]["combined"]["adversarial"]["lure_hit_at_5"] == 0
    assert len(report["data_audit"]) == 2
    adversarial = [r for r in report["rows"] if r["category"] == 5]
    assert all(r["metrics"] is None and r["exact_gold_date"] is None for r in adversarial)
    with pytest.raises(ValueError, match="incomplete"):
        score_frozen(data, before[:-1], inventories)


def test_exact_gold_parser_and_empty_aggregates():
    assert exact_gold_date("January 5th, 2024") == "2024-01-05"
    assert exact_gold_date("January 2024") is None
    assert exact_gold_date("end of January 2024") is None
    assert exact_gold_date("31 February 2024") is None
    assert normalized_ids(["D1:01 D2:4", "D1:1"]) == ["D1:1", "D2:4"]
    assert aggregate([])["n"] == 0


def test_search_stable_across_hash_seeds():
    # Summation order must not depend on Python's randomized set iteration.
    from conversation_memory import LexicalIndex

    index = LexicalIndex(["a bike yesterday", "yesterday a bike", "hiking"])
    assert index.scores("bike yesterday") == index.scores("yesterday bike")


def test_manifest_records_guarded_retrieval_contract():
    manifest = build_manifest(sample(), "not-the-official-hash", repeats=3)

    assert manifest["rules_version"] == "conversation-rules-v3"
    assert manifest["profiles"][-1] == "guarded"
    assert manifest["temporal_overlap_multiplier"] == 1.2
    assert manifest["guarded_profile"] == {
        "base_index": "raw BM25",
        "participant_states": ["supported", "unknown", "mismatch", "not_requested"],
        "unknown_subject": "neutral; never filtered or penalized",
        "explicit_mismatch_multiplier": 0.5,
        "unknown_when": (
            "participant penalty disabled when the question starts with When "
            "and has no calendar constraint"
        ),
        "temporal_gate": "bonus only for an explicit question-time overlap",
        "selection_note": (
            "rules and multiplier developed on these same ten conversations; not a held-out result"
        ),
    }

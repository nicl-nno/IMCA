import copy
import json
from pathlib import Path

import pytest
from code_metrics import score_expected
from code_search import CodeSearch, fuse
from reproduce_code import verify_inputs
from retrieval_inspection import replay

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "expected,ids,value",
    [
        ({"kind": "exact_symbol", "stable_id": "a"}, ["b", "a"], 0),
        ({"kind": "in_top_k", "stable_id": "a", "k": 2}, ["b", "a"], 1),
        ({"kind": "exact_set", "stable_ids": ["a", "b"]}, ["a"], 2 / 3),
        ({"kind": "exact_set", "stable_ids": []}, [], 1),
        ({"kind": "contains", "required": ["a", "b"]}, ["a"], 0.5),
    ],
)
def test_public_scorer(expected, ids, value):
    assert score_expected(expected, ids)["score"] == pytest.approx(value)


def test_fusion_preserves_global_tie_order():
    ids, _ = fuse([[2, 1], [1, 2]], [1, 1], 60)
    assert ids == [1, 2]


def test_public_inputs_hash_and_all_425_rankings():
    verify_inputs()
    base = ROOT / "data/code"

    def load(path):
        return json.loads(path.read_text(encoding="utf-8"))

    engine = CodeSearch(
        load(base / "documents.json"), load(base / "projection.json"), base / "source"
    )
    tasks = load(base / "tasks.json")
    recorded = load(base / "recorded_dense_order.json")["rankings"]
    frozen = {}
    for task in tasks:
        frozen[task["id"]] = replay(
            engine.route(task["query"], task["query_text"], dense_order=recorded[task["id"]])
        )["top5"]
    # Labels/reference enter only after the full retrieval pass.
    assert len(frozen) == 425
    assert frozen == load(ROOT / "results/code_reference.json")["ids"]
    task = copy.deepcopy(tasks[0])
    task["expected"] = {"LEAK_MARKER": "not a search input"}
    assert (
        frozen[task["id"]]
        == replay(
            engine.route(task["query"], task["query_text"], dense_order=recorded[task["id"]])
        )["top5"]
    )

"""Rebuild source-backed rankings; distinguish recorded channels from new search."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from code_metrics import summarize  # noqa: E402
from code_search import CodeSearch  # noqa: E402
from inspectable_memory import digest  # noqa: E402
from retrieval_inspection import replay  # noqa: E402


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_inputs():
    for name, expected in read(ROOT / "data/manifest.json")["files"].items():
        path = (ROOT / name).resolve()
        if (
            not path.is_relative_to(ROOT)
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError(f"artifact changed: {name}")


def run(output, fresh=False, fixture_output=None):
    verify_inputs()
    base = ROOT / "data/code"
    engine = CodeSearch(
        read(base / "documents.json"), read(base / "projection.json"), base / "source"
    )
    tasks = read(base / "tasks.json")
    recorded = {} if fresh else read(base / "recorded_dense_order.json")["rankings"]
    frozen, routes = {}, {}
    for task in tasks:
        route = engine.route(
            task["query"], task["query_text"], dense_order=recorded.get(task["id"])
        )
        frozen[task["id"]] = replay(route)["top5"]
        routes[task["id"]] = route
    # Evaluation begins only after retrieval finishes for every task.
    reference = read(ROOT / "results/code_reference.json")["ids"]
    matched = sum(frozen[key] == reference[key] for key in frozen)
    if not fresh and matched != 425:
        bad = [key for key in frozen if frozen[key] != reference[key]]
        raise AssertionError(f"historical graph parity: {matched}/425; differences: {bad[:10]}")
    if fixture_output:
        fixture = read(ROOT / "demo/inspectable/fixture.json")
        for case in fixture["cases"]:
            key = case["id"]
            # A historical reader belongs only to its exact original top-5.
            if frozen[key] != replay(case["routes"]["references"])["top5"]:
                raise ValueError("cannot attach historical reader to changed candidates")
            case["routes"]["references"] = routes[key]
            case["routes"]["calls"] = engine.route(
                case["structured_query"],
                case["query"],
                relation="calls",
                dense_order=recorded.get(key),
            )
        fixture.pop("content_hash")
        fixture["content_hash"] = digest(fixture)
        fixture_output.parent.mkdir(parents=True, exist_ok=True)
        fixture_output.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    report = {
        "protocol": "new BM25-only fallback"
        if fresh
        else "source graph rebuilt; dense ranks replayed",
        "model_calls": 0,
        "historical_top5_matches": matched,
        "quality": summarize(tasks, frozen),
        "ids": frozen,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "ids"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/code.json")
    parser.add_argument("--fresh-bm25", action="store_true")
    parser.add_argument("--fixture-output", type=Path)
    args = parser.parse_args()
    run(args.output, args.fresh_bm25, args.fixture_output)

"""Independent implementation of the public LongMemCode scoring contract.

This module is evaluation-only. It must not be imported by candidate retrieval.
"""

from collections import defaultdict

WEIGHTS = {
    "Completion": 0.32,
    "BugFix": 0.22,
    "Refactor": 0.12,
    "TestGen": 0.10,
    "FeatureAdd": 0.10,
    "ApiDiscovery": 0.14,
}


def score_expected(expected, returned):
    kind = expected.get("kind")
    target = expected.get("stable_id")
    if kind == "exact_symbol":
        return {"score": float(bool(returned) and returned[0] == target)}
    if kind == "in_top_k":
        return {"score": float(target in returned[: int(expected.get("k", 5))])}
    actual = set(returned)
    if kind == "contains":
        needed = expected.get("required", [])
        return {"score": sum(item in actual for item in needed) / len(needed) if needed else 1.0}
    if kind == "exact_set":
        wanted = set(expected.get("stable_ids", []))
        if not wanted and not actual:
            return dict(score=1.0, precision=1.0, recall=1.0)
        overlap = len(actual & wanted)
        return dict(
            score=2 * overlap / (len(actual) + len(wanted)),
            precision=overlap / len(actual) if actual else 0.0,
            recall=overlap / len(wanted) if wanted else 0.0,
        )
    return {"score": 0.0}


def summarize(tasks, frozen_ids):
    groups = defaultdict(list)
    for task in tasks:
        groups[task["category"]].append(
            score_expected(task["expected"], frozen_ids[task["id"]])["score"]
        )
    categories = {
        name: {
            "n": len(values),
            "passed": sum(v > 0.999 for v in values),
            "average": sum(values) / len(values),
        }
        for name, values in groups.items()
    }
    scores = [score for values in groups.values() for score in values]
    return {
        "n": len(scores),
        "passed": sum(v > 0.999 for v in scores),
        "raw": sum(scores) / len(scores),
        "weighted": sum(WEIGHTS.get(k, 0) * v["average"] for k, v in categories.items())
        / sum(WEIGHTS.get(k, 0) for k in categories),
        "categories": categories,
    }

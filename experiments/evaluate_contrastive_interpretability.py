from __future__ import annotations

import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from code_search import CHANNELS, CodeSearch
from retrieval_inspection import evidence_ids, replay


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def cutoff(expected):
    kind = expected.get("kind")
    if kind == "exact_symbol":
        return 1
    if kind == "in_top_k":
        return int(expected.get("k", 5))
    return 5


def rank_of(run, candidate_id):
    for row in run["candidates"]:
        if row["id"] == candidate_id:
            return row["rank"]
    return None


def active_signals(route):
    return [
        signal
        for signal in CHANNELS
        if any(
            candidate.get("signals", {}).get(signal, {}).get("weight", 0) != 0
            for candidate in route["candidates"]
        )
    ]


def contrastive_certificate(run, higher_id, lower_id):
    rows = {row["id"]: row for row in run["candidates"]}
    higher = rows[higher_id]
    lower = rows[lower_id]
    signal_rows = {}

    for signal in CHANNELS:
        h = higher.get("signals", {}).get(signal)
        l = lower.get("signals", {}).get(signal)
        if h is None or l is None:
            continue
        signal_rows[signal] = {
            "higher_contribution": h["contribution"],
            "lower_contribution": l["contribution"],
            "margin_contribution": h["contribution"] - l["contribution"],
        }

    margin = higher["score"] - lower["score"]
    reconstructed = sum(
        item["margin_contribution"] for item in signal_rows.values()
    )
    residual = margin - reconstructed

    adverse = sorted(
        (
            (signal, item["margin_contribution"])
            for signal, item in signal_rows.items()
            if item["margin_contribution"] > 1e-12
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    cumulative = 0.0
    minimal_adverse_count = None
    for index, (_, value) in enumerate(adverse, 1):
        cumulative += value
        if cumulative + 1e-12 >= margin:
            minimal_adverse_count = index
            break

    return {
        "higher_id": higher_id,
        "lower_id": lower_id,
        "margin": margin,
        "reconstructed_margin": reconstructed,
        "residual": residual,
        "exact": bool(signal_rows) and abs(residual) <= 1e-10,
        "dominant_adverse_signal": adverse[0][0] if adverse else None,
        "minimal_adverse_signal_count": minimal_adverse_count,
        "signals": signal_rows,
    }


def recovered(run, target_id, k):
    rank = rank_of(run, target_id)
    return rank is not None and rank <= k


def main():
    base = ROOT / "data/code"
    tasks = read(base / "tasks.json")
    documents = read(base / "documents.json")
    projection = read(base / "projection.json")
    recorded = read(base / "recorded_dense_order.json")["rankings"]
    engine = CodeSearch(documents, projection, base / "source")

    rows = []
    counts = Counter()
    task_sets = defaultdict(set)
    by_category = defaultdict(Counter)

    for task in tasks:
        route = engine.route(
            task["query"],
            task["query_text"],
            dense_order=recorded.get(task["id"]),
        )
        baseline = replay(route)
        k = cutoff(task["expected"])
        candidates = {row["id"]: row for row in baseline["candidates"]}

        if len(baseline["candidates"]) < k:
            boundary = None
        else:
            boundary = baseline["candidates"][k - 1]

        for target_id in evidence_ids(task["expected"]):
            if target_id not in candidates:
                counts["candidate_missing"] += 1
                by_category[task["category"]]["candidate_missing"] += 1
                task_sets["candidate_missing"].add(task["id"])
                continue

            if recovered(baseline, target_id, k):
                counts["retrieved"] += 1
                by_category[task["category"]]["retrieved"] += 1
                task_sets["retrieved"].add(task["id"])
                continue

            counts["ranking_loss"] += 1
            by_category[task["category"]]["ranking_loss"] += 1
            task_sets["ranking_loss"].add(task["id"])

            signals = active_signals(route)
            single_recovery = []
            subset_recovery = []

            for size in range(1, len(signals) + 1):
                for disabled in itertools.combinations(signals, size):
                    run = replay(route, disabled=disabled)
                    if recovered(run, target_id, k):
                        subset_recovery.append(list(disabled))
                        if size == 1:
                            single_recovery.append(disabled[0])

            certificate = None
            if boundary is not None:
                certificate = contrastive_certificate(
                    baseline,
                    boundary["id"],
                    target_id,
                )

            exact = bool(certificate and certificate["exact"])

            if single_recovery:
                counts["single_ablation_recovered"] += 1
                by_category[task["category"]]["single_ablation_recovered"] += 1
                task_sets["single_ablation_recovered"].add(task["id"])

            if subset_recovery:
                counts["any_ablation_recovered"] += 1
                by_category[task["category"]]["any_ablation_recovered"] += 1
                task_sets["any_ablation_recovered"].add(task["id"])

            if exact:
                counts["exact_contrastive_certificate"] += 1
                by_category[task["category"]]["exact_contrastive_certificate"] += 1
                task_sets["exact_contrastive_certificate"].add(task["id"])

            if exact and not subset_recovery:
                counts["certificate_on_ablation_resistant"] += 1
                by_category[task["category"]]["certificate_on_ablation_resistant"] += 1
                task_sets["certificate_on_ablation_resistant"].add(task["id"])

            rows.append(
                {
                    "task_id": task["id"],
                    "category": task["category"],
                    "target_id": target_id,
                    "cutoff": k,
                    "target_rank": candidates[target_id]["rank"],
                    "boundary_id": boundary["id"] if boundary else None,
                    "single_ablation_recovery": single_recovery,
                    "any_ablation_recovery": subset_recovery,
                    "certificate": certificate,
                }
            )

    ranking_loss = counts["ranking_loss"]

    summary = {
        "tasks": len(tasks),
        "target_level": {
            "retrieved": counts["retrieved"],
            "candidate_missing": counts["candidate_missing"],
            "ranking_loss": ranking_loss,
            "single_ablation_recovered": counts["single_ablation_recovered"],
            "single_ablation_recovery_rate": (
                counts["single_ablation_recovered"] / ranking_loss
                if ranking_loss
                else None
            ),
            "any_subset_ablation_recovered": counts["any_ablation_recovered"],
            "any_subset_ablation_recovery_rate": (
                counts["any_ablation_recovered"] / ranking_loss
                if ranking_loss
                else None
            ),
            "exact_contrastive_certificate": counts["exact_contrastive_certificate"],
            "exact_contrastive_certificate_rate": (
                counts["exact_contrastive_certificate"] / ranking_loss
                if ranking_loss
                else None
            ),
            "exact_certificate_on_ablation_resistant": counts[
                "certificate_on_ablation_resistant"
            ],
        },
        "task_level_unique_counts": {
            key: len(value) for key, value in sorted(task_sets.items())
        },
        "by_category": {
            category: dict(values)
            for category, values in sorted(by_category.items())
        },
    }

    output = ROOT / "outputs/contrastive_interpretability_eval.json"
    output.write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary["target_level"], indent=2))
    print("\nTask-level unique counts")
    print(json.dumps(summary["task_level_unique_counts"], indent=2))
    print()
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()

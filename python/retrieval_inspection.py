"""Label-free replay over frozen, provenance-carrying retrieval candidates."""

from __future__ import annotations

from typing import Any

from inspectable_memory import digest

SIGNALS = ("structural_order", "bm25", "edge_frequency", "graph_degree", "id_overlap")


def replay(route: dict, *, disabled: tuple[str, ...] = (), limit: int = 5) -> dict:
    """No expected IDs or reader outputs are accepted by the ranking interface."""
    if not set(disabled).issubset(SIGNALS) or not 1 <= limit <= 5:
        raise ValueError("unsupported ranking intervention")
    rows = []
    for position, item in enumerate(route["candidates"]):
        signals = item.get("signals", {})
        score = (
            sum(signal["contribution"] for name, signal in signals.items() if name not in disabled)
            if signals
            else item.get("score", 0.0)
        )
        rows.append({**item, "score": score, "discovery_position": position + 1})
    # Original ranker breaks ties by global corpus order, not discovery order.
    rows.sort(key=lambda r: (-r["score"], r["corpus_order"]))
    top = [item["id"] for item in rows[:limit]]
    return {
        "route": route["route"],
        "disabled": list(disabled),
        "top5": top,
        "candidates": [
            {**row, "rank": i + 1, "selected": row["id"] in top} for i, row in enumerate(rows)
        ],
        "candidate_hash": digest(route["candidates"]),
        "fallback": route.get("fallback", False),
    }


def evidence_ids(expected: dict[str, Any]) -> list[str]:
    """Evaluation only: enumerate explicit labels without guessing absent evidence."""
    kind = expected.get("kind")
    if kind in {"exact_symbol", "in_top_k"}:
        return [expected["stable_id"]] if expected.get("stable_id") else []
    if kind == "exact_set":
        return list(expected.get("stable_ids", []))
    if kind == "contains":
        return list(expected.get("required", []))
    return []


def diagnose_stages(run: dict, expected: dict, reader_ids: list[str] | None = None) -> list[dict]:
    """Post-retrieval inspection only, never used to generate or rank candidates."""
    candidates = {row["id"] for row in run["candidates"]}
    top = set(run["top5"])
    if reader_ids is not None and not set(reader_ids).issubset(top):
        raise ValueError("reader must only reorder/drop this run's frozen top-5")
    rows = []
    for target in evidence_ids(expected):
        if target not in candidates:
            stage = "candidate_missing"
        elif target not in top:
            stage = "ranking_loss"
        elif expected.get("kind") == "exact_symbol" and run["top5"][0] != target:
            stage = "ranking_position_loss"
        elif (
            expected.get("kind") == "in_top_k" and target not in run["top5"][: expected.get("k", 5)]
        ):
            stage = "ranking_position_loss"
        elif reader_ids is not None and target not in reader_ids:
            stage = "reader_drop"
        else:
            stage = "retrieved"
        rows.append({"id": target, "stage": stage})
    return rows

from __future__ import annotations

from typing import Any

from retrieval_inspection import SIGNALS


def contrastive_certificate(
    run: dict[str, Any],
    higher_id: str,
    lower_id: str,
) -> dict[str, Any]:
    if higher_id == lower_id:
        raise ValueError("candidates must differ")

    candidates = {row["id"]: row for row in run["candidates"]}

    if higher_id not in candidates or lower_id not in candidates:
        raise KeyError("candidate not found in run")

    higher = candidates[higher_id]
    lower = candidates[lower_id]
    signal_rows = {}

    for signal in SIGNALS:
        higher_signal = higher.get("signals", {}).get(signal)
        lower_signal = lower.get("signals", {}).get(signal)

        if higher_signal is None or lower_signal is None:
            continue

        signal_rows[signal] = {
            "higher_contribution": higher_signal["contribution"],
            "lower_contribution": lower_signal["contribution"],
            "margin_contribution": (
                higher_signal["contribution"] - lower_signal["contribution"]
            ),
            "higher_rank": higher_signal["rank"],
            "lower_rank": lower_signal["rank"],
            "weight": higher_signal["weight"],
        }

    margin = higher["score"] - lower["score"]
    reconstructed_margin = sum(
        row["margin_contribution"] for row in signal_rows.values()
    )
    residual = margin - reconstructed_margin

    adverse = sorted(
        (
            {
                "signal": signal,
                "margin_contribution": row["margin_contribution"],
            }
            for signal, row in signal_rows.items()
            if row["margin_contribution"] > 1e-12
        ),
        key=lambda row: row["margin_contribution"],
        reverse=True,
    )

    supportive = sorted(
        (
            {
                "signal": signal,
                "margin_contribution": row["margin_contribution"],
            }
            for signal, row in signal_rows.items()
            if row["margin_contribution"] < -1e-12
        ),
        key=lambda row: row["margin_contribution"],
    )

    cumulative = 0.0
    minimal_adverse_signals = []

    for row in adverse:
        cumulative += row["margin_contribution"]
        minimal_adverse_signals.append(row["signal"])
        if cumulative + 1e-12 >= margin:
            break
    else:
        minimal_adverse_signals = []

    return {
        "higher_id": higher_id,
        "lower_id": lower_id,
        "higher_rank": higher["rank"],
        "lower_rank": lower["rank"],
        "margin": margin,
        "reconstructed_margin": reconstructed_margin,
        "residual": residual,
        "exact": bool(signal_rows) and abs(residual) <= 1e-10,
        "dominant_adverse_signal": adverse[0]["signal"] if adverse else None,
        "minimal_adverse_signals": minimal_adverse_signals,
        "adverse_signals": adverse,
        "supportive_signals": supportive,
        "signals": signal_rows,
    }


def boundary_certificate(
    run: dict[str, Any],
    limit: int = 5,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be positive")

    rows = sorted(run["candidates"], key=lambda row: row["rank"])

    if len(rows) <= limit:
        return {
            "available": False,
            "limit": limit,
            "reason": "no rejected boundary candidate",
        }

    certificate = contrastive_certificate(
        run,
        rows[limit - 1]["id"],
        rows[limit]["id"],
    )

    return {
        "available": True,
        "limit": limit,
        **certificate,
    }

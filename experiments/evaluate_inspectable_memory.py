"""Controlled temporal ablation; not an official LongMemCode score."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from inspectable_demo import DEMO_SCOPE, KNOWLEDGE, DemoService  # noqa: E402
from inspectable_memory import MODES  # noqa: E402


def percentile(values, q):
    ordered = sorted(values)
    return ordered[max(0, __import__("math").ceil(q * len(ordered)) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/results/inspectable_memory_evaluation.json",
    )
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory(prefix="inspectable-eval-") as directory:
        service = DemoService(
            ROOT / "demo/inspectable/fixture.json", Path(directory) / "memory.sqlite"
        )
        for case in service.temporal.values():
            all_facts = service.memory.recall(
                at=1,
                known_at=KNOWLEDGE[2],
                scope=DEMO_SCOPE,
                entity=case["entity"],
                mode="baseline",
            )["facts"]
            old = next(f["id"] for f in all_facts if f["value"] == case["original"])
            new = next(f["id"] for f in all_facts if f["value"] == case["changed"])
            # Independent oracle from the authored event schedule, not from rule outputs.
            situations = [
                ("original_knowledge", 0, 0, {old}, False),
                ("future_fact_not_yet_valid", 0, 1, {old}, False),
                ("unresolved_overlap", 1, 1, {old, new}, True),
                ("resolved_current", 1, 2, {new}, False),
                ("resolved_historical", 0, 2, {old}, False),
                ("later_snapshot", 2, 2, {new}, False),
            ]
            for name, at, knowledge, expected_ids, expected_conflict in situations:
                for mode in sorted(MODES):
                    result = service.memory.recall(
                        at=at,
                        known_at=KNOWLEDGE[knowledge],
                        scope=DEMO_SCOPE,
                        entity=case["entity"],
                        mode=mode,
                        use_cache=False,
                    )
                    selected = set(result["selected_ids"])
                    rows.append(
                        {
                            "case": case["id"],
                            "benchmark_source": case["benchmark_task"],
                            "situation": name,
                            "mode": mode,
                            "expected_conflict": expected_conflict,
                            "detected_conflict": bool(result["conflicts"]),
                            "selection_correct": selected == expected_ids,
                            "selection_precision": len(selected & expected_ids)
                            / len(selected)
                            if selected
                            else 0,
                            "selection_recall": len(selected & expected_ids)
                            / len(expected_ids),
                            "latency_ms": result["latency_ms"],
                        }
                    )
        timings = {}
        example = next(iter(service.temporal.values()))
        for cache in (False, True):
            values = []
            for _ in range(120):
                r = service.memory.recall(
                    at=1,
                    known_at=KNOWLEDGE[2],
                    scope=DEMO_SCOPE,
                    entity=example["entity"],
                    use_cache=cache,
                )
                values.append(r["latency_ms"])
            timings["cached" if cache else "uncached"] = {
                "n": 119,
                "p50_ms": statistics.median(values[1:]),
                "p95_ms": percentile(values[1:], 0.95),
            }
        summaries = {}
        for mode in sorted(MODES):
            selected_rows = [r for r in rows if r["mode"] == mode]
            tp = sum(
                r["expected_conflict"] and r["detected_conflict"] for r in selected_rows
            )
            fp = sum(
                not r["expected_conflict"] and r["detected_conflict"]
                for r in selected_rows
            )
            fn = sum(
                r["expected_conflict"] and not r["detected_conflict"]
                for r in selected_rows
            )
            summaries[mode] = {
                "n": len(selected_rows),
                "selection_exact": sum(r["selection_correct"] for r in selected_rows),
                "conflict_tp": tp,
                "conflict_fp": fp,
                "conflict_fn": fn,
                "conflict_precision": tp / (tp + fp) if tp + fp else None,
                "conflict_recall": tp / (tp + fn) if tp + fn else None,
            }
        report = {
            "protocol": "Controlled temporal extension, NOT official LongMemCode",
            "limitations": "Six source-derived entities, six authored states each; correctness checks, not a held-out research benchmark.",
            "fixture_hash": service.fixture["content_hash"],
            "source_validation": service.fixture["validation"],
            "model_calls": 0,
            "model": None,
            "machine": platform.platform(),
            "python": platform.python_version(),
            "summary": summaries,
            "timings": timings,
            "rows": rows,
        }
        service.memory.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {"summary": summaries, "timings": timings, "output": str(args.output)}
        )
    )


if __name__ == "__main__":
    main()

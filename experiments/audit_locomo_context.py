"""Post-retrieval paired audit; never imported by conversation ranking."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from audit_locomo_memory import clustered_interval
from locomo_context_eval import ROOT, read_json, sha256, verify, write_json

from conversation_memory import ConversationMemory, terms


def audit(dataset: Path, output: Path, baseline: Path) -> dict:
    verify(dataset, output)
    data = read_json(dataset)
    saved = read_json(output / "retrieval.json")
    report = read_json(output / "results.json")
    old = read_json(baseline / "retrieval.json")
    indexed = {(r["question_id"], r["profile"]): r for r in saved["rows"]}
    expected = {
        (r["question_id"], r["profile"]): r
        for r in old["rows"]
        if r["profile"] in {"bm25", "guarded"}
    }
    actual_controls = {key for key in indexed if key[1] in {"bm25", "guarded"}}
    if actual_controls != set(expected):
        raise ValueError("control question set changed")
    for key, row in expected.items():
        if any(
            indexed[key][field] != row[field]
            for field in ("question", "ids", "hits", "index_hash")
        ):
            raise ValueError(f"frozen control changed: {key}")
    memories = {
        s["sample_id"]: ConversationMemory(s["sample_id"], s["conversation"])
        for s in data
    }
    scored = {(r["question_id"], r["profile"]): r for r in report["rows"]}
    selected = "bridge_calendar"
    wins = report["paired"]["guarded"][selected]["hit_at_5"]["win_ids"]
    by_category = {}
    for qid in wins:
        by_category.setdefault(scored[qid, selected]["category"], []).append(qid)
    example_ids = [
        qid for category in sorted(by_category) for qid in by_category[category][:3]
    ]
    examples = []
    for qid in example_ids:
        row = scored[qid, selected]
        question = indexed[qid, selected]["question"]
        memory = memories[row["conversation"]]
        hits = indexed[qid, selected]["hits"]
        extra = set(row["ids"]) - set(indexed[qid, "guarded"]["ids"])
        anchors = {h["bridge"]["anchor"] for h in hits if h.get("bridge")}
        sources = sorted(extra | anchors | set(row["evidence_ids"]))
        examples.append(
            {
                "question_id": qid,
                "question": question,
                "category": row["category"],
                "evidence_ids": row["evidence_ids"],
                "guarded_ids": indexed[qid, "guarded"]["ids"],
                "selected_ids": row["ids"],
                "trace": hits,
                "sources": {
                    eid: {
                        "speaker": memory.by_id[eid].speaker,
                        "text": memory.by_id[eid].text,
                        "time": memory.by_id[eid].source_time,
                    }
                    for eid in sources
                    if eid in memory.by_id
                },
            }
        )
    lures = {"new_lure_ids": [], "removed_lure_ids": [], "unchanged": 0}
    residual = Counter()
    residual_examples = []
    for row in report["rows"]:
        if row["profile"] != selected:
            continue
        qid = row["question_id"]
        before = scored[qid, "guarded"]
        if row["lure"] is not None:
            delta = row["lure"] - before["lure"]
            if delta:
                lures["new_lure_ids" if delta > 0 else "removed_lure_ids"].append(qid)
            else:
                lures["unchanged"] += 1
        if row["metrics"] is None or row["metrics"]["hit_at_5"]:
            continue
        residual["misses"] += 1
        memory = memories[row["conversation"]]
        positions = {episode.id: i for i, episode in enumerate(memory.episodes)}
        gold = [memory.by_id[eid] for eid in row["evidence_ids"] if eid in memory.by_id]
        if len(gold) < len(row["evidence_ids"]):
            residual["contains_missing_annotation_id"] += 1
        near = any(
            e.session == memory.by_id[rid].session
            and abs(positions[e.id] - positions[rid]) <= 2
            for e in gold
            for rid in row["ids"]
        )
        if near:
            residual["evidence_within_two_turns_of_top5"] += 1
        query_terms = set(terms(indexed[qid, selected]["question"])) - {
            t for name in memory.people for t in terms(name)
        }
        if gold and not any(query_terms & set(terms(e.text)) for e in gold):
            residual["no_query_content_term_in_any_evidence"] += 1
        if len(residual_examples) < 12:
            residual_examples.append(
                {
                    "question_id": qid,
                    "question": indexed[qid, selected]["question"],
                    "evidence_within_two_turns": near,
                    "evidence_ids": row["evidence_ids"],
                    "selected_ids": row["ids"],
                }
            )
    return {
        "results_sha256": sha256(output / "results.json"),
        "audit_source_sha256": sha256(Path(__file__)),
        "baseline_retrieval_sha256": sha256(baseline / "retrieval.json"),
        "verified_controls": len(expected),
        "selected_profile": selected,
        "selection_note": "rules, thresholds and profile selected after inspecting the same ten conversations; descriptive bootstrap does not correct selection bias",
        "clustered_intervals": [
            clustered_interval(report["rows"], before, selected, metric)
            for before in ("bm25", "guarded")
            for metric in ("hit_at_5", "recall_at_5", "mrr_at_5")
        ],
        "wins_by_category_vs_guarded": {
            str(cat): len(ids) for cat, ids in by_category.items()
        },
        "lure_changes_vs_guarded": lures,
        "remaining_errors_overlapping_diagnostics": dict(residual),
        "win_examples": examples,
        "residual_examples": residual_examples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "external/locomo/locomo10.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "experiments/results/locomo_guarded_v7_2026-09-09",
    )
    args = parser.parse_args()
    result = audit(args.dataset, args.output, args.baseline)
    write_json(args.output / "audit.json", result)
    print(
        {
            key: result[key]
            for key in (
                "verified_controls",
                "wins_by_category_vs_guarded",
                "lure_changes_vs_guarded",
                "remaining_errors_overlapping_diagnostics",
            )
        }
    )


if __name__ == "__main__":
    main()

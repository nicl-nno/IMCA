#!/usr/bin/env python3

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


POLICIES = [
    "flat_bm25",
    "strict_temporal",
    "query_aware",
    "transition_aware",
    "before_aware",
]

BASELINE = "strict_temporal"


def normalize(text):
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def load_jsonl(path):
    rows = []

    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def score_policy(case, policy):
    retrieved = case["retrieval_outputs"][policy]

    retrieved_text = {
        normalize(item["text"])
        for item in retrieved
    }

    evidence = {
        normalize(item)
        for item in case["reference_evidence"]
    }

    hits = len(retrieved_text & evidence)

    hit5 = int(hits > 0)

    recall5 = (
        hits / len(evidence)
        if evidence
        else 1.0
    )

    stale_slots = sum(
        not item["active_at_question_time"]
        for item in retrieved
    )

    has_out_of_slice = stale_slots > 0

    return {
        "hit5": hit5,
        "recall5": recall5,
        "stale_slots": stale_slots,
        "has_out_of_slice": has_out_of_slice,
        "expected_count": len(evidence),
        "matched_evidence_count": hits,
    }


def summarize_case_rows(rows):
    if not rows:
        return {
            "n": 0,
            "hit5": None,
            "recall5": None,
            "stale_slots": 0,
            "cases_with_out_of_slice": 0,
            "out_of_slice_case_rate": None,
        }

    n = len(rows)

    return {
        "n": n,
        "hit5": sum(
            row["hit5"]
            for row in rows
        ) / n,
        "recall5": sum(
            row["recall5"]
            for row in rows
        ) / n,
        "stale_slots": sum(
            row["stale_slots"]
            for row in rows
        ),
        "cases_with_out_of_slice": sum(
            row["has_out_of_slice"]
            for row in rows
        ),
        "out_of_slice_case_rate": sum(
            row["has_out_of_slice"]
            for row in rows
        ) / n,
    }


def paired_against_baseline(case_scores, policy):
    wins = 0
    losses = 0
    ties = 0

    recall_wins = 0
    recall_losses = 0
    recall_ties = 0

    for case_id, scores in case_scores.items():
        baseline = scores[BASELINE]
        candidate = scores[policy]

        if candidate["hit5"] > baseline["hit5"]:
            wins += 1
        elif candidate["hit5"] < baseline["hit5"]:
            losses += 1
        else:
            ties += 1

        if candidate["recall5"] > baseline["recall5"]:
            recall_wins += 1
        elif candidate["recall5"] < baseline["recall5"]:
            recall_losses += 1
        else:
            recall_ties += 1

    return {
        "hit5_wins": wins,
        "hit5_losses": losses,
        "hit5_ties": ties,
        "recall5_wins": recall_wins,
        "recall5_losses": recall_losses,
        "recall5_ties": recall_ties,
    }


def group_cases(cases, predicate):
    return [
        case
        for case in cases
        if predicate(case)
    ]


def evaluate_subset(cases):
    per_policy = {}
    case_scores = {}

    for case in cases:
        case_id = case["case_id"]
        case_scores[case_id] = {}

        for policy in POLICIES:
            case_scores[case_id][policy] = score_policy(
                case,
                policy,
            )

    for policy in POLICIES:
        rows = [
            case_scores[case["case_id"]][policy]
            for case in cases
        ]

        per_policy[policy] = summarize_case_rows(rows)

        if policy != BASELINE:
            per_policy[policy]["vs_strict_temporal"] = (
                paired_against_baseline(
                    case_scores,
                    policy,
                )
            )

    return {
        "n": len(cases),
        "policies": per_policy,
    }


def pct(value):
    if value is None:
        return "n/a"
    return f"{100 * value:.2f}%"


def render_policy_table(title, summary):
    lines = []

    lines.append(f"## {title}")
    lines.append("")
    lines.append(
        "| Policy | N | Hit@5 | Recall@5 | "
        "Out-of-slice slots | Cases with out-of-slice |"
    )
    lines.append(
        "|---|---:|---:|---:|---:|---:|"
    )

    for policy in POLICIES:
        row = summary["policies"][policy]

        lines.append(
            f"| `{policy}` "
            f"| {row['n']} "
            f"| {pct(row['hit5'])} "
            f"| {pct(row['recall5'])} "
            f"| {row['stale_slots']} "
            f"| {row['cases_with_out_of_slice']} "
            f"({pct(row['out_of_slice_case_rate'])}) |"
        )

    lines.append("")

    lines.append("### Paired comparison vs strict temporal")
    lines.append("")
    lines.append(
        "| Policy | Hit wins | Hit losses | Hit ties | "
        "Recall wins | Recall losses | Recall ties |"
    )
    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|"
    )

    for policy in POLICIES:
        if policy == BASELINE:
            continue

        paired = summary["policies"][policy][
            "vs_strict_temporal"
        ]

        lines.append(
            f"| `{policy}` "
            f"| {paired['hit5_wins']} "
            f"| {paired['hit5_losses']} "
            f"| {paired['hit5_ties']} "
            f"| {paired['recall5_wins']} "
            f"| {paired['recall5_losses']} "
            f"| {paired['recall5_ties']} |"
        )

    lines.append("")

    return lines


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        default="results/autojudge_consistency_cases.jsonl",
    )

    parser.add_argument(
        "--json-output",
        default="results/consistency-policy-comparison.json",
    )

    parser.add_argument(
        "--markdown-output",
        default="docs/consistency-policy-comparison.md",
    )

    args = parser.parse_args()

    cases = load_jsonl(args.input)

    if not cases:
        raise RuntimeError("No cases loaded")

    missing_policies = []

    for case in cases:
        for policy in POLICIES:
            if policy not in case["retrieval_outputs"]:
                missing_policies.append(
                    (case["case_id"], policy)
                )

    if missing_policies:
        raise RuntimeError(
            f"Missing policies: {missing_policies}"
        )

    subsets = {
        "overall_27_error_cases": cases,

        "transition_or_retrospective": group_cases(
            cases,
            lambda case:
                case["diagnostic_signals"]["query_group"]
                == "transition_or_retrospective",
        ),

        "state_at_time": group_cases(
            cases,
            lambda case:
                case["diagnostic_signals"]["query_group"]
                == "state_at_time",
        ),

        "evidence_after_question_time": group_cases(
            cases,
            lambda case:
                case["diagnostic_signals"][
                    "evidence_after_question_time"
                ],
        ),

        "evidence_not_after_question_time": group_cases(
            cases,
            lambda case:
                not case["diagnostic_signals"][
                    "evidence_after_question_time"
                ],
        ),

        "evidence_expired": group_cases(
            cases,
            lambda case:
                case["diagnostic_signals"][
                    "evidence_expired"
                ],
        ),

        "zero_length_interval": group_cases(
            cases,
            lambda case:
                case["diagnostic_signals"][
                    "zero_length_interval"
                ],
        ),
    }

    report = {
        "scope": (
            "Matched-condition comparison over the 27 "
            "selected HaluMem Memory Conflict error cases"
        ),
        "benchmark": "HaluMem-Medium",
        "subset": "Memory Conflict",
        "case_count": len(cases),
        "policies": POLICIES,
        "baseline": BASELINE,
        "subsets": {
            name: evaluate_subset(rows)
            for name, rows in subsets.items()
        },
    }

    json_output = Path(args.json_output)
    md_output = Path(args.markdown_output)

    json_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    md_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_output.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = []

    lines.append(
        "# Matched-condition consistency policy comparison"
    )
    lines.append("")

    lines.append(
        "This report compares five retrieval policies on the same "
        "27 selected HaluMem-Medium `Memory Conflict` cases."
    )
    lines.append("")

    lines.append(
        "All policies use the same question, memory corpus, BM25 "
        "index and top-k=5 retrieval budget. Only the temporal "
        "retrieval policy differs."
    )
    lines.append("")

    lines.append(
        "These 27 cases were selected because flat BM25 previously "
        "retrieved benchmark evidence that strict temporal retrieval "
        "missed. Therefore this is an error-analysis subset, not an "
        "unbiased estimate over all HaluMem questions."
    )
    lines.append("")

    ordered_sections = [
        (
            "Overall: 27 selected error cases",
            "overall_27_error_cases",
        ),
        (
            "Transition / retrospective questions",
            "transition_or_retrospective",
        ),
        (
            "State-at-time questions",
            "state_at_time",
        ),
        (
            "Reference evidence after interpreted question time",
            "evidence_after_question_time",
        ),
        (
            "Reference evidence not after interpreted question time",
            "evidence_not_after_question_time",
        ),
        (
            "Expired reference evidence",
            "evidence_expired",
        ),
        (
            "Zero-length validity interval",
            "zero_length_interval",
        ),
    ]

    for title, key in ordered_sections:
        lines.extend(
            render_policy_table(
                title,
                report["subsets"][key],
            )
        )

    lines.append("## Interpretation boundary")
    lines.append("")

    lines.append(
        "This deterministic analysis measures retrieval of benchmark "
        "reference evidence and temporal validity of retrieved slots. "
        "It does not by itself determine whether the retrieved context "
        "contains a true semantic contradiction, whether an out-of-slice "
        "fact is useful rather than harmful, or whether the answer can "
        "still be inferred without the benchmark reference evidence."
    )
    lines.append("")

    lines.append(
        "Those properties require the separate consistency / "
        "evidence-vs-inference evaluation."
    )
    lines.append("")

    md_output.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("cases:", len(cases))

    for name, subset in report["subsets"].items():
        print()
        print("===", name, "===")
        print("n:", subset["n"])

        for policy in POLICIES:
            row = subset["policies"][policy]

            print(
                f"{policy:20s} "
                f"hit5={row['hit5']!s:8s} "
                f"recall5={row['recall5']!s:8s} "
                f"stale={row['stale_slots']}"
            )

    print()
    print("saved:", json_output)
    print("saved:", md_output)


if __name__ == "__main__":
    main()

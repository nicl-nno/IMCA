#!/usr/bin/env python3

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def expected_ids(expected):
    kind = expected.get("kind")

    if kind in ("exact_symbol", "in_top_k"):
        stable_id = expected.get("stable_id")
        return [stable_id] if stable_id else []

    if kind == "contains":
        return list(expected.get("required", []))

    if kind == "exact_set":
        return list(expected.get("stable_ids", []))

    return []


def anchor_type(query):
    if "file_path" in query:
        return "file"

    stable_id = query.get("sym_stable_id")

    if stable_id:
        if stable_id.startswith("file:"):
            return "file"
        return "symbol"

    if query.get("name"):
        return "symbol"

    if query.get("kind"):
        return "kind"

    return "other"


def count_expected_hits(expected, returned):
    wanted = set(expected_ids(expected))
    actual = set(returned)
    return len(wanted & actual)


def unmapped_count(returned):
    return sum(
        isinstance(item, str)
        and item.startswith("unmapped-native:")
        for item in returned
    )


def analyze_group(group):
    # Comparable groups have one expected answer and identical
    # retrieval behaviour for identical inputs, so inspecting
    # the first row is sufficient for structural diagnostics.
    row = group["rows"][0]

    expected = expected_ids(row["expected"])

    imca = row["imca_results"]
    codebase = row["codebase_results"]

    return {
        "task_ids": group["task_ids"],
        "operation": group["operation"],
        "direction": group["direction"],
        "anchor_type": anchor_type(group["query"]),
        "query": group["query"],
        "query_text": group["query_text"],
        "expected_count": len(expected),
        "imca_score": row["imca_score"],
        "codebase_score": row["codebase_score"],
        "imca_result_count": len(imca),
        "codebase_result_count": len(codebase),
        "imca_expected_hits": count_expected_hits(
            row["expected"], imca
        ),
        "codebase_expected_hits": count_expected_hits(
            row["expected"], codebase
        ),
        "imca_empty": len(imca) == 0,
        "codebase_empty": len(codebase) == 0,
        "codebase_unmapped_count": unmapped_count(codebase),
        "imca_results": imca,
        "codebase_results": codebase,
        "expected": row["expected"],
    }


def summarize(rows):
    return {
        "n": len(rows),
        "operations": dict(
            Counter(row["operation"] for row in rows)
        ),
        "anchor_types": dict(
            Counter(row["anchor_type"] for row in rows)
        ),
        "imca_empty": sum(row["imca_empty"] for row in rows),
        "codebase_empty": sum(
            row["codebase_empty"] for row in rows
        ),
        "codebase_with_unmapped_native": sum(
            row["codebase_unmapped_count"] > 0
            for row in rows
        ),
        "codebase_unmapped_native_occurrences": sum(
            row["codebase_unmapped_count"]
            for row in rows
        ),
        "mean_imca_expected_hits": (
            sum(row["imca_expected_hits"] for row in rows)
            / len(rows)
            if rows
            else 0.0
        ),
        "mean_codebase_expected_hits": (
            sum(row["codebase_expected_hits"] for row in rows)
            / len(rows)
            if rows
            else 0.0
        ),
        "mean_expected_count": (
            sum(row["expected_count"] for row in rows)
            / len(rows)
            if rows
            else 0.0
        ),
    }


def render_markdown(imca_rows, codebase_rows):
    imca_summary = summarize(imca_rows)
    codebase_summary = summarize(codebase_rows)

    lines = []

    lines.append(
        "# IMCA vs Codebase-Memory disagreement cause analysis"
    )
    lines.append("")

    lines.append(
        "This analysis uses only the 327 comparable unique inputs "
        "from the frozen LongMemCode retrieval comparison. "
        "The ambiguous repeated `orphans` input is excluded."
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")

    lines.append(
        f"- Comparable disagreements: "
        f"{len(imca_rows) + len(codebase_rows)}"
    )
    lines.append(
        f"- IMCA higher: {len(imca_rows)}"
    )
    lines.append(
        f"- Codebase-Memory higher: {len(codebase_rows)}"
    )
    lines.append("")

    lines.append("## IMCA-higher cases")
    lines.append("")

    lines.append(
        f"- Cases: {imca_summary['n']}"
    )
    lines.append(
        f"- Operations: {imca_summary['operations']}"
    )
    lines.append(
        f"- Anchor types: {imca_summary['anchor_types']}"
    )
    lines.append(
        f"- Codebase-Memory empty result: "
        f"{imca_summary['codebase_empty']}"
    )
    lines.append(
        f"- Codebase-Memory result contains "
        f"`unmapped-native`: "
        f"{imca_summary['codebase_with_unmapped_native']}"
    )
    lines.append(
        f"- Total `unmapped-native` occurrences: "
        f"{imca_summary['codebase_unmapped_native_occurrences']}"
    )
    lines.append(
        f"- Mean expected targets per case: "
        f"{imca_summary['mean_expected_count']:.2f}"
    )
    lines.append(
        f"- Mean expected targets found by IMCA: "
        f"{imca_summary['mean_imca_expected_hits']:.2f}"
    )
    lines.append(
        f"- Mean expected targets found by Codebase-Memory: "
        f"{imca_summary['mean_codebase_expected_hits']:.2f}"
    )
    lines.append("")

    lines.append("## Codebase-Memory-higher cases")
    lines.append("")

    lines.append(
        f"- Cases: {codebase_summary['n']}"
    )
    lines.append(
        f"- Operations: {codebase_summary['operations']}"
    )
    lines.append(
        f"- Anchor types: {codebase_summary['anchor_types']}"
    )
    lines.append(
        f"- IMCA empty result: "
        f"{codebase_summary['imca_empty']}"
    )
    lines.append(
        f"- Codebase-Memory result contains "
        f"`unmapped-native`: "
        f"{codebase_summary['codebase_with_unmapped_native']}"
    )
    lines.append(
        f"- Total `unmapped-native` occurrences: "
        f"{codebase_summary['codebase_unmapped_native_occurrences']}"
    )
    lines.append(
        f"- Mean expected targets per case: "
        f"{codebase_summary['mean_expected_count']:.2f}"
    )
    lines.append(
        f"- Mean expected targets found by IMCA: "
        f"{codebase_summary['mean_imca_expected_hits']:.2f}"
    )
    lines.append(
        f"- Mean expected targets found by Codebase-Memory: "
        f"{codebase_summary['mean_codebase_expected_hits']:.2f}"
    )
    lines.append("")

    lines.append("## Detailed IMCA-higher cases")
    lines.append("")

    for row in imca_rows:
        lines.append(
            f"### {', '.join(row['task_ids'])}"
        )
        lines.append("")
        lines.append(
            f"- Operation: `{row['operation']}`"
        )
        lines.append(
            f"- Anchor type: `{row['anchor_type']}`"
        )
        lines.append(
            f"- IMCA score: {row['imca_score']}"
        )
        lines.append(
            f"- Codebase-Memory score: "
            f"{row['codebase_score']}"
        )
        lines.append(
            f"- Expected targets: {row['expected_count']}"
        )
        lines.append(
            f"- Expected targets found by IMCA: "
            f"{row['imca_expected_hits']}"
        )
        lines.append(
            f"- Expected targets found by Codebase-Memory: "
            f"{row['codebase_expected_hits']}"
        )
        lines.append(
            f"- Codebase-Memory empty: "
            f"{row['codebase_empty']}"
        )
        lines.append(
            f"- Codebase-Memory unmapped-native count: "
            f"{row['codebase_unmapped_count']}"
        )
        lines.append("")

    lines.append(
        "## Detailed Codebase-Memory-higher cases"
    )
    lines.append("")

    for row in codebase_rows:
        lines.append(
            f"### {', '.join(row['task_ids'])}"
        )
        lines.append("")
        lines.append(
            f"- Operation: `{row['operation']}`"
        )
        lines.append(
            f"- Anchor type: `{row['anchor_type']}`"
        )
        lines.append(
            f"- IMCA score: {row['imca_score']}"
        )
        lines.append(
            f"- Codebase-Memory score: "
            f"{row['codebase_score']}"
        )
        lines.append(
            f"- Expected targets: {row['expected_count']}"
        )
        lines.append(
            f"- Expected targets found by IMCA: "
            f"{row['imca_expected_hits']}"
        )
        lines.append(
            f"- Expected targets found by Codebase-Memory: "
            f"{row['codebase_expected_hits']}"
        )
        lines.append(
            f"- IMCA empty: {row['imca_empty']}"
        )
        lines.append(
            f"- Codebase-Memory unmapped-native count: "
            f"{row['codebase_unmapped_count']}"
        )
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        default="results/memory-retrieval-disagreements.json",
    )

    parser.add_argument(
        "--json-output",
        default=(
            "results/"
            "memory-retrieval-disagreement-causes.json"
        ),
    )

    parser.add_argument(
        "--markdown-output",
        default=(
            "docs/"
            "memory-retrieval-disagreement-causes.md"
        ),
    )

    args = parser.parse_args()

    data = load(args.input)

    groups = data["comparable_unique_groups"]

    disagreements = [
        analyze_group(group)
        for group in groups
        if group["direction"]
        in ("imca_higher", "codebase_higher")
    ]

    imca_rows = [
        row
        for row in disagreements
        if row["direction"] == "imca_higher"
    ]

    codebase_rows = [
        row
        for row in disagreements
        if row["direction"] == "codebase_higher"
    ]

    result = {
        "scope": (
            "Comparable unique-input disagreements "
            "from frozen LongMemCode retrieval results"
        ),
        "disagreement_count": len(disagreements),
        "imca_higher": {
            "summary": summarize(imca_rows),
            "cases": imca_rows,
        },
        "codebase_higher": {
            "summary": summarize(codebase_rows),
            "cases": codebase_rows,
        },
    }

    json_output = Path(args.json_output)
    markdown_output = Path(args.markdown_output)

    json_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    markdown_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_output.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    markdown_output.write_text(
        render_markdown(
            imca_rows,
            codebase_rows,
        ),
        encoding="utf-8",
    )

    print("disagreements:", len(disagreements))
    print()

    print("=== IMCA HIGHER ===")
    print(
        json.dumps(
            result["imca_higher"]["summary"],
            indent=2,
            ensure_ascii=False,
        )
    )

    print()

    print("=== CODEBASE-MEMORY HIGHER ===")
    print(
        json.dumps(
            result["codebase_higher"]["summary"],
            indent=2,
            ensure_ascii=False,
        )
    )

    print()
    print("saved:", json_output)
    print("saved:", markdown_output)


if __name__ == "__main__":
    main()

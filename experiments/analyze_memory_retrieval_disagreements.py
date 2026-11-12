#!/usr/bin/env python3

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


IMCA = "imca_fresh_source"
CODEBASE = "codebase_memory_structural_adapter"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def score_expected(expected, returned):
    kind = expected.get("kind")
    target = expected.get("stable_id")

    if kind == "exact_symbol":
        return float(bool(returned) and returned[0] == target)

    if kind == "in_top_k":
        return float(target in returned[: int(expected.get("k", 5))])

    actual = set(returned)

    if kind == "contains":
        needed = expected.get("required", [])
        return (
            sum(item in actual for item in needed) / len(needed)
            if needed
            else 1.0
        )

    if kind == "exact_set":
        wanted = set(expected.get("stable_ids", []))

        if not wanted and not actual:
            return 1.0

        overlap = len(actual & wanted)

        return (
            2 * overlap / (len(actual) + len(wanted))
            if (actual or wanted)
            else 1.0
        )

    return 0.0


def direction(imca_score, codebase_score):
    if imca_score > codebase_score:
        return "imca_higher"

    if codebase_score > imca_score:
        return "codebase_higher"

    return "equal"


def full_score_status(imca_score, codebase_score):
    imca_pass = imca_score > 0.999
    codebase_pass = codebase_score > 0.999

    if imca_pass and not codebase_pass:
        return "only_imca"

    if codebase_pass and not imca_pass:
        return "only_codebase"

    if imca_pass and codebase_pass:
        return "both_pass"

    return "neither_pass"


def make_row(task, predictions):
    task_id = task["id"]

    imca_result = predictions[IMCA][task_id]
    codebase_result = predictions[CODEBASE][task_id]

    imca_score = score_expected(
        task["expected"],
        imca_result,
    )

    codebase_score = score_expected(
        task["expected"],
        codebase_result,
    )

    return {
        "id": task_id,
        "category": task["category"],
        "operation": task["query"]["op"],
        "query": task["query"],
        "query_text": task.get("query_text"),
        "expected": task["expected"],
        "imca_score": imca_score,
        "codebase_score": codebase_score,
        "direction": direction(
            imca_score,
            codebase_score,
        ),
        "full_score_status": full_score_status(
            imca_score,
            codebase_score,
        ),
        "imca_results": imca_result,
        "codebase_results": codebase_result,
    }


def input_key(task):
    return json.dumps(
        {
            "query": task["query"],
            "query_text": task.get("query_text"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def expected_key(expected):
    return json.dumps(
        expected,
        sort_keys=True,
        ensure_ascii=False,
    )


def summarize_unique_groups(tasks, rows):
    by_id = {row["id"]: row for row in rows}

    groups = defaultdict(list)

    for task in tasks:
        groups[input_key(task)].append(
            by_id[task["id"]]
        )

    comparable = []
    ambiguous = []

    for members in groups.values():
        first = members[0]

        expected_values = {
            expected_key(row["expected"])
            for row in members
        }

        directions = sorted(
            {row["direction"] for row in members}
        )

        full_statuses = sorted(
            {
                row["full_score_status"]
                for row in members
            }
        )

        group = {
            "query": first["query"],
            "query_text": first["query_text"],
            "operation": first["operation"],
            "task_ids": [
                row["id"]
                for row in members
            ],
            "task_count": len(members),
            "categories": sorted(
                {
                    row["category"]
                    for row in members
                }
            ),
            "distinct_expected_count": len(
                expected_values
            ),
            "rows": members,
        }

        if len(expected_values) > 1:
            group["status"] = (
                "ambiguous_expected_group"
            )
            group["directions"] = directions
            group["full_score_statuses"] = (
                full_statuses
            )

            ambiguous.append(group)
            continue

        group["status"] = "comparable"

        if len(directions) != 1:
            raise ValueError(
                "Comparable identical inputs produced "
                "different score directions"
            )

        if len(full_statuses) != 1:
            raise ValueError(
                "Comparable identical inputs produced "
                "different full-score statuses"
            )

        group["direction"] = directions[0]
        group["full_score_status"] = (
            full_statuses[0]
        )

        comparable.append(group)

    return comparable, ambiguous


def count_field(rows, field):
    return dict(
        Counter(
            row[field]
            for row in rows
        )
    )


def format_counter(counter):
    if not counter:
        return "none"

    return ", ".join(
        f"{key}: {value}"
        for key, value in sorted(
            counter.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )
    )


def render_markdown(
    task_rows,
    comparable_groups,
    ambiguous_groups,
):
    task_direction = Counter(
        row["direction"]
        for row in task_rows
    )

    task_full = Counter(
        row["full_score_status"]
        for row in task_rows
    )

    group_direction = Counter(
        row["direction"]
        for row in comparable_groups
    )

    group_full = Counter(
        row["full_score_status"]
        for row in comparable_groups
    )

    imca_unique = [
        row
        for row in comparable_groups
        if row["direction"] == "imca_higher"
    ]

    codebase_unique = [
        row
        for row in comparable_groups
        if row["direction"] == "codebase_higher"
    ]

    only_imca_unique = [
        row
        for row in comparable_groups
        if row["full_score_status"]
        == "only_imca"
    ]

    only_codebase_unique = [
        row
        for row in comparable_groups
        if row["full_score_status"]
        == "only_codebase"
    ]

    lines = []

    lines.append(
        "# IMCA vs Codebase-Memory retrieval disagreements"
    )
    lines.append("")

    lines.append(
        "This analysis reuses the frozen retrieval "
        "predictions from the existing LongMemCode "
        "comparison and does not rerun either memory "
        "system."
    )
    lines.append("")

    lines.append(
        "The original benchmark-level results are "
        "reported separately from the unique-input "
        "analysis. Repeated inputs with different "
        "expected answers are treated as ambiguous "
        "groups rather than independent comparable "
        "inputs."
    )
    lines.append("")

    lines.append("## Task-level results")
    lines.append("")

    lines.append(
        f"- Tasks: {len(task_rows)}"
    )
    lines.append(
        f"- IMCA higher score: "
        f"{task_direction['imca_higher']}"
    )
    lines.append(
        f"- Codebase-Memory higher score: "
        f"{task_direction['codebase_higher']}"
    )
    lines.append(
        f"- Equal score: "
        f"{task_direction['equal']}"
    )
    lines.append("")

    lines.append(
        f"- Only IMCA full score: "
        f"{task_full['only_imca']}"
    )
    lines.append(
        f"- Only Codebase-Memory full score: "
        f"{task_full['only_codebase']}"
    )
    lines.append(
        f"- Both full score: "
        f"{task_full['both_pass']}"
    )
    lines.append(
        f"- Neither full score: "
        f"{task_full['neither_pass']}"
    )
    lines.append("")

    lines.append("## Unique-input audit")
    lines.append("")

    total_unique = (
        len(comparable_groups)
        + len(ambiguous_groups)
    )

    lines.append(
        f"- Distinct query + question inputs: "
        f"{total_unique}"
    )
    lines.append(
        f"- Comparable unique inputs: "
        f"{len(comparable_groups)}"
    )
    lines.append(
        f"- Ambiguous expected groups: "
        f"{len(ambiguous_groups)}"
    )
    lines.append("")

    lines.append(
        "An ambiguous expected group contains the "
        "same retrieval input more than once with "
        "different benchmark expected answers. "
        "Such a group is preserved for auditing but "
        "excluded from the main unique-input "
        "direction counts."
    )
    lines.append("")

    lines.append(
        "## Comparable unique-input results"
    )
    lines.append("")

    lines.append(
        f"- IMCA higher score: "
        f"{group_direction['imca_higher']}"
    )
    lines.append(
        f"- Codebase-Memory higher score: "
        f"{group_direction['codebase_higher']}"
    )
    lines.append(
        f"- Equal score: "
        f"{group_direction['equal']}"
    )
    lines.append("")

    lines.append(
        f"- Only IMCA full score: "
        f"{group_full['only_imca']}"
    )
    lines.append(
        f"- Only Codebase-Memory full score: "
        f"{group_full['only_codebase']}"
    )
    lines.append(
        f"- Both full score: "
        f"{group_full['both_pass']}"
    )
    lines.append(
        f"- Neither full score: "
        f"{group_full['neither_pass']}"
    )
    lines.append("")

    lines.append(
        "## Unique inputs where IMCA scores higher"
    )
    lines.append("")

    lines.append(
        "- Operations: "
        + format_counter(
            Counter(
                row["operation"]
                for row in imca_unique
            )
        )
    )
    lines.append("")

    for row in imca_unique:
        lines.append(
            f"- `{', '.join(row['task_ids'])}` "
            f"— `{row['operation']}` "
            f"— {row['query_text']}"
        )

    lines.append("")

    lines.append(
        "## Unique inputs where Codebase-Memory "
        "scores higher"
    )
    lines.append("")

    lines.append(
        "- Operations: "
        + format_counter(
            Counter(
                row["operation"]
                for row in codebase_unique
            )
        )
    )
    lines.append("")

    for row in codebase_unique:
        lines.append(
            f"- `{', '.join(row['task_ids'])}` "
            f"— `{row['operation']}` "
            f"— {row['query_text']}"
        )

    lines.append("")

    lines.append(
        "## Strict full-score disagreements"
    )
    lines.append("")

    lines.append(
        f"- Comparable unique inputs with only "
        f"IMCA full score: "
        f"{len(only_imca_unique)}"
    )
    lines.append(
        f"- Comparable unique inputs with only "
        f"Codebase-Memory full score: "
        f"{len(only_codebase_unique)}"
    )
    lines.append("")

    lines.append("### Only IMCA")
    lines.append("")

    for row in only_imca_unique:
        first = row["rows"][0]

        lines.append(
            f"#### {', '.join(row['task_ids'])}"
        )
        lines.append("")

        lines.append(
            f"- Operation: `{row['operation']}`"
        )
        lines.append(
            f"- Query: {row['query_text']}"
        )
        lines.append(
            f"- IMCA score: "
            f"{first['imca_score']}"
        )
        lines.append(
            f"- Codebase-Memory score: "
            f"{first['codebase_score']}"
        )
        lines.append(
            f"- Expected: "
            f"`{first['expected']}`"
        )
        lines.append(
            f"- IMCA: "
            f"`{first['imca_results']}`"
        )
        lines.append(
            f"- Codebase-Memory: "
            f"`{first['codebase_results']}`"
        )
        lines.append("")

    lines.append("### Only Codebase-Memory")
    lines.append("")

    if not only_codebase_unique:
        lines.append(
            "No comparable unique input gives "
            "Codebase-Memory a full score while "
            "IMCA does not receive a full score."
        )
        lines.append("")
    else:
        for row in only_codebase_unique:
            first = row["rows"][0]

            lines.append(
                f"#### {', '.join(row['task_ids'])}"
            )
            lines.append("")

            lines.append(
                f"- Operation: "
                f"`{row['operation']}`"
            )
            lines.append(
                f"- Query: {row['query_text']}"
            )
            lines.append(
                f"- IMCA score: "
                f"{first['imca_score']}"
            )
            lines.append(
                f"- Codebase-Memory score: "
                f"{first['codebase_score']}"
            )
            lines.append(
                f"- Expected: "
                f"`{first['expected']}`"
            )
            lines.append(
                f"- IMCA: "
                f"`{first['imca_results']}`"
            )
            lines.append(
                f"- Codebase-Memory: "
                f"`{first['codebase_results']}`"
            )
            lines.append("")

    lines.append(
        "## Ambiguous expected groups"
    )
    lines.append("")

    if not ambiguous_groups:
        lines.append(
            "No repeated retrieval input has "
            "different expected answers."
        )
        lines.append("")
    else:
        for group in ambiguous_groups:
            lines.append(
                f"### {group['operation']} — "
                f"{', '.join(group['task_ids'])}"
            )
            lines.append("")

            lines.append(
                f"- Query: {group['query_text']}"
            )
            lines.append(
                f"- Number of tasks: "
                f"{group['task_count']}"
            )
            lines.append(
                f"- Distinct expected answers: "
                f"{group['distinct_expected_count']}"
            )
            lines.append(
                f"- Directions observed: "
                f"{', '.join(group['directions'])}"
            )
            lines.append(
                f"- Full-score statuses observed: "
                f"{', '.join(group['full_score_statuses'])}"
            )
            lines.append("")

            for row in group["rows"]:
                lines.append(
                    f"- `{row['id']}`: "
                    f"IMCA={row['imca_score']}, "
                    f"Codebase-Memory="
                    f"{row['codebase_score']}, "
                    f"expected=`{row['expected']}`"
                )

            lines.append("")

    lines.append("## Interpretation status")
    lines.append("")

    lines.append(
        "The script reports disagreement cases "
        "without assigning causal labels. "
        "The causes should be determined by manual "
        "inspection and quantitative analysis of "
        "representative comparable inputs."
    )
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--tasks",
        required=True,
    )

    parser.add_argument(
        "--predictions",
        required=True,
    )

    parser.add_argument(
        "--json-output",
        default=(
            "results/"
            "memory-retrieval-disagreements.json"
        ),
    )

    parser.add_argument(
        "--markdown-output",
        default=(
            "docs/"
            "memory-retrieval-disagreements.md"
        ),
    )

    args = parser.parse_args()

    tasks = load(args.tasks)
    predictions = load(args.predictions)

    if (
        IMCA not in predictions
        or CODEBASE not in predictions
    ):
        raise ValueError(
            "Required prediction methods are missing"
        )

    task_rows = [
        make_row(task, predictions)
        for task in tasks
    ]

    (
        comparable_groups,
        ambiguous_groups,
    ) = summarize_unique_groups(
        tasks,
        task_rows,
    )

    total_unique = (
        len(comparable_groups)
        + len(ambiguous_groups)
    )

    result = {
        "scope": (
            "Frozen LongMemCode retrieval "
            "predictions; no memory systems rerun"
        ),
        "task_count": len(task_rows),
        "distinct_input_count": total_unique,
        "comparable_unique_input_count": (
            len(comparable_groups)
        ),
        "ambiguous_expected_group_count": (
            len(ambiguous_groups)
        ),
        "task_level": {
            "direction_counts": count_field(
                task_rows,
                "direction",
            ),
            "full_score_counts": count_field(
                task_rows,
                "full_score_status",
            ),
        },
        "comparable_unique_input_level": {
            "direction_counts": count_field(
                comparable_groups,
                "direction",
            ),
            "full_score_counts": count_field(
                comparable_groups,
                "full_score_status",
            ),
        },
        "comparable_unique_groups": (
            comparable_groups
        ),
        "ambiguous_expected_groups": (
            ambiguous_groups
        ),
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
            result,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    md_output.write_text(
        render_markdown(
            task_rows,
            comparable_groups,
            ambiguous_groups,
        ),
        encoding="utf-8",
    )

    print(
        "task_count:",
        len(task_rows),
    )

    print(
        "distinct_input_count:",
        total_unique,
    )

    print(
        "comparable_unique_input_count:",
        len(comparable_groups),
    )

    print(
        "ambiguous_expected_group_count:",
        len(ambiguous_groups),
    )

    print()

    print(
        "task-level directions:"
    )
    print(
        Counter(
            row["direction"]
            for row in task_rows
        )
    )

    print()

    print(
        "comparable unique-input directions:"
    )
    print(
        Counter(
            row["direction"]
            for row in comparable_groups
        )
    )

    print()

    print(
        "task-level full score:"
    )
    print(
        Counter(
            row["full_score_status"]
            for row in task_rows
        )
    )

    print()

    print(
        "comparable unique-input full score:"
    )
    print(
        Counter(
            row["full_score_status"]
            for row in comparable_groups
        )
    )

    print()

    print(
        "ambiguous groups:"
    )

    for group in ambiguous_groups:
        print(
            " ",
            group["operation"],
            "| tasks =",
            group["task_count"],
            "| distinct expected =",
            group["distinct_expected_count"],
        )

    print()

    print(
        "saved:",
        json_output,
    )

    print(
        "saved:",
        md_output,
    )


if __name__ == "__main__":
    main()

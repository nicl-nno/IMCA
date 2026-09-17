"""Model-free diagnostics on MemoryAgentBench and HaluMem.

This is deliberately a memory-isolated retrieval evaluation.  It does not
claim the end-to-end, LLM-judged scores reported by either leaderboard.
Expected answers and evidence are read only after each top-k is frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import statistics
import time
from collections import Counter, defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"[a-z0-9]+")
NUMBERED_FACT = re.compile(r"^\s*\d+\.\s*(.*?)\s*$")
STOP = frozenset(
    "a an and are as at be by did do does for from had has have in is it of on or that "
    "the their to was were what when where which who whose with".split()
)


def normalize(text: str) -> str:
    return " ".join(TOKEN.findall(text.lower()))


def tokens(text: str) -> list[str]:
    return [token for token in TOKEN.findall(text.lower()) if token not in STOP]


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)] if ordered else 0.0


class BM25:
    def __init__(self, documents: list[str]):
        self.documents = documents
        self.rows = [tokens(document) for document in documents]
        self.length = [len(row) for row in self.rows]
        self.average = statistics.fmean(self.length) if self.length else 1.0
        self.tf = [Counter(row) for row in self.rows]
        document_frequency = Counter()
        for row in self.rows:
            document_frequency.update(set(row))
        total = len(documents)
        self.idf = {
            term: math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def scores(self, query: str, allowed: set[int] | None = None) -> list[tuple[int, float]]:
        query_terms = Counter(tokens(query))
        rows = []
        for index, frequencies in enumerate(self.tf):
            if allowed is not None and index not in allowed:
                continue
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + 1.2 * (
                    1 - 0.75 + 0.75 * self.length[index] / self.average
                )
                score += self.idf.get(term, 0.0) * frequency * 2.2 / denominator
                score *= 1 + 0.05 * min(query_frequency - 1, 2)
            rows.append((index, score))
        return sorted(rows, key=lambda item: (-item[1], item[0]))

    def top(self, query: str, k: int, allowed: set[int] | None = None) -> list[int]:
        return [index for index, _ in self.scores(query, allowed)[:k]]


RELATIONS = (
    r"^The author of (?P<s>.+?) is (?P<o>.+?)\.?$",
    r"^The chairperson of (?P<s>.+?) is (?P<o>.+?)\.?$",
    r"^The director of (?P<s>.+?) is (?P<o>.+?)\.?$",
    r"^The headquarters of (?P<s>.+?) is located in the city of (?P<o>.+?)\.?$",
    r"^The chief executive officer of (?P<s>.+?) is (?P<o>.+?)\.?$",
    r"^The univeristy where (?P<s>.+?) was educated is (?P<o>.+?)\.?$",
    r"^The capital of (?P<s>.+?) is (?P<o>.+?)\.?$",
    r"^The official language of (?P<s>.+?) is (?P<o>.+?)\.?$",
    r"^The type of music that (?P<s>.+?) plays is (?P<o>.+?)\.?$",
    r"^The company that produced (?P<s>.+?) is (?P<o>.+?)\.?$",
    r"^The name of the current head of (?:state in|the) (?P<s>.+?) is (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) was born in the city of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) died in the city of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) plays the position of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) is located in the continent of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) worked in the city of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) is married to (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) was founded by (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) was founded in the city of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) is associated with the sport of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) is a citizen of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) was performed by (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) was created by (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) was created in the country of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) speaks the language of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) is famous for (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) is employed by (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) is affiliated with the religion of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) works in the field of (?P<o>.+?)\.?$",
    r"^(?P<s>.+?)'s child is (?P<o>.+?)\.?$",
    r"^(?P<s>.+?) was written in the language of (?P<o>.+?)\.?$",
)
COMPILED_RELATIONS = tuple(re.compile(pattern) for pattern in RELATIONS)


def endpoints(fact: str) -> tuple[str, str] | None:
    for pattern in COMPILED_RELATIONS:
        match = pattern.match(fact)
        if match:
            return normalize(match.group("s")), normalize(match.group("o"))
    return None


def graph_rank(query: str, facts: list[str], index: BM25, *, k: int = 5) -> list[int]:
    """Label-free adjacency expansion with RRF-like direct/structural fusion."""
    parsed = [endpoints(fact) for fact in facts]
    by_entity: dict[str, list[int]] = defaultdict(list)
    for document_id, edge in enumerate(parsed):
        if edge:
            for entity in set(edge):
                by_entity[entity].append(document_id)
    direct = index.top(query, 20)
    direct_rank = {document_id: rank for rank, document_id in enumerate(direct, 1)}
    best_hop = {document_id: 0 for document_id in direct[:1]}
    queue = deque((document_id, 0) for document_id in direct[:1])
    while queue:
        document_id, hop = queue.popleft()
        if hop == 3 or parsed[document_id] is None:
            continue
        for entity in parsed[document_id] or ():
            for neighbor in by_entity[entity]:
                next_hop = hop + 1
                if next_hop < best_hop.get(neighbor, 99):
                    best_hop[neighbor] = next_hop
                    queue.append((neighbor, next_hop))
    # Keep the strongest lexical witness, then spend the remaining slots on
    # traversing its neighborhood.  Otherwise five direct keyword matches can
    # consume the whole budget before a two-hop answer gets a slot.
    pinned = direct[:3]
    candidates = (set(direct) | set(best_hop)) - set(pinned)
    scored = []
    for document_id in candidates:
        direct_score = (
            0.2 / (60 + direct_rank[document_id]) if document_id in direct_rank else 0
        )
        hop = best_hop.get(document_id)
        structural = 0 if hop is None else (0.82**hop) / (hop + 1)
        edge = parsed[document_id]
        degree = 0 if edge is None else sum(len(by_entity[node]) - 1 for node in set(edge))
        continuation = min(degree, 6) * 0.01
        scored.append((document_id, direct_score + structural + continuation))
    expanded = [
        document_id
        for document_id, _ in sorted(scored, key=lambda x: (-x[1], x[0]))
    ]
    return (pinned + expanded)[:k]


def graph_needed(query: str) -> bool:
    """A label-free syntax gate for nested relational questions."""
    lowered = f" {query.lower()} "
    return lowered.count(" of ") >= 2 or " whose " in lowered


def answer_in_documents(
    document_ids: Iterable[int], facts: list[str], expected: list[str]
) -> bool:
    rendered = [normalize(facts[document_id]) for document_id in document_ids]
    return any(answer and any(answer in fact for fact in rendered) for answer in expected)


def evidence_metrics(
    document_ids: list[int],
    points: list[MemoryPoint],
    evidence: set[str],
    target_time: float,
) -> tuple[bool, float, int]:
    found = {normalize(points[index].text) for index in document_ids} & evidence
    stale = sum(not points[index].active_at(target_time) for index in document_ids)
    return bool(found), len(found) / len(evidence) if evidence else 0.0, stale


def summarize_binary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    return {
        "n": len(rows),
        "hits": sum(bool(row[field]) for row in rows),
        "rate": sum(bool(row[field]) for row in rows) / len(rows) if rows else 0.0,
    }


def evaluate_memory_agent_bench(path: Path) -> dict[str, Any]:
    import pyarrow.parquet as parquet

    source_rows = parquet.read_table(path).to_pylist()
    selected_sources = {"factconsolidation_mh_6k", "factconsolidation_sh_6k"}
    rows = []
    timings: dict[str, list[float]] = defaultdict(list)
    for source in source_rows:
        name = source["metadata"]["source"]
        if name not in selected_sources:
            continue
        facts = [
            match.group(1)
            for line in source["context"].splitlines()
            if (match := NUMBERED_FACT.match(line))
        ]
        bm25 = BM25(facts)
        for question_index, question in enumerate(source["questions"]):
            started = time.perf_counter()
            baseline = bm25.top(question, 5)
            timings["bm25"].append((time.perf_counter() - started) * 1000)
            routed = graph_needed(question)
            started = time.perf_counter()
            graph = graph_rank(question, facts, bm25) if routed else baseline
            graph_elapsed = (time.perf_counter() - started) * 1000
            timings["graph_all"].append(graph_elapsed)
            if routed:
                timings["graph_routed"].append(graph_elapsed)
            # Labels enter only here, after both rankings are frozen.
            expected = [normalize(answer) for answer in source["answers"][question_index]]

            rows.append(
                {
                    "source": name,
                    "question_index": question_index,
                    "routed": routed,
                    "bm25_hit": answer_in_documents(baseline, facts, expected),
                    "graph_hit": answer_in_documents(graph, facts, expected),
                    "bm25_ids": baseline,
                    "graph_ids": graph,
                }
            )
    by_source = {}
    for name in sorted(selected_sources):
        group = [row for row in rows if row["source"] == name]
        by_source[name] = {
            "bm25": summarize_binary(group, "bm25_hit"),
            "graph": summarize_binary(group, "graph_hit"),
        }
    return {
        "protocol": "official 6k single-hop and multi-hop contexts; answer-string evidence proxy@5",
        "comparability": "memory-isolated retrieval diagnostic, not official end-to-end accuracy",
        "n": len(rows),
        "bm25": summarize_binary(rows, "bm25_hit"),
        "graph": summarize_binary(rows, "graph_hit"),
        "paired": {
            "wins": sum(row["graph_hit"] and not row["bm25_hit"] for row in rows),
            "losses": sum(row["bm25_hit"] and not row["graph_hit"] for row in rows),
            "ties": sum(row["bm25_hit"] == row["graph_hit"] for row in rows),
        },
        "routed_questions": sum(row["routed"] for row in rows),
        "by_source": by_source,
        "timings_ms": {
            name: {"p50": statistics.median(values), "p95": percentile(values, 0.95)}
            for name, values in timings.items()
        },
        "rows": rows,
    }


@dataclass
class MemoryPoint:
    text: str
    valid_from: float
    valid_to: float | None = None

    def active_at(self, target: float) -> bool:
        return self.valid_from <= target and (self.valid_to is None or target < self.valid_to)


MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        1,
    )
}
MONTHS.update({name[:3].lower(): number for name, number in list(MONTHS.items())})
TEXT_DATE = re.compile(
    r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")"
    r"(?:\s+(\d{1,2}))?,?\s+(20\d{2})\b",
    re.IGNORECASE,
)
ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
MEMORY_DATE = re.compile(
    r"\b([A-Z][a-z]{2})\s+(\d{1,2}),\s+(20\d{2}).*?(\d{2}):(\d{2}):(\d{2})\s*$"
)


def memory_time(value: str) -> float:
    match = MEMORY_DATE.search(value)
    if not match:
        raise ValueError(f"unsupported HaluMem timestamp: {value!r}")
    month, day, year, hour, minute, second = match.groups()
    return datetime.strptime(
        f"{month} {day}, {year}, {hour}:{minute}:{second}", "%b %d, %Y, %H:%M:%S"
    ).timestamp()


def question_time(question: str, fallback: str) -> float:
    dates = [
        datetime(int(year), int(month), int(day), 23, 59, 59).timestamp()
        for year, month, day in ISO_DATE.findall(question)
    ]
    for month, day, year in TEXT_DATE.findall(question):
        # Month-only references mean the end of that month for "by/as of" questions.
        month_number = MONTHS[month.lower()]
        day_number = int(day) if day else 31
        parsed = None
        while day_number > 28:
            try:
                parsed = datetime(int(year), month_number, day_number, 23, 59, 59)
                break
            except ValueError:
                day_number -= 1
        if parsed is None:
            parsed = datetime(int(year), month_number, day_number, 23, 59, 59)
        dates.append(parsed.timestamp())
    return max(dates) if dates else memory_time(fallback)


def evaluate_halumem(path: Path) -> dict[str, Any]:
    rows = []
    timings: dict[str, list[float]] = defaultdict(list)
    user_count = 0
    session_count = 0
    point_count = 0
    update_count = 0
    linked_updates = 0
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            user_count += 1
            user = json.loads(line)
            points: list[MemoryPoint] = []
            by_text: dict[str, list[int]] = defaultdict(list)
            for session_index, session in enumerate(user["sessions"]):
                session_count += 1
                for memory in session.get("memory_points", []):
                    update_count += str(memory.get("is_update", "false")).lower() == "true"
                    for original in memory.get("original_memories", []):
                        candidates = by_text.get(normalize(original), [])
                        if candidates:
                            update_time = memory_time(memory["timestamp"])
                            old_id = next(
                                (
                                    item
                                    for item in reversed(candidates)
                                    if points[item].valid_to is None
                                ),
                                None,
                            )
                            if old_id is not None:
                                points[old_id].valid_to = update_time
                                linked_updates += 1
                    point_id = len(points)
                    points.append(
                        MemoryPoint(
                            memory["memory_content"], memory_time(memory["timestamp"])
                        )
                    )
                    by_text[normalize(memory["memory_content"])].append(point_id)
                    point_count += 1
                if not session.get("questions"):
                    continue
                search = BM25([point.text for point in points])
                for question_index, question in enumerate(session["questions"]):
                    target_time = question_time(question["question"], session["end_time"])
                    active = {
                        index for index, point in enumerate(points) if point.active_at(target_time)
                    }
                    started = time.perf_counter()
                    flat = search.top(question["question"], 5)
                    timings["flat"].append((time.perf_counter() - started) * 1000)
                    started = time.perf_counter()
                    temporal = search.top(question["question"], 5, active)
                    timings["temporal"].append((time.perf_counter() - started) * 1000)
                    # Evidence labels enter only after both result lists are frozen.
                    evidence = {normalize(item["memory_content"]) for item in question["evidence"]}

                    flat_hit, flat_recall, flat_stale = evidence_metrics(
                        flat, points, evidence, target_time
                    )
                    temporal_hit, temporal_recall, temporal_stale = evidence_metrics(
                        temporal, points, evidence, target_time
                    )
                    rows.append(
                        {
                            "user": user["uuid"],
                            "session": session_index,
                            "question": question_index,
                            "type": question["question_type"],
                            "evidence_count": len(evidence),
                            "flat_hit": flat_hit,
                            "temporal_hit": temporal_hit,
                            "flat_recall": flat_recall,
                            "temporal_recall": temporal_recall,
                            "flat_stale": flat_stale,
                            "temporal_stale": temporal_stale,
                        }
                    )
    evidence_rows = [row for row in rows if row["evidence_count"]]

    def summary(group: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "n": len(group),
            "flat_hit5": sum(row["flat_hit"] for row in group) / len(group) if group else 0,
            "temporal_hit5": sum(row["temporal_hit"] for row in group) / len(group) if group else 0,
            "flat_recall5": statistics.fmean(row["flat_recall"] for row in group) if group else 0,
            "temporal_recall5": statistics.fmean(row["temporal_recall"] for row in group)
            if group
            else 0,
            "wins": sum(row["temporal_hit"] and not row["flat_hit"] for row in group),
            "losses": sum(row["flat_hit"] and not row["temporal_hit"] for row in group),
            "flat_stale_slots": sum(row["flat_stale"] for row in group),
            "temporal_stale_slots": sum(row["temporal_stale"] for row in group),
        }

    return {
        "protocol": "all HaluMem-Medium questions with evidence; top-5 memory retrieval",
        "comparability": (
            "oracle-writer/update-layer diagnostic: official memory points and original_memories "
            "are structured writes; not leaderboard QA or extraction scores"
        ),
        "users": user_count,
        "sessions": session_count,
        "memory_points": point_count,
        "annotated_updates": update_count,
        "linked_replacements": linked_updates,
        "questions": len(rows),
        "questions_with_evidence": len(evidence_rows),
        "overall": summary(evidence_rows),
        "by_type": {
            question_type: summary([row for row in evidence_rows if row["type"] == question_type])
            for question_type in sorted({row["type"] for row in evidence_rows})
        },
        "timings_ms": {
            name: {"p50": statistics.median(values), "p95": percentile(values, 0.95)}
            for name, values in timings.items()
        },
        "rows": rows,
    }


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(report: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in report.items() if key != "wall_seconds"}
    for benchmark in ("memory_agent_bench", "halumem"):
        result[benchmark] = {
            key: value for key, value in report[benchmark].items() if key != "rows"
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "outputs/benchmarks")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/additional-benchmarks.json")
    parser.add_argument("--compact-output", type=Path)
    args = parser.parse_args()
    mab = args.data / "mab_conflict.parquet"
    halumem = args.data / "halumem-medium.jsonl"
    started = time.perf_counter()
    report = {
        "protocol_version": "additional-benchmarks-v2",
        "model_calls": 0,
        "models": [],
        "machine": platform.platform(),
        "python": platform.python_version(),
        "sources": {mab.name: file_hash(mab), halumem.name: file_hash(halumem)},
        "memory_agent_bench": evaluate_memory_agent_bench(mab),
        "halumem": evaluate_halumem(halumem),
    }
    report["wall_seconds"] = time.perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.compact_output:
        args.compact_output.parent.mkdir(parents=True, exist_ok=True)
        args.compact_output.write_text(
            json.dumps(compact(report), indent=2), encoding="utf-8"
        )
    metadata = {
        key: value
        for key, value in report.items()
        if key not in {"memory_agent_bench", "halumem"}
    }
    summaries = {
        name: {key: value for key, value in report[name].items() if key != "rows"}
        for name in ("memory_agent_bench", "halumem")
    }
    print(json.dumps(metadata, indent=2))
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()

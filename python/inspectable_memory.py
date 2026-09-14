"""Opt-in, append-only assertion memory with bitemporal inspection.

Valid time is an integer position in a caller-pinned linear snapshot history,
NOT a Git timestamp or an ordering of arbitrary branches. Recorded time is UTC.
No model, benchmark labels, or existing product stores are used by this layer.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import sqlite3
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RULE_VERSION = "inspectable-v1"
SINGLE_VALUED = frozenset({"default", "signature", "exists", "parameter_exists"})
MODES = frozenset({"baseline", "temporal", "conflict", "combined"})


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("recorded/known time must have an explicit timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class Scope:
    repository: str
    branch: str = "main"
    environment: str = "default"


@dataclass(frozen=True)
class Fact:
    entity: str
    predicate: str
    value: Any
    scope: Scope
    valid_from: int | None
    valid_to: int | None
    recorded_at: str
    evidence: dict[str, Any]
    negated: bool = False

    def payload(self) -> dict[str, Any]:
        if not self.entity or not self.predicate or not self.scope.repository:
            raise ValueError("entity, predicate and repository are required")
        for bound in (self.valid_from, self.valid_to):
            if bound is not None and (type(bound) is not int or bound < 0):
                raise ValueError("valid bounds must be nonnegative snapshot positions")
        if self.valid_to is not None and (
            self.valid_from is None or self.valid_to <= self.valid_from
        ):
            raise ValueError("valid interval must be nonempty and half-open")
        if not self.evidence or not self.evidence.get("source"):
            raise ValueError("every assertion requires source evidence")
        payload = asdict(self)
        payload["recorded_at"] = utc(self.recorded_at)
        canonical(payload)
        return payload


def incompatible(a: dict, b: dict) -> bool:
    """Open-world rules: absence is never negation, calls are multi-valued."""
    if (a["entity"], a["predicate"]) != (b["entity"], b["predicate"]):
        return False
    same_value = canonical(a["value"]) == canonical(b["value"])
    if a["negated"] != b["negated"]:
        return same_value
    return not a["negated"] and a["predicate"] in SINGLE_VALUED and not same_value


def pair_diagnosis(a: dict, b: dict, *, temporal: bool = True) -> str | None:
    if not incompatible(a, b):
        return None
    if a["scope"] != b["scope"]:
        return "different_scope"
    if temporal:
        if a["valid_from"] is None or b["valid_from"] is None:
            return "unknown_validity"
        a_end = a["effective_to"] if a["effective_to"] is not None else float("inf")
        b_end = b["effective_to"] if b["effective_to"] is not None else float("inf")
        if max(a["valid_from"], b["valid_from"]) >= min(a_end, b_end):
            return "version_change"
    return "conflict"


class InspectableMemory:
    """SQLite event journal; optional facade, never a silent primary-store override.

    Calls may reopen the same database. Writes are transactional and idempotent.
    Cache reads include the database revision and all query coordinates; results
    are copied, so callers cannot mutate cached history.
    """

    def __init__(self, path: str | Path = ":memory:", *, cache_size: int = 128):
        self.db = sqlite3.connect(str(path), timeout=5, check_same_thread=False)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS assertions (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS replacements (
                id TEXT PRIMARY KEY, old_id TEXT NOT NULL REFERENCES assertions(id),
                new_id TEXT NOT NULL REFERENCES assertions(id),
                effective INTEGER NOT NULL, recorded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS revision (singleton INTEGER PRIMARY KEY, n INTEGER NOT NULL);
            INSERT OR IGNORE INTO revision VALUES (1, 0);
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        """)
        self.cache_size = max(0, cache_size)
        self.cache: OrderedDict[str, dict] = OrderedDict()

    def close(self):
        self.db.close()

    @property
    def revision(self) -> int:
        return self.db.execute("SELECT n FROM revision WHERE singleton=1").fetchone()[0]

    def save(self, facts: list[Fact]) -> list[str]:
        prepared = [fact.payload() for fact in facts]
        ids = [digest(payload) for payload in prepared]
        with self.db:
            changed = False
            for fact_id, payload in zip(ids, prepared, strict=True):
                cursor = self.db.execute(
                    "INSERT OR IGNORE INTO assertions VALUES (?, ?)", (fact_id, canonical(payload))
                )
                changed |= bool(cursor.rowcount)
            if changed:
                self.db.execute("UPDATE revision SET n=n+1 WHERE singleton=1")
        return ids

    def supersede(self, old_id: str, new_id: str, *, effective: int, recorded_at: str) -> str:
        if type(effective) is not int or effective < 0 or old_id == new_id:
            raise ValueError("invalid replacement")
        recorded = utc(recorded_at)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            rows = self.db.execute(
                "SELECT id, payload FROM assertions WHERE id IN (?, ?)", (old_id, new_id)
            ).fetchall()
            facts = {key: json.loads(payload) for key, payload in rows}
            if len(facts) != 2:
                raise ValueError("replacement must reference two saved facts")
            old, new = facts[old_id], facts[new_id]
            if any(old[key] != new[key] for key in ("entity", "predicate", "scope")):
                raise ValueError("replacement cannot cross entity, predicate or scope")
            if old["predicate"] not in SINGLE_VALUED and old["value"] != new["value"]:
                raise ValueError("multi-valued relationships cannot replace unrelated values")
            for fact in (old, new):
                if fact["recorded_at"] > recorded:
                    raise ValueError("replacement cannot predate knowledge of its assertions")
                if fact["valid_from"] is None or fact["valid_from"] > effective:
                    raise ValueError("replacement requires known, compatible validity")
                if fact["valid_to"] is not None and effective >= fact["valid_to"]:
                    raise ValueError("replacement falls outside the assertion interval")
            # Cycles would incorrectly retire an entire assertion history.
            edges = self.db.execute("SELECT old_id, new_id FROM replacements").fetchall()
            pending, seen = [new_id], set()
            while pending:
                current = pending.pop()
                if current == old_id:
                    raise ValueError("replacement cycle")
                if current not in seen:
                    seen.add(current)
                    pending.extend(b for a, b in edges if a == current)
            event = {"old": old_id, "new": new_id, "effective": effective, "recorded": recorded}
            event_id = digest(event)
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO replacements VALUES (?, ?, ?, ?, ?)",
                (event_id, old_id, new_id, effective, recorded),
            )
            if cursor.rowcount:
                self.db.execute("UPDATE revision SET n=n+1 WHERE singleton=1")
        return event_id

    def recall(
        self,
        *,
        at: int,
        known_at: str,
        scope: Scope,
        entity: str | None = None,
        mode: str = "combined",
        use_cache: bool = True,
    ) -> dict:
        if type(at) is not int or at < 0 or mode not in MODES:
            raise ValueError("invalid snapshot position or mode")
        known = utc(known_at)
        started = time.perf_counter()
        # One read transaction gives rows, events and cache revision the same snapshot.
        self.db.execute("BEGIN")
        try:
            revision = self.revision
            key = digest([RULE_VERSION, revision, at, known, asdict(scope), entity, mode])
            if use_cache and key in self.cache:
                result = copy.deepcopy(self.cache[key])
                self.cache.move_to_end(key)
                result["cache_hit"] = True
                result["latency_ms"] = (time.perf_counter() - started) * 1000
                return result
            facts = []
            for fact_id, payload in self.db.execute(
                "SELECT id, payload FROM assertions ORDER BY id"
            ):
                fact = json.loads(payload)
                if fact["recorded_at"] > known or fact["scope"] != asdict(scope):
                    continue
                if entity is not None and fact["entity"] != entity:
                    continue
                facts.append({"id": fact_id, **fact, "effective_to": fact["valid_to"]})
            events = self.db.execute(
                "SELECT old_id, new_id, effective, recorded_at FROM replacements "
                "WHERE recorded_at <= ? ORDER BY effective, id",
                (known,),
            ).fetchall()
        finally:
            self.db.commit()
        for fact in facts:
            replacements = [e for e in events if e[0] == fact["id"]]
            bounds = [e[2] for e in replacements]
            if fact["valid_to"] is not None:
                bounds.append(fact["valid_to"])
            fact["effective_to"] = min(bounds) if bounds else None
            fact["superseded_by"] = [e[1] for e in replacements if e[2] <= at]
            if fact["valid_from"] is None:
                status = "unknown_validity"
            elif at < fact["valid_from"]:
                status = "not_yet_valid"
            elif fact["effective_to"] is not None and at >= fact["effective_to"]:
                status = "superseded" if fact["superseded_by"] else "expired"
            else:
                status = "active"
            fact["status"] = status
        temporal = mode in {"temporal", "combined"}
        selected = [f["id"] for f in facts if not temporal or f["status"] == "active"]
        selected_set = set(selected)
        pairs = []
        if mode in {"conflict", "combined"}:
            # Block by subject/predicate instead of comparing every fact to every other fact.
            groups: dict[tuple, list] = {}
            for fact in facts:
                groups.setdefault((fact["entity"], fact["predicate"]), []).append(fact)
            for group in groups.values():
                for a, b in itertools.combinations(group, 2):
                    diagnosis = pair_diagnosis(a, b, temporal=temporal)
                    if diagnosis:
                        pairs.append(
                            {
                                "ids": [a["id"], b["id"]],
                                "diagnosis": diagnosis,
                                "current": a["id"] in selected_set and b["id"] in selected_set,
                                "rule": "same-subject/incompatible-values/overlapping-validity",
                            }
                        )
        conflicts = [p for p in pairs if p["diagnosis"] == "conflict" and p["current"]]
        result = {
            "revision": revision,
            "rule_version": RULE_VERSION,
            "at": at,
            "known_at": known,
            "scope": asdict(scope),
            "mode": mode,
            "facts": facts,
            "selected_ids": selected,
            "pairs": pairs,
            "conflicts": conflicts,
            "answer_status": "conflict" if conflicts else ("supported" if selected else "unknown"),
            "cache_hit": False,
            "latency_ms": (time.perf_counter() - started) * 1000,
        }
        if use_cache and self.cache_size:
            self.cache[key] = copy.deepcopy(result)
            self.cache.move_to_end(key)
            while len(self.cache) > self.cache_size:
                self.cache.popitem(last=False)
        return result

    def save_run(self, payload: dict, *, parent_id: str | None = None) -> str:
        """Persist an immutable replay, including explicit parent and data hashes."""
        if "run_id" in payload:
            raise ValueError("run_id is generated from content and cannot be supplied")
        if (
            parent_id
            and self.db.execute("SELECT 1 FROM runs WHERE id=?", (parent_id,)).fetchone() is None
        ):
            raise ValueError("unknown parent run")
        value = {**payload, "parent_id": parent_id}
        run_id = digest(value)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO runs VALUES (?, ?)", (run_id, canonical(value)))
        return run_id

    def get_run(self, run_id: str) -> dict:
        row = self.db.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        payload = json.loads(row[0])
        if digest(payload) != run_id:
            raise ValueError("stored run failed its content hash check")
        return {"run_id": run_id, **payload}

"""Live, isolated workspaces over the unchanged research assertion journal.

No LLM or automatic fact extraction. Agent names are provenance supplied by the
visitor; the guided events are explicitly authored, not benchmark observations.
"""

import json
import re
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from inspectable_memory import Fact, Scope, digest, utc

ENTITY = "project.architecture"
PREDICATES = {"default", "signature", "exists", "parameter_exists", "calls"}


def text(value, name, limit=160):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name}: expected nonempty text, max {limit} characters")
    return value.strip()


def position(value, name):
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError(f"{name}: expected a snapshot number between 0 and 100")
    return value


class LiveLab:
    def __init__(self, memory):
        self.memory = memory
        with memory.db:
            memory.db.execute(
                "CREATE TABLE IF NOT EXISTS live_sessions "
                "(id TEXT PRIMARY KEY, created TEXT NOT NULL)"
            )

    def create(self):
        room = uuid.uuid4().hex
        with self.memory.db:
            self.memory.db.execute(
                "INSERT INTO live_sessions VALUES (?, ?)",
                (room, utc(datetime.now(UTC).isoformat())),
            )
        return self.snapshot({"room": room})

    def room(self, value):
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
            raise ValueError("invalid workspace")
        row = self.memory.db.execute(
            "SELECT created FROM live_sessions WHERE id=?", (value,)
        ).fetchone()
        if row is None:
            raise ValueError("unknown workspace")
        return row[0]

    def journal(self, room):
        self.room(room)
        facts = []
        for sid, raw in self.memory.db.execute("SELECT id, payload FROM assertions"):
            fact = json.loads(raw)
            if fact["scope"]["repository"] == "live-lab" and fact["scope"]["branch"] == room:
                facts.append({"id": sid, **fact})
        by_id = {f["id"]: f for f in facts}
        events = [
            {
                "id": f["id"],
                "kind": "assertion",
                "recorded_at": f["recorded_at"],
                "entity": f["entity"],
                "value": f["value"],
                "agent": f["evidence"]["agent"],
            }
            for f in facts
        ]
        replacements = []
        for eid, old, new, effective, recorded in self.memory.db.execute(
            "SELECT * FROM replacements"
        ):
            if old in by_id and new in by_id:
                event = {
                    "id": eid,
                    "kind": "replacement",
                    "old_id": old,
                    "new_id": new,
                    "effective": effective,
                    "recorded_at": recorded,
                    "agent": "Visitor confirmation",
                }
                replacements.append(event)
                events.append(event)
        events.sort(key=lambda e: (e["recorded_at"], e["id"]))
        return facts, events, replacements

    def clock(self, room):
        _, events, _ = self.journal(room)
        previous = events[-1]["recorded_at"] if events else self.room(room)
        return utc(
            max(
                datetime.now(UTC),
                datetime.fromisoformat(previous) + timedelta(microseconds=1),
            ).isoformat()
        )

    def save(self, request):
        room = request.get("room")
        facts, _, _ = self.journal(room)
        if len(facts) >= 80:
            raise ValueError("workspace limit: create another workspace")
        predicate = request.get("predicate", "default")
        if predicate not in PREDICATES:
            raise ValueError("unsupported predicate")
        value = request.get("value")
        if type(value) not in (str, int, float, bool) or (
            isinstance(value, str) and len(value) > 500
        ):
            raise ValueError("value must be a short scalar")
        negated = request.get("negated", False)
        if type(negated) is not bool:
            raise ValueError("negated must be boolean")
        start = request.get("valid_from", 0)
        if start is not None:
            position(start, "valid_from")
        end = request.get("valid_to")
        if end is not None:
            position(end, "valid_to")
        environment = text(request.get("environment", "production"), "environment", 40)
        evidence = {
            "source": text(request.get("source"), "source", 300),
            "text": text(request.get("excerpt"), "excerpt", 1500),
            "agent": text(request.get("agent", "Visitor"), "agent", 80),
            "kind": "visitor_assertion_not_independently_verified",
        }
        fact = Fact(
            text(request.get("entity"), "entity"),
            predicate,
            value,
            Scope("live-lab", room, environment),
            start,
            end,
            self.clock(room),
            evidence,
            negated,
        )
        self.snapshot({**request, "known": None})  # Validate view coordinates before writing.
        sid = self.memory.save([fact])[0]
        return {"saved_id": sid, **self.snapshot({**request, "known": None})}

    def replace(self, request):
        room = request.get("room")
        facts, _, _ = self.journal(room)
        own = {f["id"] for f in facts}
        old, new = request.get("old_id"), request.get("new_id")
        if old not in own or new not in own:
            raise ValueError("replacement requires two facts from this workspace")
        self.snapshot({**request, "known": None})
        eid = self.memory.supersede(
            old,
            new,
            effective=position(request.get("effective"), "effective"),
            recorded_at=self.clock(room),
        )
        return {"replacement_id": eid, **self.snapshot({**request, "known": None})}

    def step(self, request):
        """Three real writes, no pre-seeded state. Repeated steps are idempotent."""
        room = request.get("room")
        facts, _, replacements = self.journal(room)
        demo = {f["evidence"]["source"]: f for f in facts if f["entity"] == ENTITY}
        common = {
            "room": room,
            "entity": ENTITY,
            "predicate": "default",
            "environment": "production",
            "at": 42,
        }
        old, new = (
            demo.get("scenario://architecture/decision-x-v41"),
            demo.get("scenario://architecture/evidence-y-v42"),
        )
        step = request.get("step")
        if type(step) is not int or step not in (1, 2, 3):
            raise ValueError("step must be 1, 2 or 3")

        if step == 1 and not old:
            return self.save(
                {
                    **common,
                    "value": "Architecture X",
                    "valid_from": 41,
                    "source": "scenario://architecture/decision-x-v41",
                    "agent": "Architecture decision · ADR-001",
                    "excerpt": (
                        "At V41, ADR-001 records Architecture X as the approved project architecture. "
                        "This decision is valid for the current project scope."
                    ),
                }
            )

        if step >= 2 and not old:
            raise ValueError("start with step 1")

        if step == 2 and not new:
            return self.save(
                {
                    **common,
                    "value": "Architecture Y",
                    "valid_from": 42,
                    "source": "scenario://architecture/evidence-y-v42",
                    "agent": "Architecture review · ADR-002",
                    "excerpt": (
                        "At V42, a later architecture review records Architecture Y for the same project scope. "
                        "The relation to the earlier Architecture X decision has not yet been confirmed in memory."
                    ),
                }
            )

        if step == 3:
            if not new:
                raise ValueError("add the second assertion first")
            if not any(
                event["old_id"] == old["id"] and event["new_id"] == new["id"]
                for event in replacements
            ):
                return self.replace(
                    {
                        **common,
                        "old_id": old["id"],
                        "new_id": new["id"],
                        "effective": 42,
                    }
                )

        return self.snapshot(common)

    def snapshot(self, request):
        room = request.get("room")
        created = self.room(room)
        facts, events, replacements = self.journal(room)
        at = position(request.get("at", 42), "at")
        known = request.get("known")
        known = len(events) if known is None else known
        if type(known) is not int or not 0 <= known <= len(events):
            raise ValueError("knowledge position outside journal")
        cutoff = events[known - 1]["recorded_at"] if known else created
        entity = text(request.get("entity", ENTITY), "entity")
        predicate = text(request.get("predicate", "default"), "predicate")
        environment = text(request.get("environment", "production"), "environment", 40)
        scope = Scope("live-lab", room, environment)
        result = self.memory.recall(at=at, known_at=cutoff, scope=scope, entity=entity)
        relevant = {f["id"]: f for f in result["facts"] if f["predicate"] == predicate}
        selected = [sid for sid in result["selected_ids"] if sid in relevant]
        conflicts = [p for p in result["conflicts"] if all(sid in relevant for sid in p["ids"])]
        status = "conflict" if conflicts else "supported" if selected else "unknown"
        trace = []
        for f in sorted(facts, key=lambda f: (f["recorded_at"], f["id"])):
            reason = (
                "not_known"
                if f["recorded_at"] > cutoff
                else "different_environment"
                if f["scope"] != asdict(scope)
                else "different_entity"
                if f["entity"] != entity
                else "different_predicate"
                if f["predicate"] != predicate
                else relevant[f["id"]]["status"]
            )
            trace.append(
                {
                    **f,
                    "status": reason,
                    "selected": f["id"] in selected,
                    "effective_to": relevant.get(f["id"], {}).get("effective_to", f["valid_to"]),
                    "conflicting": any(f["id"] in pair["ids"] for pair in conflicts),
                }
            )
        payload = {
            "room": room,
            "at": at,
            "known": known,
            "known_at": cutoff,
            "query": {"entity": entity, "predicate": predicate, "environment": environment},
            "events": events,
            "facts": trace,
            "replacements": replacements,
            "pairs": [p for p in result["pairs"] if all(sid in relevant for sid in p["ids"])],
            "conflicts": conflicts,
            "selected_ids": selected,
            "answer_status": status,
            "cache_hit": result["cache_hit"],
            "latency_ms": result["latency_ms"],
            "revision": result["revision"],
            "rule_version": result["rule_version"],
            "model_calls": 0,
            "scope": asdict(scope),
        }
        payload["trace_hash"] = digest(
            {k: v for k, v in payload.items() if k not in ("cache_hit", "latency_ms")}
        )
        return payload

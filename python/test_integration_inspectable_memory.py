"""Hermetic save/save/recall tests using real SQLite, no model or service."""

from dataclasses import replace

import pytest

from inspectable_memory import Fact, InspectableMemory, Scope

SCOPE = Scope("repo@pinned-chain")
T1, T2, T3 = (f"2026-09-0{i}T00:00:00Z" for i in (1, 2, 3))


def fact(value=30, **kwargs):
    return replace(
        Fact(
            "api.f.timeout",
            "default",
            value,
            SCOPE,
            0,
            None,
            T1,
            {"source": "api.py:2", "kind": "test"},
        ),
        **kwargs,
    )


def read(memory, **kwargs):
    return memory.recall(**{"at": 1, "known_at": T3, "scope": SCOPE, **kwargs})


def test_save_save_recall_late_supersession_and_historical_knowledge(tmp_path):
    path = tmp_path / "memory.sqlite"
    m = InspectableMemory(path)
    old = m.save([fact()])[0]
    assert m.save([fact()]) == [old]
    assert m.revision == 1
    assert read(m)["selected_ids"] == [old]
    assert read(m)["cache_hit"]
    new = m.save([fact(60, valid_from=1, recorded_at=T2)])[0]
    assert not read(m)["cache_hit"]
    assert read(m)["answer_status"] == "conflict"
    m.supersede(old, new, effective=1, recorded_at=T3)
    assert read(m)["selected_ids"] == [new]
    assert read(m, at=0)["selected_ids"] == [old]
    assert read(m, known_at=T1)["selected_ids"] == [old]
    assert read(m, known_at=T2)["answer_status"] == "conflict"
    assert read(m)["pairs"][0]["diagnosis"] == "version_change"
    m.close()
    reopened = InspectableMemory(path)
    assert read(reopened)["selected_ids"] == [new]
    assert len(read(reopened)["facts"]) == 2
    reopened.close()


def test_external_writer_invalidates_cache_and_return_values_are_isolated(tmp_path):
    path = tmp_path / "shared.sqlite"
    m, other = InspectableMemory(path), InspectableMemory(path)
    old = m.save([fact()])[0]
    read(m)["facts"].clear()
    assert len(read(m)["facts"]) == 1
    other.save([fact(60)])
    assert not read(m)["cache_hit"]
    assert read(m)["conflicts"]
    assert old in read(m)["selected_ids"]
    m.close()
    other.close()


def test_half_open_boundaries_scope_unknown_and_multivalued_relations():
    m = InspectableMemory()
    old, new, unknown = m.save(
        [
            fact(valid_to=1),
            fact(60, valid_from=1),
            fact(90, valid_from=None),
        ]
    )
    m.save([fact(80, scope=Scope("repo@pinned-chain", environment="test"))])
    assert read(m, at=0)["selected_ids"] == [old]
    assert read(m, at=1)["selected_ids"] == [new]
    assert unknown not in read(m)["selected_ids"]
    assert len(read(m, mode="baseline")["selected_ids"]) == 3
    assert read(m, mode="conflict")["answer_status"] == "conflict"
    assert read(m)["answer_status"] == "supported"
    m.save([fact("g", predicate="calls"), fact("h", predicate="calls")])
    assert not read(m)["conflicts"]
    m.save([fact("g", predicate="calls", negated=True)])
    assert len(read(m)["conflicts"]) == 1
    m.close()


def test_invalid_batch_is_atomic_and_replacements_validate_scope_cycles():
    m = InspectableMemory()
    with pytest.raises(ValueError):
        m.save([fact(), fact(60, valid_to=0)])
    assert not read(m)["facts"]
    a, b, c = m.save([fact(), fact(60), fact(90, entity="other")])
    with pytest.raises(ValueError):
        m.supersede(a, c, effective=1, recorded_at=T2)
    m.supersede(a, b, effective=1, recorded_at=T2)
    revision = m.revision
    m.supersede(a, b, effective=1, recorded_at=T2)
    assert m.revision == revision
    with pytest.raises(ValueError):
        m.supersede(b, a, effective=1, recorded_at=T3)
    m.close()


def test_replay_parent_immutable_and_cache_coordinates():
    m = InspectableMemory()
    m.save([fact(valid_to=1)])
    initial = read(m, at=0)
    first = m.save_run(initial)
    later = read(m, at=1)
    second = m.save_run(later, parent_id=first)
    assert m.get_run(first)["selected_ids"]
    assert not m.get_run(second)["selected_ids"]
    assert m.get_run(second)["parent_id"] == first
    assert not read(m, mode="baseline")["cache_hit"]
    with pytest.raises(ValueError):
        m.save_run({}, parent_id="missing")
    with pytest.raises(ValueError):
        read(m, known_at="2026-09-01")
    m.close()


def test_journal_reserved_id_and_corruption_are_rejected():
    m = InspectableMemory()
    with pytest.raises(ValueError):
        m.save_run({"run_id": "pretend-id"})
    run_id = m.save_run({"example": 1})
    with m.db:
        m.db.execute("UPDATE runs SET payload=? WHERE id=?", ('{"example":2}', run_id))
    with pytest.raises(ValueError):
        m.get_run(run_id)
    m.close()

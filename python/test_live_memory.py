import json
import threading
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path

import pytest
from inspectable_demo import DemoService, make_handler
from inspectable_memory import InspectableMemory
from live_memory import ENTITY, LiveLab


def test_live_save_conflict_replace_time_travel_and_restart(tmp_path):
    path = tmp_path / "lab.sqlite"
    memory = InspectableMemory(path)
    lab = LiveLab(memory)
    room = lab.create()["room"]
    assert lab.snapshot({"room": room})["answer_status"] == "unknown"
    first = lab.step({"room": room, "step": 1})
    assert first["answer_status"] == "supported"
    second = lab.step({"room": room, "step": 2})
    assert second["answer_status"] == "conflict"
    old_payload = next(f for f in second["facts"] if f["value"] == "30 s")
    third = lab.step({"room": room, "step": 3})
    assert third["answer_status"] == "supported" and len(third["selected_ids"]) == 1
    assert len(third["facts"]) == 2 and len(third["events"]) == 3
    assert any(p["diagnosis"] == "version_change" for p in third["pairs"])
    assert lab.snapshot({"room": room, "known": 2})["answer_status"] == "conflict"
    before = lab.snapshot({"room": room, "at": 0})
    assert before["selected_ids"] == [old_payload["id"]]
    assert lab.snapshot({"room": room, "at": 0})["cache_hit"]
    assert lab.snapshot({"room": room, "known": 0})["selected_ids"] == []
    # Re-running the guided action does not add another assertion/event.
    assert len(lab.step({"room": room, "step": 3})["events"]) == 3
    raw = json.loads(
        memory.db.execute(
            "SELECT payload FROM assertions WHERE id=?", (old_payload["id"],)
        ).fetchone()[0]
    )
    assert raw["valid_to"] is None  # original fact never overwritten
    memory.close()
    reopened = InspectableMemory(path)
    assert LiveLab(reopened).snapshot({"room": room})["selected_ids"] == third["selected_ids"]
    reopened.close()


def test_live_scope_unknown_dates_negation_and_invalid_write():
    memory = InspectableMemory()
    lab = LiveLab(memory)
    a, b = lab.create()["room"], lab.create()["room"]
    first = lab.step({"room": a, "step": 1})
    assert not lab.snapshot({"room": b})["facts"]
    with pytest.raises(ValueError, match="workspace"):
        lab.replace(
            {"room": b, "old_id": first["selected_ids"][0], "new_id": "none", "effective": 1}
        )
    request = {
        "room": a,
        "entity": ENTITY,
        "predicate": "default",
        "value": "60 s",
        "source": "visitor-note",
        "excerpt": "Demo assertion",
        "environment": "staging",
    }
    lab.save(request)
    assert lab.snapshot({"room": a})["answer_status"] == "supported"
    unknown = lab.save({**request, "environment": "production", "valid_from": None})
    assert unknown["answer_status"] == "supported"
    assert any(f["status"] == "unknown_validity" for f in unknown["facts"])
    negative = lab.save({**request, "environment": "production", "value": "30 s", "negated": True})
    assert negative["answer_status"] == "conflict"
    count = len(negative["facts"])
    with pytest.raises(ValueError):
        lab.save({**request, "at": -1})
    assert len(lab.snapshot({"room": a})["facts"]) == count
    memory.close()


def test_real_http_live_writes_and_origin_protection(tmp_path):
    root = Path(__file__).resolve().parents[1]
    service = DemoService(root / "demo/inspectable/fixture.json", tmp_path / "http.sqlite")
    server = HTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def post(path, body, origin=None):
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        connection.request("POST", path, json.dumps(body), headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    try:
        status, initial = post("/api/live/create", {})
        assert status == 200
        room = initial["room"]
        assert post("/api/live/step", {"room": room, "step": 1}, "https://other.example")[0] == 403
        assert post("/api/live/snapshot", {"room": room})[1]["facts"] == []
        for step in (1, 2, 3):
            status, result = post("/api/live/step", {"room": room, "step": step})
            assert status == 200
        assert result["answer_status"] == "supported"
        assert (
            post("/api/live/snapshot", {"room": room, "known": 2})[1]["answer_status"] == "conflict"
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        service.memory.close()

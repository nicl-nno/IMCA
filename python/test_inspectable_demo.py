"""Exercise real HTTP, fixture-based ranking and the persistent assertion journal."""

import io
import json
import threading
from email.message import Message
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inspectable_demo import DemoService, make_handler

FIXTURE = Path(__file__).resolve().parents[1] / "demo/inspectable/fixture.json"


def test_all_fixture_replays_reader_firewall_and_temporal_states(tmp_path):
    service = DemoService(FIXTURE, tmp_path / "memory.sqlite")
    for case_id, case in service.cases.items():
        original = service.retrieval({"case_id": case_id})
        assert original["score"] == pytest.approx(case["saved_graph_score"])
        assert len(original["top5"]) <= 5
        intervention = service.retrieval(
            {
                "case_id": case_id,
                "relation": "calls",
                "parent_id": original["run_id"],
                "disabled": ["bm25"],
            }
        )
        assert intervention["reader"] is None
        assert intervention["parent_id"] == original["run_id"]
        assert service.memory.get_run(original["run_id"])["reader"]["historical"]
    for case_id in service.temporal:
        conflict = service.temporal_recall({"case_id": case_id, "knowledge": 1, "at": 1})
        assert len(conflict["conflicts"]) == 1
        resolved = service.temporal_recall({"case_id": case_id, "knowledge": 2, "at": 1})
        assert not resolved["conflicts"]
        assert len(resolved["selected_ids"]) == 1
        assert len(resolved["facts"]) == 2
        cached = service.temporal_recall({"case_id": case_id, "knowledge": 2, "at": 1})
        assert cached["cache_hit"]
        historical = service.temporal_recall({"case_id": case_id, "knowledge": 2, "at": 0})
        assert historical["selected_ids"] != resolved["selected_ids"]
    service.memory.close()


def test_http_api_static_assets_origin_guards_and_export(tmp_path):
    service = DemoService(FIXTURE, tmp_path / "memory.sqlite")
    server = HTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        for url in ("/", "/app.js", "/style.css", "/api/catalog"):
            connection.request("GET", url)
            response = connection.getresponse()
            assert response.status == 200
            assert response.getheader("Content-Security-Policy")
            response.read()
        body = json.dumps({"case_id": next(iter(service.cases))})
        connection.request("POST", "/api/replay", body, {"Content-Type": "application/json"})
        response = connection.getresponse()
        assert response.status == 200
        run = json.loads(response.read())
        connection.request("GET", "/api/run?id=" + run["run_id"])
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["top5"] == run["top5"]
        connection.request(
            "POST",
            "/api/replay",
            body,
            {"Content-Type": "application/json", "Origin": "https://external.test"},
        )
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.request("GET", "/../../AGENTS.md")
        response = connection.getresponse()
        assert response.status == 404
        response.read()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        service.memory.close()


def test_fixture_tampering_fails_closed(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["validation"]["graph_top5"] = 999
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        DemoService(altered, ":memory:")


def test_rejected_post_consumes_bounded_body_before_closing_connection(tmp_path):
    # An unread request body causes a TCP reset on Windows and can hide the 403.
    service = DemoService(FIXTURE, tmp_path / "memory.sqlite")
    handler = object.__new__(make_handler(service))
    body = b'{"case_id":"unused"}'
    handler.headers = Message()
    for key, value in {
        "Host": "127.0.0.1:8765",
        "Origin": "https://external.test",
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }.items():
        handler.headers[key] = value
    handler.server = SimpleNamespace(server_port=8765)
    handler.connection = Mock()
    handler.rfile = io.BytesIO(body)
    handler.path = "/api/replay"
    sent = []
    handler.send_data = lambda payload, status=200: sent.append(status)
    handler.do_POST()
    assert sent == [403]
    assert handler.rfile.tell() == len(body)
    service.memory.close()

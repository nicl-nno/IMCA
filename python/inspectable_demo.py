"""Local-only interactive demo; no API keys, hosted writes, or model calls."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from code_metrics import score_expected
from inspectable_memory import Fact, InspectableMemory, Scope, digest
from live_memory import LiveLab
from retrieval_inspection import diagnose_stages, replay

ROOT = Path(__file__).resolve().parents[1]

KNOWLEDGE = ("2026-09-01T00:00:00Z", "2026-09-02T00:00:00Z", "2026-09-03T00:00:00Z")
DEMO_SCOPE = Scope("fastapi-controlled-linear-demo", "synthetic-chain", "default")


def seed_temporal(memory: InspectableMemory, cases: list[dict]) -> dict:
    ids = {}
    for case in cases:
        evidence = {
            "source": case["source"],
            "line_start": case["line_start"],
            "text": case["source_text"],
            "source_sha256": case["source_sha256"],
            "kind": "verified_base_source_in_controlled_timeline",
        }
        old = Fact(
            case["entity"], "default", case["original"], DEMO_SCOPE, 0, None, KNOWLEDGE[0], evidence
        )
        # A synthetic event never claims to be a real source edit in the benchmark.
        new = replace(
            old,
            value=case["changed"],
            valid_from=1,
            recorded_at=KNOWLEDGE[1],
            evidence={
                "source": f"scenario://{case['id']}/injected-change",
                "kind": "synthetic_change",
                "base_source": case["source"],
                "text": f"Controlled change: {case['parameter']} = {case['changed']!r}",
            },
        )
        old_id, new_id = memory.save([old, new])
        memory.supersede(old_id, new_id, effective=1, recorded_at=KNOWLEDGE[2])
        ids[case["id"]] = (old_id, new_id)
    return ids


class DemoService:
    def __init__(self, fixture: Path, database: str | Path):
        self.fixture = json.loads(fixture.read_text(encoding="utf-8"))
        payload = {k: v for k, v in self.fixture.items() if k != "content_hash"}
        if digest(payload) != self.fixture.get("content_hash"):
            raise ValueError("fixture hash mismatch: rebuild the demo fixture")
        self.cases = {c["id"]: c for c in self.fixture["cases"]}
        self.temporal = {c["id"]: c for c in self.fixture["temporal_cases"]}
        self.memory = InspectableMemory(database)
        seed_temporal(self.memory, list(self.temporal.values()))
        self.live = LiveLab(self.memory)

    def retrieval(self, request: dict) -> dict:
        case = self.cases[request["case_id"]]
        relation = request.get("relation", "references")
        route = case["routes"][relation]
        disabled = tuple(request.get("disabled", []))
        started = time.perf_counter()
        run = replay(route, disabled=disabled)
        run["replay_ms"] = (time.perf_counter() - started) * 1000
        original = relation == "references" and not disabled
        reader = case["reader"] if original else None
        # Scoring and reader attribution occur only after the top-5 is frozen.
        run.update(
            {
                "case_id": case["id"],
                "query": case["query"],
                "relation": relation,
                "pins": self.fixture["pins"],
                "fixture_hash": self.fixture["content_hash"],
                "score": score_expected(case["expected"], run["top5"])["score"],
                "stage_diagnoses": diagnose_stages(
                    run, case["expected"], reader["ids"] if reader else None
                ),
                "reader": reader,
                "execution": "live_ranking_over_frozen_candidates",
            }
        )
        parent = request.get("parent_id")
        if parent and self.memory.get_run(parent).get("case_id") != case["id"]:
            raise ValueError("parent must belong to the same case")
        run_id = self.memory.save_run(run, parent_id=parent)
        return {"run_id": run_id, "parent_id": parent, **run}

    def temporal_recall(self, request: dict) -> dict:
        case = self.temporal[request["case_id"]]
        knowledge = request.get("knowledge", 2)
        if type(knowledge) is not int or knowledge not in range(3):
            raise ValueError("knowledge must be a demo position 0, 1 or 2")
        result = self.memory.recall(
            at=request.get("at", 1),
            known_at=KNOWLEDGE[knowledge],
            scope=DEMO_SCOPE,
            entity=case["entity"],
            mode=request.get("mode", "combined"),
        )
        result.update(
            {
                "case_id": case["id"],
                "fixture_hash": self.fixture["content_hash"],
                "synthetic": True,
                "knowledge_position": knowledge,
            }
        )
        parent = request.get("parent_id")
        if parent and self.memory.get_run(parent).get("case_id") != case["id"]:
            raise ValueError("parent must belong to the same case")
        run_id = self.memory.save_run(result, parent_id=parent)
        return {"run_id": run_id, "parent_id": parent, **result}


def make_handler(service: DemoService):
    class Handler(BaseHTTPRequestHandler):
        def send_data(self, payload, status=200, mime="application/json; charset=utf-8"):
            data = (
                payload
                if isinstance(payload, bytes)
                else json.dumps(payload, ensure_ascii=False).encode()
            )
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(data)

        def trusted(self):
            allowed = {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }
            return self.headers.get("Host") in allowed

        def do_GET(self):
            if not self.trusted():
                return self.send_data({"error": "invalid host"}, 403)
            parsed = urlparse(self.path)
            if parsed.path == "/api/catalog":
                return self.send_data(service.fixture)
            if parsed.path == "/api/run":
                try:
                    return self.send_data(service.memory.get_run(parse_qs(parsed.query)["id"][0]))
                except (KeyError, IndexError):
                    return self.send_data({"error": "unknown run"}, 404)
                except ValueError:
                    return self.send_data({"error": "run integrity check failed"}, 409)
            paths = {
                "/": ("../live/index.html", "text/html; charset=utf-8"),
                "/live": ("../live/index.html", "text/html; charset=utf-8"),
                "/replay": ("index.html", "text/html; charset=utf-8"),
                "/live.js": ("../live/live.js", "text/javascript; charset=utf-8"),
                "/live.css": ("../live/live.css", "text/css; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            if parsed.path not in paths:
                return self.send_data({"error": "not found"}, 404)
            name, mime = paths[parsed.path]
            return self.send_data((ROOT / "demo/inspectable" / name).read_bytes(), mime=mime)

        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16384:
                    raise ValueError("invalid request size")
                # Drain a bounded body before closing even on rejection. Otherwise
                # Windows can reset the TCP connection before the client sees 403.
                self.connection.settimeout(5)
                body = self.rfile.read(size)
                if len(body) != size:
                    raise ValueError("incomplete request")
                origin = self.headers.get("Origin")
                if not self.trusted() or (
                    origin and origin != f"http://{self.headers.get('Host')}"
                ):
                    return self.send_data({"error": "cross-origin writes are disabled"}, 403)
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("application/json required")
                request = json.loads(body)
                if not isinstance(request, dict):
                    raise ValueError("request must be an object")
                live_actions = {
                    "/api/live/create": lambda _: service.live.create(),
                    "/api/live/save": service.live.save,
                    "/api/live/replace": service.live.replace,
                    "/api/live/step": service.live.step,
                    "/api/live/snapshot": service.live.snapshot,
                }
                if self.path in live_actions:
                    result = live_actions[self.path](request)
                elif self.path == "/api/replay":
                    result = service.retrieval(request)
                elif self.path == "/api/temporal":
                    result = service.temporal_recall(request)
                else:
                    return self.send_data({"error": "not found"}, 404)
                self.send_data(result)
            except (ValueError, KeyError, TypeError, IndexError, TimeoutError) as exc:
                self.send_data({"error": str(exc)}, 400)

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", type=Path, default=ROOT / ".inspectable/demo.sqlite")
    parser.add_argument("--fixture", type=Path, default=ROOT / "demo/inspectable/fixture.json")
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    service = DemoService(args.fixture, args.database)
    server = HTTPServer(("127.0.0.1", args.port), make_handler(service))
    print(f"Inspectable Memory: http://127.0.0.1:{server.server_port} (local only)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.memory.close()


if __name__ == "__main__":
    main()

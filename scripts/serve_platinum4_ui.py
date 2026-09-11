#!/usr/bin/env python3
"""Serve the Platinum 4 briefing UI (chat + markdown + mermaid).

  python scripts/serve_platinum4_ui.py
  python scripts/serve_platinum4_ui.py --port 8765
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.platinum4.errors import TEST_SEALED, BotError
from src.modeling.platinum4.ui_api import bootstrap, run_ui_turn, stack_payload

UI_DIR = REPO / "platinum4" / "ui"
SESSIONS: dict[str, dict] = {}


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".html": "text/html",
        ".json": "application/json",
    }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid json: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("body must be an object")
        return data

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        self.path = parsed.path or "/"
        if parsed.path == "/api/meta":
            self._json(bootstrap())
            return
        if parsed.path == "/api/stack":
            qs = parse_qs(parsed.query)
            project = (qs.get("project_key") or [""])[0]
            scenario = (qs.get("scenario") or ["baseline"])[0]
            try:
                self._json(stack_payload(project, scenario))
            except (ValueError, KeyError, FileNotFoundError) as exc:
                self._json({"error": True, "message": str(exc)}, 400)
            return
        if parsed.path in {"/", "/index.html"}:
            self.path = "/index.html"
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/turn":
            self._json({"error": True, "message": "not found"}, 404)
            return
        try:
            body = self._read_json()
            if str(body.get("split") or "val") == "test":
                raise BotError(TEST_SEALED, "2024 test is sealed.")
            mode = str(body.get("mode") or "chat").strip().lower()
            view = run_ui_turn(
                SESSIONS,
                session_id=body.get("session_id"),
                question=str(body.get("question") or body.get("focus") or ""),
                project_key=str(body.get("project_key") or ""),
                scenario=str(body.get("scenario") or "baseline"),
                want_diagram=bool(body.get("want_diagram", True)),
                reset=bool(body.get("reset")),
                mode=mode,
                fmt=str(body.get("format") or "long"),
                focus=str(body.get("focus") or body.get("question") or ""),
            )
            self._json(view, 400 if view.get("error") else 200)
        except BotError as exc:
            self._json({"error": True, "error_code": exc.code, "message": str(exc)}, 400)
        except (ValueError, KeyError, FileNotFoundError) as exc:
            self._json({"error": True, "message": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": True, "message": str(exc)}, 500)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description="Platinum 4 briefing UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not (UI_DIR / "index.html").exists():
        print(f"missing {UI_DIR / 'index.html'}", flush=True)
        return 2
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Platinum 4 UI  {url}", flush=True)
    print("CatBoost stack. gpt-4.1 only. 2024 sealed.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

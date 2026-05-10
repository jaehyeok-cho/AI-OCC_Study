"""Local HTTP control server for the Symbol Detector PyQt app.

The MCP server talks to this module over localhost. This file deliberately uses
only Python standard-library networking so the desktop app does not need Flask,
FastAPI, or another web framework.

To add a new app command:
1. Add a command name in _dispatch().
2. Implement the behavior on MainWindow, or call an existing MainWindow method.
3. Add a matching MCP tool in ../../symbol_mcp_server.py.
"""

from __future__ import annotations

import json
import queue
import threading
import traceback
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from PyQt6.QtCore import QTimer


@dataclass
class CommandRequest:
    command: str
    payload: dict[str, Any]
    event: threading.Event
    result: dict[str, Any] | None = None


class LocalControlServer:
    def __init__(self, window, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.window = window
        self.host = host
        self.port = port
        self._queue: queue.Queue[CommandRequest] = queue.Queue()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

        self._timer = QTimer(window)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._process_pending)

    def start(self) -> None:
        if self._httpd is not None:
            return

        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path.rstrip("/") in {"", "/health"}:
                    self._send_json({"ok": True, "service": "symbol-detector-app"})
                else:
                    self._send_json({"ok": False, "error": "Unknown endpoint"}, status=404)

            def do_POST(self) -> None:
                command = self.path.strip("/")
                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw_body.decode("utf-8") or "{}")
                    if not isinstance(payload, dict):
                        raise ValueError("JSON body must be an object.")
                    response = bridge.submit(command, payload)
                    self._send_json(response)
                except Exception as exc:
                    self._send_json(
                        {
                            "ok": False,
                            "error": str(exc),
                            "traceback": traceback.format_exc(limit=6),
                        },
                        status=500,
                    )

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
                encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="SymbolDetectorLocalControl",
            daemon=True,
        )
        self._thread.start()
        self._timer.start()
        print(f"Symbol Detector local control server listening on http://{self.host}:{self.port}")

    def stop(self) -> None:
        self._timer.stop()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def submit(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = CommandRequest(command=command, payload=payload, event=threading.Event())
        self._queue.put(request)
        if not request.event.wait(timeout=900):
            return {"ok": False, "error": f"Command timed out: {command}"}
        return request.result or {"ok": False, "error": "Command returned no result."}

    def _process_pending(self) -> None:
        for _ in range(10):
            try:
                request = self._queue.get_nowait()
            except queue.Empty:
                return

            try:
                request.result = self._dispatch(request.command, request.payload)
            except Exception as exc:
                request.result = {
                    "ok": False,
                    "command": request.command,
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=8),
                }
            finally:
                request.event.set()

    def _dispatch(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        window = self.window

        if command == "status":
            return {"ok": True, "data": window.api_status()}
        if command == "list_symbols":
            return {"ok": True, "data": window.api_list_symbols()}
        if command == "open_file":
            return {
                "ok": True,
                "data": window.api_open_file(
                    payload["file_path"],
                    int(payload.get("page_index", 0)),
                ),
            }
        if command == "load_page":
            return {"ok": True, "data": window.api_load_page(int(payload["page_index"]))}
        if command == "select_symbol":
            return {"ok": True, "data": window.api_select_symbol(payload["label"])}
        if command == "set_confidence":
            return {
                "ok": True,
                "data": window.api_set_confidence(float(payload["conf_threshold"])),
            }
        if command == "run_yolo":
            return {
                "ok": True,
                "data": window.api_run_yolo(
                    payload.get("target_class"),
                    payload.get("conf_threshold"),
                ),
            }
        if command == "run_vlm":
            return {
                "ok": True,
                "data": window.api_run_vlm(
                    payload.get("target_class"),
                    payload.get("conf_threshold"),
                ),
            }
        if command == "get_results":
            return {"ok": True, "data": window.api_get_results()}
        if command == "clear_results":
            window.clear_bounding_boxes()
            return {"ok": True, "data": window.api_get_results()}
        if command == "save_result_image":
            return {
                "ok": True,
                "data": window.api_save_result_image(payload["output_path"]),
            }

        return {"ok": False, "error": f"Unknown command: {command}"}

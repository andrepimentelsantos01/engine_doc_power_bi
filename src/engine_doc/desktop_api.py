"""Local-only JSON API used by the Flutter desktop presentation layer."""

from __future__ import annotations

import argparse
import json
import sys
import os
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, unquote

from .desktop_service import DesktopService, DesktopServiceError


DEFAULT_DESKTOP_PORT = 8766
MAX_REQUEST_BYTES = 1_048_576
PICKER_LOCK = threading.Lock()


def select_project_folder() -> str | None:
    # All Tk operations stay on the same request thread.
    import tkinter as tk
    from tkinter import filedialog
    with PICKER_LOCK:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            return filedialog.askdirectory(
                parent=root, title="Selecione a pasta do projeto PBIP",
                mustexist=True,
            ) or None
        finally:
            root.destroy()


class DesktopApiHandler(BaseHTTPRequestHandler):
    """Small request router; request bodies and credentials are never logged."""

    server_version = "EngineDocDesktop/0.1"

    @property
    def service(self) -> DesktopService:
        return self.server.service  # type: ignore[attr-defined,no-any-return]

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if not self._local_request():
            return
        path = urlsplit(self.path).path
        if path == "/health":
            self._send_json(200, {"success": True, "service": "engine-doc-desktop",
                                 "web": True, "root": str(Path(__file__).resolve().parents[2])})
            return
        base = Path(__file__).resolve().parents[2] / "frontend" / "build" / "web"
        target = (base / unquote(path).lstrip("/")).resolve()
        if not target.is_relative_to(base.resolve()):
            self._send_error(403, "invalid_path", "Caminho inválido.")
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self._send_error(404, "not_found", "Arquivo não encontrado. Execute .\\app.")
            return
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _local_request(self) -> bool:
        host = f"127.0.0.1:{self.server.server_port}"
        if (self.headers.get("Host") != host or
                self.headers.get("Origin") not in (None, f"http://{host}")):
            self._send_error(403, "origin", "Origem não permitida.")
            return False
        return True

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if not self._local_request():
            return
        path = urlsplit(self.path).path
        try:
            body = self._read_json()
            if path == "/project/select":
                result = {"success": True, "project_path": select_project_folder()}
            elif path == "/output/open":
                target = Path(body.get("path", "")).resolve()
                if not target.is_relative_to(self.service.output_dir):
                    raise DesktopServiceError("invalid_path", "Saída não autorizada.", 403)
                if not target.exists() or (target.is_file() and target.suffix.lower() != ".txt"):
                    raise DesktopServiceError("invalid_path", "Arquivo de saída não encontrado.")
                os.startfile(str(target))
                result = {"success": True}
            elif path == "/analyze":
                result = self.service.analyze_project(
                    body.get("project_path", ""),
                    include_content=body.get("include_content", True) is not False,
                )
            elif path == "/ai/openrouter/models":
                result = self.service.list_openrouter_models(body.get("api_key", ""))
            elif path == "/ai/generate":
                result = self.service.generate_ai(
                    mode=body.get("mode", ""),
                    provider=body.get("provider", ""),
                    api_key=body.get("api_key", ""),
                    xray_path_value=body.get("xray_path", ""),
                    model=body.get("model"),
                    include_content=body.get("include_content", True) is not False,
                )
            elif path == "/results":
                result = self.service.existing_results(
                    body.get("xray_path", ""),
                    include_content=body.get("include_content", True) is not False,
                )
            else:
                self._send_error(404, "not_found", "Operação não encontrada.")
                return
            self._send_json(200, result)
        except DesktopServiceError as exc:
            self._send_error(exc.status, exc.code, exc.message)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            self._send_error(400, "invalid_json", "A solicitação enviada é inválida.")
        except Exception as exc:  # prevent tracebacks and secrets from crossing the API
            print(f"[desktop-api] erro interno: {exc.__class__.__name__}")
            self._send_error(
                500,
                "internal_error",
                "O Engine Doc encontrou um erro inesperado. Tente novamente.",
            )

    def _read_json(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/json"):
            raise ValueError("content type")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("content length") from None
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("request size")
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("json object")
        return body

    def _send_error(self, status: int, code: str, message: str) -> None:
        self._send_json(
            status,
            {"success": False, "error": {"code": code, "message": message}},
        )

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        # BaseHTTPRequestHandler logs only method/path/status here. Bodies are
        # intentionally never rendered because AI requests contain API keys.
        print(f"[desktop-api] {self.address_string()} - {format % args}")


class DesktopApiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], service: DesktopService) -> None:
        self.service = service
        super().__init__(address, DesktopApiHandler)


def create_server(output_dir: Path, port: int = DEFAULT_DESKTOP_PORT) -> DesktopApiServer:
    """Create a server bound exclusively to the IPv4 loopback interface."""
    return DesktopApiServer(("127.0.0.1", port), DesktopService(output_dir))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engine Doc local desktop bridge")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--port", type=int, default=DEFAULT_DESKTOP_PORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    server = create_server(output_dir, args.port)
    print(f"[ready] Engine Doc Desktop API: http://127.0.0.1:{args.port}")
    print("[info] Pressione Ctrl+C para encerrar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[info] API local encerrada.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

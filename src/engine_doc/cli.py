"""Command-line entry point and local documentation preview."""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
from pathlib import Path

from . import __version__
from .analysis.dependencies import analyze_dependencies
from .discovery import discover_projects
from .exporters.html import write_index
from .exporters.markdown import export_project
from .parsers import parse_report, parse_semantic_model


DEFAULT_PORT = 8765


def analyze(input_dir: Path, output_dir: Path) -> int:
    projects = discover_projects(input_dir)
    exported = []
    for project in projects:
        if project.semantic_model_path:
            try:
                project.model = parse_semantic_model(project.semantic_model_path, project.name)
                project.dependencies = analyze_dependencies(project.model)
            except Exception as exc:  # keep partial documentation useful
                project.warnings.append(f"Semantic model could not be parsed: {exc}")
        else:
            project.warnings.append("Semantic model folder was not found.")

        if project.report_path:
            try:
                project.report = parse_report(project.report_path, project.name)
            except Exception as exc:  # keep partial documentation useful
                project.warnings.append(f"Report could not be parsed: {exc}")
        else:
            project.warnings.append("Report folder was not found.")

        target = export_project(project, output_dir)
        exported.append((project, target))
        print(f"[ok] {project.name}: {target}")

    write_index(output_dir, exported)
    if not projects:
        print(f"[info] No PBIP project found in {input_dir}")
    print(f"[ok] Documentation index: {output_dir / 'index.html'}")
    return len(projects)


class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".md": "text/markdown; charset=utf-8",
        ".mmd": "text/plain; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }

    def log_message(self, format: str, *args: object) -> None:
        print(f"[http] {format % args}")


class PreviewServer(http.server.ThreadingHTTPServer):
    # Prevent two Engine Doc processes from silently sharing the fixed port.
    allow_reuse_address = False


def serve(output_dir: Path, port: int) -> None:
    handler = functools.partial(PreviewHandler, directory=str(output_dir.resolve()))
    server = PreviewServer(("127.0.0.1", port), handler)
    print(f"[ready] Engine Doc Power BI: http://127.0.0.1:{port}")
    print("[info] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[info] Server stopped.")
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="engine-doc-power-bi",
        description="Generate technical documentation from Power BI PBIP projects.",
    )
    parser.add_argument("--input", type=Path, default=Path("input"), help="PBIP input directory")
    parser.add_argument("--output", type=Path, default=Path("output"), help="Documentation output")
    parser.add_argument("--serve", action="store_true", help="Serve output as a local preview")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Preview TCP port")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    analyze(input_dir, output_dir)
    if args.serve:
        serve(output_dir, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())

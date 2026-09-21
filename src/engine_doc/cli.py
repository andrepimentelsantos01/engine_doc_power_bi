"""Command-line entry point and local documentation preview."""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
from collections import Counter
from collections.abc import Callable
from getpass import getpass
from pathlib import Path

from . import __version__
from .ai import NvidiaClientError, review_ray_x
from .analysis.dependencies import analyze_dependencies
from .discovery import discover_projects
from .exporters.html import write_index
from .exporters.markdown import export_project
from .exporters.text import ray_x_path, safe_filename
from .models import PBIPProject
from .parsers import parse_report, parse_semantic_model


DEFAULT_PORT = 8765


ExportedProject = tuple[PBIPProject, Path]


def _relative_output_paths(
    projects: list[PBIPProject], input_dir: Path
) -> list[Path]:
    """Mirror each project container and disambiguate shared containers."""
    input_root = input_dir.resolve()
    candidates: list[Path] = []
    for project in projects:
        try:
            relative = project.root.resolve().relative_to(input_root)
        except ValueError:
            relative = Path()
        candidates.append(
            relative if relative.parts else Path(safe_filename(project.name))
        )

    counts = Counter(path.as_posix().casefold() for path in candidates)
    planned = [
        path / safe_filename(project.name)
        if counts[path.as_posix().casefold()] > 1
        else path
        for project, path in zip(projects, candidates, strict=True)
    ]
    unique: list[Path] = []
    used: set[str] = set()
    for path in planned:
        candidate = path
        suffix = 2
        while candidate.as_posix().casefold() in used:
            candidate = path.with_name(f"{path.name}_{suffix}")
            suffix += 1
        used.add(candidate.as_posix().casefold())
        unique.append(candidate)
    return unique


def analyze_projects(input_dir: Path, output_dir: Path) -> list[ExportedProject]:
    print("=" * 60)
    print("ENGINE DOC POWER BI")
    print("=" * 60)
    print("\n[1/4] Localizando projeto PBIP...")
    projects = discover_projects(input_dir)
    exported: list[ExportedProject] = []
    if projects:
        print(f"[OK] {len(projects)} projeto(s) localizado(s).")
    print("\n[2/4] Extraindo arquitetura do projeto...")
    output_paths = _relative_output_paths(projects, input_dir)
    for project, relative_output in zip(projects, output_paths, strict=True):
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

        print(f"\n[3/4] Gerando raio-X de {project.name}...")
        target = export_project(project, output_dir, relative_output)
        exported.append((project, target))
        generated_ray_x = ray_x_path(target, project.name)
        print("[OK] Raio-X gerado com sucesso.")
        print(f"Arquivo: {generated_ray_x}")

    write_index(output_dir, exported)
    if not projects:
        print(f"[INFO] Nenhum projeto PBIP encontrado em {input_dir}")
    print(f"[OK] Índice da documentação: {output_dir / 'index.html'}")
    return exported


def analyze(input_dir: Path, output_dir: Path) -> int:
    """Compatibility wrapper for the deterministic extraction stage."""
    return len(analyze_projects(input_dir, output_dir))


def run_ai_reviews(
    exported: list[ExportedProject],
    *,
    key_reader: Callable[[str], str] = getpass,
) -> list[Path]:
    """Prompt only after all text X-rays exist, then review them safely."""
    ray_x_files = [ray_x_path(target, project.name) for project, target in exported]
    if not ray_x_files or not all(path.is_file() for path in ray_x_files):
        return []

    print("\n" + "=" * 60)
    print("ANÁLISE INTELIGENTE")
    print("=" * 60)
    print(
        "\nO conteúdo do raio-X será enviado à API NVIDIA NIM para "
        "realização da análise técnica."
    )
    print("Para continuar, informe sua NVIDIA API Key.\n")
    try:
        api_key = key_reader("NVIDIA API Key: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[INFO] Análise por IA cancelada. O raio-X foi preservado.")
        return []
    if not api_key:
        print("[ERRO] A NVIDIA API Key não foi informada. A etapa de IA foi encerrada.")
        return []

    generated: list[Path] = []
    try:
        for ray_x_file in ray_x_files:
            print("\n[4/4] Analisando projeto com IA...")
            try:
                destination = review_ray_x(ray_x_file, api_key)
            except NvidiaClientError as exc:
                print(f"[ERRO] {exc}")
                print("[INFO] O raio-X foi preservado. Somente a etapa de IA foi encerrada.")
                return generated
            except OSError:
                print("[ERRO] Não foi possível gravar a análise produzida pela NVIDIA.")
                print("[INFO] O raio-X foi preservado. Somente a etapa de IA foi encerrada.")
                return generated
            generated.append(destination)
            print("[OK] Análise concluída.")
            print(f"Arquivo: {destination}")
    finally:
        del api_key
    return generated


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
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Generate the deterministic X-ray without requesting an NVIDIA review",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = analyze_projects(input_dir, output_dir)
    if exported and not args.skip_ai:
        run_ai_reviews(exported)
    print("\nEngine Doc Power BI finalizado.")
    if args.serve:
        serve(output_dir, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())

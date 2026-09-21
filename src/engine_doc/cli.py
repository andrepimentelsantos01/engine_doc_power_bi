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
from .ai import (
    NVIDIA_MODEL,
    OPENROUTER_MODEL,
    NvidiaClientError,
    OpenRouterClientError,
    ReviewOutputError,
    document_ray_x,
    list_free_models,
    request_openrouter_review,
    review_ray_x,
)
from .analysis.dependencies import analyze_dependencies
from .analysis.report_usage import analyze_report_dependencies
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
    print("-" * 60)
    print("ENGINE DOC POWER BI")
    print("-" * 60)
    print(f"\nProcurando projetos em {input_dir}...")
    projects = discover_projects(input_dir)
    exported: list[ExportedProject] = []
    if not projects:
        write_index(output_dir, exported)
        print(f"\n[ERRO] Nenhum projeto PBIP foi encontrado em {input_dir}.")
        print("Coloque um projeto PBIP nessa pasta e execute novamente.")
        return exported

    print(f"[OK] {len(projects)} projeto(s) encontrado(s).")
    output_paths = _relative_output_paths(projects, input_dir)
    for project, relative_output in zip(projects, output_paths, strict=True):
        print("\n" + "-" * 60)
        print(f"Projeto encontrado: {project.name}")
        print("Analisando projeto...\n")

        if project.semantic_model_path:
            try:
                project.model = parse_semantic_model(
                    project.semantic_model_path,
                    project.name,
                    warnings=project.warnings,
                )
                project.dependencies = analyze_dependencies(project.model)
            except FileNotFoundError:
                project.warnings.append(
                    "A definição do modelo semântico não foi encontrada."
                )
            except (OSError, UnicodeError, ValueError, KeyError, TypeError):
                project.warnings.append(
                    "O modelo semântico não pôde ser interpretado completamente."
                )
        else:
            project.warnings.append("Modelo semântico não encontrado.")

        if project.model:
            table_count = len(project.model.tables)
            column_count = sum(len(table.columns) for table in project.model.tables)
            measure_count = sum(len(table.measures) for table in project.model.tables)
            print("[OK] Modelo semântico")
            print(f"[OK] Tabelas e colunas: {table_count} tabela(s), {column_count} coluna(s)")
            print(f"[OK] Medidas DAX: {measure_count}")
            print(f"[OK] Relacionamentos: {len(project.model.relationships)}")
        else:
            print("[AVISO] Modelo semântico não disponível.")

        if project.report_path:
            try:
                project.report = parse_report(
                    project.report_path,
                    project.name,
                    warnings=project.warnings,
                )
            except FileNotFoundError:
                project.warnings.append("A definição do relatório não foi encontrada.")
            except (OSError, UnicodeError, ValueError, KeyError, TypeError):
                project.warnings.append(
                    "O relatório não pôde ser interpretado completamente."
                )
        else:
            project.warnings.append("Relatório não encontrado.")

        if project.report:
            visual_count = sum(page.visual_count for page in project.report.pages)
            print(f"[OK] Páginas: {len(project.report.pages)}")
            print(f"[OK] Visuais: {visual_count}")
        else:
            print("[AVISO] Camada de relatório não disponível.")

        if not project.model and not project.report:
            print("[ERRO] Não há informações suficientes para gerar o raio-X deste projeto.")
            if project.warnings:
                print(f"[AVISO] {len(project.warnings)} aviso(s) registrado(s).")
            continue

        project.dependencies.extend(analyze_report_dependencies(project))
        print(f"[OK] Dependências: {len(project.dependencies)}")

        print("Gerando raio-X...")
        target = export_project(project, output_dir, relative_output)
        exported.append((project, target))
        generated_ray_x = ray_x_path(target, project.name)
        print("[OK] Lineage")
        print("\nRaio-X gerado com sucesso.")
        print(f"Arquivo: {generated_ray_x}")
        if project.warnings:
            print(f"\nAnálise concluída com {len(project.warnings)} aviso(s).")
            print("Consulte a seção AVISOS do raio-X.")

    write_index(output_dir, exported)
    if exported:
        print(f"\n[OK] Índice da documentação: {output_dir / 'index.html'}")
    else:
        print("\n[ERRO] Nenhum projeto pôde ser analisado.")
    return exported


def analyze(input_dir: Path, output_dir: Path) -> int:
    """Compatibility wrapper for the deterministic extraction stage."""
    return len(analyze_projects(input_dir, output_dir))


def run_ai_reviews(
    exported: list[ExportedProject],
    *,
    key_reader: Callable[[str], str] = getpass,
    input_reader: Callable[[str], str] = input,
) -> list[Path]:
    """Choose an AI output and provider only after all text X-rays exist."""
    ray_x_files = [ray_x_path(target, project.name) for project, target in exported]
    if not ray_x_files or not all(path.is_file() for path in ray_x_files):
        return []

    try:
        while True:
            print("\n" + "-" * 60)
            print("INTELIGÊNCIA ARTIFICIAL")
            print("-" * 60)
            print("O que deseja gerar?")
            print("[1] Análise crítica")
            print("[2] Documentação executiva/técnica")
            print("[0] Finalizar sem IA")
            while True:
                mode_choice = input_reader("\nEscolha: ").strip()
                if mode_choice in {"0", "1", "2"}:
                    break
                print("[ERRO] Opção inválida. Informe 0, 1 ou 2.")

            if mode_choice == "0":
                print("[INFO] Finalizado sem processamento com IA.")
                return []

            print("\nEscolha o provedor:")
            print("[1] NVIDIA NIM")
            print("[2] OpenRouter")
            print("[0] Voltar")
            while True:
                provider_choice = input_reader("\nEscolha: ").strip()
                if provider_choice in {"0", "1", "2"}:
                    break
                print("[ERRO] Opção inválida. Informe 0, 1 ou 2.")
            if provider_choice == "0":
                continue
            break
    except (EOFError, KeyboardInterrupt):
        print("\n[INFO] Processamento por IA cancelado. Os raios-X foram preservados.")
        return []

    if mode_choice == "1":
        processor = review_ray_x
        action_progress = "Analisando projeto com IA"
        action_success = "Análise concluída"
    else:
        processor = document_ray_x
        action_progress = "Gerando documentação com IA"
        action_success = "Documentação concluída"

    review_client = None
    if provider_choice == "1":
        provider = "NVIDIA NIM"
        model = NVIDIA_MODEL
        print("\nO raio-X será enviado à NVIDIA NIM para processamento.")
        key_prompt = "NVIDIA API Key: "
    else:
        provider = "OpenRouter"
        model = OPENROUTER_MODEL
        print(
            "\nO raio-X será enviado ao OpenRouter e processado pelo provedor "
            "do modelo selecionado."
        )
        key_prompt = "OpenRouter API Key: "

    print("A chave será usada somente nesta execução e não será salva.\n")
    try:
        api_key = key_reader(key_prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[INFO] Processamento por IA cancelado. Os raios-X foram preservados.")
        return []
    if not api_key:
        print(f"[ERRO] A API Key do {provider} não foi informada. A etapa de IA foi encerrada.")
        return []

    if provider_choice == "2":
        try:
            free_models = list_free_models(api_key)
        except OpenRouterClientError as exc:
            print("[AVISO] Não foi possível concluir a análise com IA.")
            print(f"Causa: {exc}")
            print("Não foi possível confirmar que este modelo é gratuito no OpenRouter.")
            print("[INFO] Nenhuma requisição de análise foi realizada.")
            return []

        confirmed_ids = {available_model.id for available_model in free_models}
        if OPENROUTER_MODEL not in confirmed_ids:
            print("[AVISO] Não foi possível concluir a análise com IA.")
            print("Não foi possível confirmar que este modelo é gratuito no OpenRouter.")
            print("[INFO] Nenhuma requisição de análise foi realizada.")
            return []

        selectable_models = [
            available_model
            for available_model in free_models
            if available_model.id != OPENROUTER_MODEL
        ]
        print("\nModelos gratuitos disponíveis:")
        for index, available_model in enumerate(selectable_models, start=1):
            context = (
                f"{available_model.context_length:,}".replace(",", ".")
                if available_model.context_length
                else "não informado"
            )
            print(f"\n[{index}] {available_model.name}")
            print(f"    Contexto: {context} tokens")
        print(f"\n[A] Automático — OpenRouter Free Router ({OPENROUTER_MODEL})")
        try:
            while True:
                model_choice = input_reader("\nEscolha [A]: ").strip().upper() or "A"
                if model_choice == "A":
                    break
                if model_choice.isdigit() and 1 <= int(model_choice) <= len(selectable_models):
                    break
                print("[ERRO] Selecione um número exibido na lista ou A.")
        except (EOFError, KeyboardInterrupt):
            print("\n[INFO] Análise por IA cancelada. Os raios-X foram preservados.")
            return []
        if model_choice != "A":
            model = selectable_models[int(model_choice) - 1].id

        review_client = lambda key, system, user: request_openrouter_review(
            key, system, user, model=model
        )

    print(f"\n[INFO] Provedor selecionado: {provider}")
    print(f"[INFO] Modelo selecionado: {model}")

    generated: list[Path] = []
    try:
        for ray_x_file in ray_x_files:
            print(f"\n[4/4] {action_progress}...")
            try:
                review_options = {"provider": provider, "model": model}
                if review_client is not None:
                    review_options["client"] = review_client
                destination = processor(ray_x_file, api_key, **review_options)
            except (NvidiaClientError, OpenRouterClientError, ReviewOutputError) as exc:
                print("[AVISO] Não foi possível concluir o processamento com IA.")
                print(f"Causa: {exc}")
                print(f"Raio-X preservado em: {ray_x_file}")
                return generated
            except OSError:
                print("[AVISO] Não foi possível gravar o arquivo produzido pela IA.")
                print(f"Raio-X preservado em: {ray_x_file}")
                return generated
            generated.append(destination)
            print(f"[OK] {action_success}.")
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
        help="Generate the deterministic X-ray without requesting an AI review",
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
    if not exported:
        return 1
    if exported and not args.skip_ai:
        run_ai_reviews(exported)
    print("\nEngine Doc Power BI finalizado.")
    if args.serve:
        serve(output_dir, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())

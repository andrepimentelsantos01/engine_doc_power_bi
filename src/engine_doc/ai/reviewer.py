"""Read the final X-ray and persist an optional AI review."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from pathlib import Path

from .nvidia_client import NVIDIA_MODEL, request_review
from .prompts import (
    DOCUMENTATION_PROMPT,
    SYSTEM_PROMPT,
    build_documentation_user_prompt,
    build_user_prompt,
)


ReviewClient = Callable[[str, str, str], str]
SEPARATOR = "=" * 72
SUBSEPARATOR = "-" * 72
REPORT_SECTIONS = (
    "VISAO GERAL",
    "PONTOS POSITIVOS",
    "PONTOS QUE MERECEM ATENCAO",
    "PERFORMANCE",
    "OBJETOS SEM USO FINAL IDENTIFICADO",
    "RELACIONAMENTOS",
    "RELATORIO",
    "DEPENDENCIAS E IMPACTO",
    "PRIORIDADES SUGERIDAS",
    "CONCLUSAO",
)
DOCUMENTATION_SECTIONS = (
    "VISAO EXECUTIVA",
    "OBJETIVO E ESCOPO",
    "ARQUITETURA DO PROJETO",
    "FONTES DE DADOS",
    "MODELO SEMANTICO",
    "MEDIDAS E INDICADORES",
    "COLUNAS CALCULADAS E DERIVACOES",
    "RELACIONAMENTOS",
    "PAGINAS DO RELATORIO",
    "COMPOSICAO VISUAL",
    "FILTROS E NAVEGACAO ANALITICA",
    "DEPENDENCIAS PRINCIPAIS",
    "LINEAGE",
    "MAPA DE IMPACTO PARA MANUTENCAO",
    "RESUMO TECNICO",
    "INFORMACOES NAO IDENTIFICADAS",
)


class ReviewOutputError(Exception):
    """The provider returned text that is not a usable technical review."""


def _normalize_for_validation(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).upper()


def _validate_analysis(model_analysis: str) -> str:
    analysis = model_analysis.strip()
    normalized = _normalize_for_validation(analysis)
    sections_found = sum(section in normalized for section in REPORT_SECTIONS)
    if (
        len(analysis) < 600
        or "<UNK>" in normalized
        or "VISAO GERAL" not in normalized
        or "CONCLUSAO" not in normalized
        or sections_found < 5
    ):
        raise ReviewOutputError(
            "O provedor retornou uma resposta incompleta ou fora do formato esperado. "
            "O arquivo de análise não foi atualizado; execute novamente."
        )
    return analysis


def _validate_documentation(model_documentation: str) -> str:
    documentation = model_documentation.strip()
    normalized = _normalize_for_validation(documentation)
    sections_found = sum(section in normalized for section in DOCUMENTATION_SECTIONS)
    required_sections = (
        "VISAO EXECUTIVA",
        "MODELO SEMANTICO",
        "MEDIDAS E INDICADORES",
        "PAGINAS DO RELATORIO",
        "RESUMO TECNICO",
        "INFORMACOES NAO IDENTIFICADAS",
    )
    if (
        len(documentation) < 800
        or "<UNK>" in normalized
        or any(section not in normalized for section in required_sections)
        or sections_found < 10
    ):
        raise ReviewOutputError(
            "O provedor retornou uma documentação incompleta ou fora do formato "
            "esperado. O arquivo de documentação não foi atualizado; execute novamente."
        )
    return documentation


def analysis_path(ray_x_file: Path) -> Path:
    return ray_x_file.with_name(f"{ray_x_file.stem}_analise_ia.txt")


def documentation_path(ray_x_file: Path) -> Path:
    project = ray_x_file.stem.removesuffix("_raio_x")
    return ray_x_file.with_name(f"{project}_documentacao_ia.txt")


def _render_analysis(
    model_analysis: str, provider: str, model: str, project: str
) -> str:
    return "\n".join(
        [
            SEPARATOR,
            "ENGINE DOC POWER BI",
            "ANÁLISE TÉCNICA POR IA",
            SEPARATOR,
            "",
            f"Projeto: {project}",
            f"Provedor: {provider}",
            f"Modelo: {model}",
            "",
            "Aviso:",
            "Esta análise foi produzida por um modelo de linguagem a partir",
            "do raio-X gerado pelo Engine Doc Power BI.",
            "",
            "As recomendações devem ser validadas tecnicamente antes de",
            "qualquer alteração no projeto.",
            "",
            SUBSEPARATOR,
            "",
            model_analysis.strip(),
            "",
            SEPARATOR,
            "",
        ]
    )


def _render_documentation(
    model_documentation: str, provider: str, model: str, project: str
) -> str:
    return "\n".join(
        [
            SEPARATOR,
            "ENGINE DOC POWER BI",
            "DOCUMENTAÇÃO EXECUTIVA E TÉCNICA POR IA",
            SEPARATOR,
            "",
            f"Projeto: {project}",
            f"Provedor: {provider}",
            f"Modelo: {model}",
            "",
            "Aviso:",
            "Esta documentação foi produzida por um modelo de linguagem a partir",
            "do raio-X gerado pelo Engine Doc Power BI.",
            "",
            SUBSEPARATOR,
            "",
            model_documentation.strip(),
            "",
            SEPARATOR,
            "",
        ]
    )


def review_ray_x(
    ray_x_file: Path,
    api_key: str,
    *,
    client: ReviewClient = request_review,
    provider: str = "NVIDIA NIM",
    model: str = NVIDIA_MODEL,
) -> Path:
    """Send only the UTF-8 X-ray text and write the review after success."""
    if not ray_x_file.is_file():
        raise FileNotFoundError(f"Arquivo de raio-X não encontrado: {ray_x_file}")
    ray_x = ray_x_file.read_text(encoding="utf-8")
    model_analysis = _validate_analysis(
        client(api_key, SYSTEM_PROMPT, build_user_prompt(ray_x))
    )
    destination = analysis_path(ray_x_file)
    project = ray_x_file.stem.removesuffix("_raio_x")
    destination.write_text(
        _render_analysis(model_analysis, provider, model, project), encoding="utf-8"
    )
    return destination


def document_ray_x(
    ray_x_file: Path,
    api_key: str,
    *,
    client: ReviewClient = request_review,
    provider: str = "NVIDIA NIM",
    model: str = NVIDIA_MODEL,
) -> Path:
    """Send only the UTF-8 X-ray text and write independent documentation."""
    if not ray_x_file.is_file():
        raise FileNotFoundError(f"Arquivo de raio-X não encontrado: {ray_x_file}")
    ray_x = ray_x_file.read_text(encoding="utf-8")
    model_documentation = _validate_documentation(
        client(
            api_key,
            DOCUMENTATION_PROMPT,
            build_documentation_user_prompt(ray_x),
        )
    )
    destination = documentation_path(ray_x_file)
    project = ray_x_file.stem.removesuffix("_raio_x")
    destination.write_text(
        _render_documentation(model_documentation, provider, model, project),
        encoding="utf-8",
    )
    return destination

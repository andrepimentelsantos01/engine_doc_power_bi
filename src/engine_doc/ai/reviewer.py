"""Read the final X-ray and persist an optional NVIDIA review."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .nvidia_client import NVIDIA_MODEL, request_review
from .prompts import SYSTEM_PROMPT, build_user_prompt


ReviewClient = Callable[[str, str, str], str]
SEPARATOR = "=" * 72
SUBSEPARATOR = "-" * 72


def analysis_path(ray_x_file: Path) -> Path:
    return ray_x_file.with_name(f"{ray_x_file.stem}_analise_ia.txt")


def _render_analysis(model_analysis: str) -> str:
    return "\n".join(
        [
            SEPARATOR,
            "ENGINE DOC POWER BI",
            "ANÁLISE TÉCNICA POR IA",
            SEPARATOR,
            "",
            f"Modelo: {NVIDIA_MODEL}",
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


def review_ray_x(
    ray_x_file: Path,
    api_key: str,
    *,
    client: ReviewClient = request_review,
) -> Path:
    """Send only the UTF-8 X-ray text and write the review after success."""
    if not ray_x_file.is_file():
        raise FileNotFoundError(f"Arquivo de raio-X não encontrado: {ray_x_file}")
    ray_x = ray_x_file.read_text(encoding="utf-8")
    model_analysis = client(api_key, SYSTEM_PROMPT, build_user_prompt(ray_x))
    destination = analysis_path(ray_x_file)
    destination.write_text(_render_analysis(model_analysis), encoding="utf-8")
    return destination

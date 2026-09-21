"""Plain-text, deterministic PBIP technical X-ray export."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..models import PBIPProject


SEPARATOR = "=" * 72
SUBSEPARATOR = "-" * 72


def safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
    return "_".join(filter(None, cleaned.split("_"))) or "projeto"


def ray_x_path(project_dir: Path, project_name: str) -> Path:
    return project_dir / f"{safe_filename(project_name)}_raio_x.txt"


def _value(value: object) -> str:
    return "não informado" if value is None or value == "" else str(value)


def render_ray_x(project: PBIPProject) -> str:
    """Render only facts produced by the deterministic extraction pipeline."""
    model = project.model
    report = project.report
    tables = model.tables if model else []
    pages = report.pages if report else []
    columns = [column for table in tables for column in table.columns]
    measures = [measure for table in tables for measure in table.measures]

    lines = [
        SEPARATOR,
        "ENGINE DOC POWER BI",
        "RAIO-X TÉCNICO DO PROJETO",
        SEPARATOR,
        "",
        f"Projeto: {project.name}",
        "Origem: extração local e determinística de artefatos PBIP",
        "",
        "RESUMO",
        SUBSEPARATOR,
        f"Tabelas: {len(tables)}",
        f"Colunas: {len(columns)}",
        f"Colunas calculadas: {sum(column.calculated for column in columns)}",
        f"Medidas: {len(measures)}",
        f"Relacionamentos: {len(model.relationships) if model else 0}",
        f"Dependências: {len(project.dependencies)}",
        f"Páginas: {len(pages)}",
        f"Visuais: {sum(page.visual_count for page in pages)}",
        "",
        "MODELO SEMÂNTICO",
        SUBSEPARATOR,
    ]

    if model:
        lines += [
            f"Nome: {model.name}",
            f"Nível de compatibilidade: {_value(model.compatibility_level)}",
            f"Cultura: {_value(model.culture)}",
        ]
        for table in tables:
            lines += [
                "",
                f"TABELA: {table.name}",
                f"Descrição: {_value(table.description)}",
                f"Oculta: {'sim' if table.hidden else 'não'}",
                f"Calculada: {'sim' if table.is_calculated else 'não'}",
            ]
            if table.expression:
                lines += ["Expressão da tabela:", table.expression]

            lines += ["", "COLUNAS"]
            if not table.columns:
                lines.append("(nenhuma coluna encontrada)")
            for column in table.columns:
                lines += [
                    f"- Nome: {column.name}",
                    f"  Tipo: {_value(column.data_type)}",
                    f"  Natureza: {'calculada' if column.calculated else 'origem'}",
                    f"  Coluna de origem: {_value(column.source_column)}",
                    f"  Formato: {_value(column.format_string)}",
                    f"  Oculta: {'sim' if column.hidden else 'não'}",
                ]
                if column.expression:
                    lines += ["  Expressão:", column.expression]

            lines += ["", "MEDIDAS"]
            if not table.measures:
                lines.append("(nenhuma medida encontrada)")
            for measure in table.measures:
                lines += [
                    f"- Nome: {measure.name}",
                    f"  Pasta de exibição: {_value(measure.display_folder)}",
                    f"  Formato: {_value(measure.format_string)}",
                    f"  Oculta: {'sim' if measure.hidden else 'não'}",
                    "  Expressão DAX:",
                    measure.expression or "(vazia)",
                ]

            lines += ["", "PARTIÇÕES E FONTES"]
            if not table.partitions:
                lines.append("(nenhuma partição encontrada)")
            for partition in table.partitions:
                lines += [
                    f"- Nome: {partition.name}",
                    f"  Modo: {_value(partition.mode)}",
                    f"  Tipo da fonte: {_value(partition.source_type)}",
                    "  Expressão da fonte:",
                    partition.expression or "(vazia)",
                ]
    else:
        lines.append("Modelo semântico não disponível.")

    lines += ["", "RELACIONAMENTOS", SUBSEPARATOR]
    if model and model.relationships:
        for relation in model.relationships:
            lines += [
                f"- {relation.name}",
                f"  Origem: {relation.from_table}[{relation.from_column}]",
                f"  Destino: {relation.to_table}[{relation.to_column}]",
                f"  Cardinalidade: {_value(relation.cardinality)}",
                f"  Direção de filtro: {_value(relation.cross_filtering_behavior)}",
                f"  Ativo: {'sim' if relation.active else 'não'}",
            ]
    else:
        lines.append("Nenhum relacionamento encontrado.")

    lines += ["", "DEPENDÊNCIAS", SUBSEPARATOR]
    if project.dependencies:
        for dependency in project.dependencies:
            lines.append(
                f"- {dependency.source} -> {dependency.target} ({dependency.kind})"
            )
    else:
        lines.append("Nenhuma dependência detectada.")

    lines += ["", "RELATÓRIO", SUBSEPARATOR]
    if pages:
        for page in pages:
            visual_types = ", ".join(
                f"{kind} ({count})"
                for kind, count in sorted(Counter(page.visual_types).items())
            )
            lines += [
                f"- Página: {page.display_name}",
                f"  Nome interno: {page.name}",
                f"  Oculta: {'sim' if page.hidden else 'não'}",
                f"  Visuais: {page.visual_count}",
                f"  Tipos de visual: {visual_types or 'não informado'}",
            ]
    else:
        lines.append("Nenhuma página de relatório encontrada.")

    lines += ["", "AVISOS DA EXTRAÇÃO", SUBSEPARATOR]
    lines.extend(f"- {warning}" for warning in project.warnings)
    if not project.warnings:
        lines.append("Nenhum aviso.")
    lines += ["", SEPARATOR, "FIM DO RAIO-X", SEPARATOR, ""]
    return "\n".join(lines)


def export_ray_x(project: PBIPProject, project_dir: Path) -> Path:
    destination = ray_x_path(project_dir, project.name)
    destination.write_text(render_ray_x(project), encoding="utf-8")
    return destination


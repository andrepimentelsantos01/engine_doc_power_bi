"""Export a self-contained technical documentation bundle."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

from ..analysis.lineage import build_mermaid
from ..models import PBIPProject, Table
from .text import export_ray_x


def _safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "-" for char in value)
    return "-".join(filter(None, cleaned.split("-"))) or "project"


def _cell(value: object) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _code(value: str | None, language: str = "dax") -> str:
    return f"```{language}\n{value or '—'}\n```"


def _table_document(table: Table) -> str:
    lines = [f"# {table.name}", ""]
    if table.description:
        lines += [table.description, ""]
    lines += [
        f"- Hidden: {'yes' if table.hidden else 'no'}",
        f"- Calculated table: {'yes' if table.is_calculated else 'no'}",
        f"- Columns: {len(table.columns)}",
        f"- Measures: {len(table.measures)}",
        "",
        "## Columns",
        "",
        "| Name | Type | Kind | Source | Hidden |",
        "|---|---|---|---|---|",
    ]
    for column in table.columns:
        kind = "calculated" if column.calculated else "source"
        lines.append(
            f"| {_cell(column.name)} | {_cell(column.data_type)} | {kind} | "
            f"{_cell(column.source_column)} | {'yes' if column.hidden else 'no'} |"
        )
    if not table.columns:
        lines.append("| — | — | — | — | — |")

    calculated = [column for column in table.columns if column.expression]
    if calculated:
        lines += ["", "### Calculated column expressions", ""]
        for column in calculated:
            lines += [f"#### {column.name}", "", _code(column.expression), ""]

    lines += ["", "## Measures", ""]
    if not table.measures:
        lines += ["No measures found.", ""]
    for measure in table.measures:
        lines += [
            f"### {measure.name}",
            "",
            f"- Display folder: {_cell(measure.display_folder)}",
            f"- Format string: {_cell(measure.format_string)}",
            f"- Hidden: {'yes' if measure.hidden else 'no'}",
            "",
            _code(measure.expression),
            "",
        ]

    lines += ["## Partitions and sources", ""]
    if not table.partitions:
        lines += ["No partitions found.", ""]
    for partition in table.partitions:
        lines += [
            f"### {partition.name}",
            "",
            f"- Mode: {_cell(partition.mode)}",
            f"- Source type: {_cell(partition.source_type)}",
            "",
            _code(partition.expression, "powerquery"),
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def _overview(project: PBIPProject) -> str:
    model = project.model
    report = project.report
    tables = model.tables if model else []
    column_count = sum(len(table.columns) for table in tables)
    measure_count = sum(len(table.measures) for table in tables)
    calculated_count = sum(
        1 for table in tables for column in table.columns if column.calculated
    )
    relationship_count = len(model.relationships) if model else 0
    pages = report.pages if report else []
    visual_count = sum(page.visual_count for page in pages)

    lines = [
        f"# {project.name} — Technical Documentation",
        "",
        "> Generated locally by Engine Doc Power BI.",
        "",
        "## Executive inventory",
        "",
        "| Tables | Columns | Calculated columns | Measures | Relationships | Pages | Visuals |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        f"| {len(tables)} | {column_count} | {calculated_count} | {measure_count} | "
        f"{relationship_count} | {len(pages)} | {visual_count} |",
        "",
        "## Source",
        "",
        f"- PBIP root: `{project.root}`",
        f"- Semantic model: `{project.semantic_model_path or 'not found'}`",
        f"- Report: `{project.report_path or 'not found'}`",
        "",
        "## Semantic model",
        "",
    ]
    if model:
        lines += [
            f"- Compatibility level: {_cell(model.compatibility_level)}",
            f"- Culture: {_cell(model.culture)}",
            "",
            "| Table | Columns | Measures | Partitions | Hidden |",
            "|---|---:|---:|---:|---|",
        ]
        for table in tables:
            slug = _safe_name(table.name)
            lines.append(
                f"| [{_cell(table.name)}](tables/{slug}.md) | {len(table.columns)} | "
                f"{len(table.measures)} | {len(table.partitions)} | "
                f"{'yes' if table.hidden else 'no'} |"
            )
    else:
        lines.append("Semantic model not available.")

    lines += ["", "## Relationships", ""]
    if model and model.relationships:
        lines += [
            "| From | To | Cardinality | Filtering | Active |",
            "|---|---|---|---|---|",
        ]
        for relation in model.relationships:
            lines.append(
                f"| {_cell(relation.from_table)}[{_cell(relation.from_column)}] | "
                f"{_cell(relation.to_table)}[{_cell(relation.to_column)}] | "
                f"{_cell(relation.cardinality)} | {_cell(relation.cross_filtering_behavior)} | "
                f"{'yes' if relation.active else 'no'} |"
            )
    else:
        lines.append("No relationships found.")

    lines += ["", "## Report pages", ""]
    if pages:
        lines += ["| Page | Internal name | Visuals | Types | Hidden |", "|---|---|---:|---|---|"]
        for page in pages:
            types = ", ".join(
                f"{name} ({count})" for name, count in sorted(Counter(page.visual_types).items())
            )
            lines.append(
                f"| {_cell(page.display_name)} | {_cell(page.name)} | {page.visual_count} | "
                f"{_cell(types)} | {'yes' if page.hidden else 'no'} |"
            )
    else:
        lines.append("No report pages found.")

    lines += [
        "",
        "## Dependencies and lineage",
        "",
        f"Detected dependencies: **{len(project.dependencies)}**.",
        "",
        "- [Dependency inventory](dependencies.md)",
        "- [Mermaid lineage source](lineage.mmd)",
        "- [Machine-readable metadata](metadata.json)",
    ]
    if project.warnings:
        lines += ["", "## Warnings", ""] + [f"- {warning}" for warning in project.warnings]
    return "\n".join(lines).rstrip() + "\n"


def _dependencies(project: PBIPProject) -> str:
    lines = [
        f"# {project.name} — Dependencies",
        "",
        "| Source | Target | Kind |",
        "|---|---|---|",
    ]
    for item in project.dependencies:
        lines.append(f"| `{_cell(item.source)}` | `{_cell(item.target)}` | {_cell(item.kind)} |")
    if not project.dependencies:
        lines.append("| — | — | — |")
    lines += ["", "## Lineage", "", "```mermaid", build_mermaid(project).rstrip(), "```", ""]
    return "\n".join(lines)


def export_project(
    project: PBIPProject,
    output_root: Path,
    relative_output: Path | None = None,
) -> Path:
    """Export one project, optionally mirroring its folder below ``output_root``."""
    target = output_root / (relative_output or Path(_safe_name(project.name)))
    if target.exists():
        shutil.rmtree(target)
    tables_dir = target / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    overview = _overview(project)
    (target / "README.md").write_text(overview, encoding="utf-8")
    (target / "dependencies.md").write_text(_dependencies(project), encoding="utf-8")
    (target / "lineage.mmd").write_text(build_mermaid(project), encoding="utf-8")
    (target / "metadata.json").write_text(
        json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    export_ray_x(project, target)
    if project.model:
        for table in project.model.tables:
            (tables_dir / f"{_safe_name(table.name)}.md").write_text(
                _table_document(table), encoding="utf-8"
            )
    return target

"""Plain-text, deterministic PBIP technical X-ray export."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..analysis.report_usage import collect_report_usage, downstream_dependencies, object_id
from ..models import PBIPProject, ReportFilter, VisualField


SEPARATOR = "=" * 72
SUBSEPARATOR = "-" * 72


def safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
    return "_".join(filter(None, cleaned.split("_"))) or "projeto"


def ray_x_path(project_dir: Path, project_name: str) -> Path:
    return project_dir / f"{safe_filename(project_name)}_raio_x.txt"


def _value(value: object) -> str:
    return "não informado" if value is None or value == "" else str(value)


def _field_label(field: VisualField) -> str:
    table = field.table or "?"
    label = f"{table}[{field.name}]"
    details = [f"tipo={field.kind}"]
    if field.role:
        details.append(f"papel={field.role}")
    if field.aggregation:
        details.append(f"agregação={field.aggregation}")
    details.append(f"resolução={field.resolution}")
    return f"{label} ({', '.join(details)})"


def _filter_lines(filters: list[ReportFilter], indent: str = "") -> list[str]:
    lines: list[str] = []
    if not filters:
        return [f"{indent}(nenhum filtro explícito encontrado)"]
    for report_filter in filters:
        lines.append(
            f"{indent}- {report_filter.display_name or report_filter.name} "
            f"(tipo={_value(report_filter.filter_type)}, escopo={report_filter.scope})"
        )
        if report_filter.fields:
            lines.extend(
                f"{indent}  Campo: {_field_label(field)}"
                for field in report_filter.fields
            )
        else:
            lines.append(f"{indent}  Dependência não determinada")
    return lines


def _usage_location(reference) -> str:
    if reference.visual_name:
        visual = reference.visual_title or reference.visual_name
        role = f"; papel={reference.role}" if reference.role else ""
        return f"{reference.page_display_name} > {visual} ({reference.scope}{role})"
    return f"{reference.page_display_name} ({reference.scope})"


def _node_label(node: str) -> str:
    prefixes = {
        "measure:": "Medida: ",
        "column:": "Coluna: ",
        "visual:": "Visual: ",
        "page:": "Página: ",
        "report:": "Relatório: ",
        "hierarchy:": "Hierarquia: ",
        "table:": "Tabela: ",
        "source:": "Fonte/partição: ",
    }
    for prefix, label in prefixes.items():
        if node.startswith(prefix):
            return label + node[len(prefix):]
    return node


def _expression_dependencies(project: PBIPProject, source: str) -> list[str]:
    allowed = {"measure_reference", "column_reference"}
    return sorted(
        {
            dependency.target
            for dependency in project.dependencies
            if dependency.source == source and dependency.kind in allowed
        }
    )


def render_ray_x(project: PBIPProject) -> str:
    """Render only facts produced by the deterministic extraction pipeline."""
    model = project.model
    report = project.report
    tables = model.tables if model else []
    pages = report.pages if report else []
    columns = [column for table in tables for column in table.columns]
    measures = [measure for table in tables for measure in table.measures]
    usage = collect_report_usage(project)
    used_measure_ids = {key for key in usage if key.startswith("measure:")}
    used_column_ids = {key for key in usage if key.startswith("column:")}
    visual_types = Counter(
        visual.visual_type for page in pages for visual in page.visuals
    )
    all_measure_ids = {
        f"measure:{table.name}[{measure.name}]"
        for table in tables
        for measure in table.measures
    }
    all_column_ids = {
        f"column:{table.name}[{column.name}]"
        for table in tables
        for column in table.columns
    }

    lines = [
        SEPARATOR,
        "ENGINE DOC POWER BI",
        "RAIO-X DO PROJETO",
        SEPARATOR,
        "",
        f"Projeto: {project.name}",
        "Formato: PBIP",
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
        "Visuais por tipo: "
        + (
            ", ".join(f"{kind} ({count})" for kind, count in sorted(visual_types.items()))
            or "não informado"
        ),
        f"Medidas utilizadas diretamente em visuais/filtros: {len(used_measure_ids)}",
        f"Colunas utilizadas diretamente em visuais/filtros: {len(used_column_ids)}",
        "Medidas sem uso direto identificado na camada de relatório: "
        f"{len(all_measure_ids - used_measure_ids)}",
        "Colunas sem uso direto identificado na camada de relatório: "
        f"{len(all_column_ids - used_column_ids)}",
        "Observação: ausência de uso direto em visual não significa que o objeto seja inútil; "
        "ele pode participar de cálculos, relacionamentos ou outras estruturas.",
        "",
        "FONTES",
        SUBSEPARATOR,
    ]

    partitions = [partition for table in tables for partition in table.partitions]
    if partitions:
        for partition in partitions:
            lines += [
                f"FONTE: {partition.table}/{partition.name}",
                f"  Modo: {_value(partition.mode)}",
                f"  Tipo: {_value(partition.source_type)}",
            ]
    else:
        lines.append("Nenhuma fonte ou partição encontrada.")

    lines += ["", "MODELO SEMÂNTICO", SUBSEPARATOR]

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
                column_key = f"column:{table.name}[{column.name}]"
                lines += [
                    "",
                    f"COLUNA: {table.name}[{column.name}]",
                    f"  Tipo: {_value(column.data_type)}",
                    f"  Natureza: {'calculada' if column.calculated else 'origem'}",
                    f"  Coluna de origem: {_value(column.source_column)}",
                    f"  Formato: {_value(column.format_string)}",
                    f"  Oculta: {'sim' if column.hidden else 'não'}",
                ]
                references = usage.get(column_key, [])
                if references:
                    lines.append("  Utilizada diretamente em:")
                    lines.extend(f"  - {_usage_location(ref)}" for ref in references)
                else:
                    lines.append("  Uso direto em visual/filtro: não identificado")
                dependent_measures = [
                    node
                    for node in downstream_dependencies(project, column_key)
                    if node.startswith("measure:")
                ]
                if dependent_measures:
                    lines.append("  USADA POR / DEPENDÊNCIAS A JUSANTE:")
                    lines.extend(f"  - {_node_label(node)}" for node in dependent_measures)
                if column.expression:
                    lines += ["  Expressão:", column.expression]
                    dependencies = _expression_dependencies(project, column_key)
                    lines.append("  DEPENDE DE:")
                    lines.extend(
                        (f"  - {_node_label(node)}" for node in dependencies),
                    )
                    if not dependencies:
                        lines.append("  - Dependência não determinada")

            lines += ["", "MEDIDAS"]
            if not table.measures:
                lines.append("(nenhuma medida encontrada)")
            for measure in table.measures:
                measure_key = f"measure:{table.name}[{measure.name}]"
                lines += [
                    "",
                    f"MEDIDA: {table.name}[{measure.name}]",
                    f"  Pasta de exibição: {_value(measure.display_folder)}",
                    f"  Formato: {_value(measure.format_string)}",
                    f"  Oculta: {'sim' if measure.hidden else 'não'}",
                    "  Expressão DAX:",
                    measure.expression or "(vazia)",
                    "  DEPENDE DE:",
                ]
                dependencies = _expression_dependencies(project, measure_key)
                lines.extend(f"  - {_node_label(node)}" for node in dependencies)
                if not dependencies:
                    lines.append("  - Dependência não determinada")
                references = usage.get(measure_key, [])
                if references:
                    lines.append("  Utilizada diretamente em:")
                    lines.extend(f"  - {_usage_location(ref)}" for ref in references)
                else:
                    lines.append("  Uso direto em visual/filtro: não identificado")
                dependent_measures = [
                    node
                    for node in downstream_dependencies(project, measure_key)
                    if node.startswith("measure:")
                ]
                if dependent_measures:
                    lines.append("  USADA POR / DEPENDÊNCIAS A JUSANTE:")
                    lines.extend(f"  - {_node_label(node)}" for node in dependent_measures)

            lines += ["", "PARTIÇÕES E FONTES"]
            if not table.partitions:
                lines.append("(nenhuma partição encontrada)")
            for partition in table.partitions:
                lines += [
                    f"FONTE: {table.name}/{partition.name}",
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
                f"RELACIONAMENTO: {relation.name}",
                f"  Origem: {relation.from_table}[{relation.from_column}]",
                f"  Destino: {relation.to_table}[{relation.to_column}]",
                f"  Cardinalidade: {_value(relation.cardinality)}",
                f"  Direção de filtro: {_value(relation.cross_filtering_behavior)}",
                f"  Ativo: {'sim' if relation.active else 'não'}",
            ]
    else:
        lines.append("Nenhum relacionamento encontrado.")

    lines += [
        "",
        "DEPENDÊNCIAS",
        SUBSEPARATOR,
        "Formato: objeto dependente -> dependência comprovada",
    ]
    if project.dependencies:
        for dependency in project.dependencies:
            lines.append(
                f"- {dependency.source} -> {dependency.target} ({dependency.kind})"
            )
    else:
        lines.append("Nenhuma dependência detectada.")

    lines += [
        "",
        "LINEAGE",
        SUBSEPARATOR,
        "Formato: dependência comprovada -> objeto dependente",
    ]
    if project.dependencies:
        for dependency in project.dependencies:
            lines.append(
                f"- {_node_label(dependency.target)} -> "
                f"{_node_label(dependency.source)} ({dependency.kind})"
            )
    else:
        lines.append("Nenhuma conexão de lineage pôde ser comprovada.")

    lines += ["", "PÁGINAS", SUBSEPARATOR]
    if pages:
        for page in pages:
            visual_types = ", ".join(
                f"{kind} ({count})"
                for kind, count in sorted(Counter(page.visual_types).items())
            )
            lines += [
                f"PÁGINA: {page.display_name}",
                f"  Nome interno: {page.name}",
                f"  Oculta: {'sim' if page.hidden else 'não'}",
                f"  Visuais: {page.visual_count}",
                f"  Tipos de visual: {visual_types or 'não informado'}",
            ]
    else:
        lines.append("Nenhuma página de relatório encontrada.")

    lines += ["", "PÁGINAS E VISUAIS", SUBSEPARATOR]
    if pages:
        lines += [
            f"Tema do relatório: {_value(report.theme if report else None)}",
            "Filtros do relatório:",
        ]
        lines.extend(_filter_lines(report.filters if report else [], "  "))
        for page in pages:
            lines += [
                "",
                f"PÁGINA: {page.display_name}",
                f"Nome técnico: {page.name}",
                f"Ordem: {_value(page.order)}",
                f"Oculta: {'sim' if page.hidden else 'não'}",
                f"Quantidade de visuais: {page.visual_count}",
                "Filtros da página:",
            ]
            lines.extend(_filter_lines(page.filters, "  "))
            for visual in page.visuals:
                tables_used = sorted(
                    {
                        field.table
                        for field in (
                            visual.fields
                            + [
                                filter_field
                                for report_filter in visual.filters
                                for filter_field in report_filter.fields
                            ]
                        )
                        if field.table
                    }
                )
                position = ", ".join(
                    f"{key}={value:g}" for key, value in visual.position.items()
                )
                lines += [
                    "",
                    f"  VISUAL: {visual.title or visual.name}",
                    f"  ID técnico: {visual.name}",
                    f"  Tipo: {visual.visual_type}",
                    f"  Título: {_value(visual.title)}",
                    f"  Oculto: {'sim' if visual.hidden else 'não'}",
                    f"  Posição: {position or 'não informada'}",
                    f"  Tabelas relacionadas: {', '.join(tables_used) or 'não determinadas'}",
                    "  Campos utilizados:",
                ]
                if visual.fields:
                    lines.extend(f"  - {_field_label(field)}" for field in visual.fields)
                else:
                    lines.append("  - Dependência não determinada")
                lines.append("  Filtros do visual:")
                lines.extend(_filter_lines(visual.filters, "    "))
                lines.append("  Dependências comprovadas:")
                if visual.fields:
                    for field in visual.fields:
                        target = object_id(field)
                        lines.append(f"  - {_node_label(target)}")
                        direct_dependencies = [
                            dependency.target
                            for dependency in project.dependencies
                            if dependency.source == target
                            and dependency.kind
                            in {
                                "measure_reference",
                                "column_reference",
                                "measure_member_of",
                                "column_member_of",
                            }
                        ]
                        lines.extend(
                            f"    - {_node_label(dependency)}"
                            for dependency in direct_dependencies
                        )
                else:
                    lines.append("  - Dependência não determinada")
    else:
        lines.append("Nenhum detalhe visual disponível.")

    lines += ["", "ANÁLISE DE IMPACTO", SUBSEPARATOR]
    impact_found = False
    for semantic_object in sorted(all_measure_ids | all_column_ids):
        downstream = downstream_dependencies(project, semantic_object)
        report_impact = [
            node
            for node in downstream
            if node.startswith(("measure:", "visual:", "page:"))
        ]
        if not report_impact:
            continue
        impact_found = True
        lines += ["", f"OBJETO: {_node_label(semantic_object)}", "DEPENDÊNCIAS A JUSANTE:"]
        lines.extend(f"- {_node_label(node)}" for node in report_impact)
    if not impact_found:
        lines.append("Nenhuma dependência a jusante pôde ser comprovada.")

    lines += ["", "AVISOS", SUBSEPARATOR]
    lines.extend(f"- {warning}" for warning in project.warnings)
    if not project.warnings:
        lines.append("Nenhum aviso.")
    lines += ["", SEPARATOR, "FIM DO RAIO-X", SEPARATOR, ""]
    return "\n".join(lines)


def export_ray_x(project: PBIPProject, project_dir: Path) -> Path:
    destination = ray_x_path(project_dir, project.name)
    destination.write_text(render_ray_x(project), encoding="utf-8")
    return destination

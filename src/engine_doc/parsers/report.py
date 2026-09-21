"""Defensive report parser for PBIR and legacy report.json artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..models import Report, ReportFilter, ReportPage, ReportVisual, VisualField


AGGREGATIONS = {
    0: "sum",
    1: "average",
    2: "count",
    3: "min",
    4: "max",
    5: "count_non_null",
    6: "median",
    7: "standard_deviation",
    8: "variance",
}


def _json(
    path: Path,
    warnings: list[str] | None = None,
    *,
    label: str | None = None,
) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError:
        if warnings is not None:
            warnings.append(f"{label or path.name} não pôde ser lido.")
        return {}
    except UnicodeDecodeError:
        if warnings is not None:
            warnings.append(f"{label or path.name} possui codificação não suportada.")
        return {}
    except json.JSONDecodeError:
        if warnings is not None:
            warnings.append(f"{label or path.name} contém JSON inválido.")
        return {}


def _decode(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _visual_config(raw: dict) -> dict:
    visual = raw.get("visual")
    if isinstance(visual, dict):
        return visual
    single = raw.get("singleVisual")
    if isinstance(single, dict):
        return single
    return raw


def _visual_type(raw: dict) -> str:
    visual = _visual_config(raw)
    return str(visual.get("visualType") or raw.get("visualType") or "unknown")


def _source_entity(node: Any) -> str | None:
    if isinstance(node, dict):
        source = node.get("SourceRef")
        if isinstance(source, dict) and source.get("Entity"):
            return str(source["Entity"])
        for value in node.values():
            found = _source_entity(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _source_entity(value)
            if found:
                return found
    return None


def _query_ref_field(query_ref: str | None, role: str | None) -> VisualField | None:
    if not query_ref:
        return None
    cleaned = query_ref.strip()
    function = re.match(r"^[A-Za-z]+\((.*)\)$", cleaned)
    if function:
        cleaned = function.group(1)
    if "." in cleaned:
        table, name = cleaned.rsplit(".", 1)
        return VisualField(
            table=table.strip("' "),
            name=name.strip("' []"),
            kind="unknown",
            role=role,
            query_ref=query_ref,
            resolution="reference",
        )
    return VisualField(
        table=None,
        name=cleaned.strip("[]"),
        kind="unknown",
        role=role,
        query_ref=query_ref,
        resolution="undetermined",
    )


def _field_expression(node: Any, role: str | None = None) -> VisualField | None:
    if not isinstance(node, dict):
        return None

    aggregation = node.get("Aggregation")
    if isinstance(aggregation, dict):
        inner = _field_expression(aggregation.get("Expression"), role)
        function = aggregation.get("Function")
        name = AGGREGATIONS.get(function, str(function) if function is not None else None)
        return replace(inner, aggregation=name) if inner else None

    for key, kind in (("Measure", "measure"), ("Column", "column")):
        payload = node.get(key)
        if isinstance(payload, dict):
            name = payload.get("Property") or payload.get("Name")
            if name:
                return VisualField(
                    table=_source_entity(payload),
                    name=str(name),
                    kind=kind,
                    role=role,
                    resolution="explicit",
                )

    level = node.get("HierarchyLevel")
    if isinstance(level, dict):
        name = level.get("Level") or level.get("Property") or level.get("Name")
        if name:
            return VisualField(
                table=_source_entity(level),
                name=str(name),
                kind="hierarchy",
                role=role,
                resolution="explicit",
            )

    hierarchy = node.get("Hierarchy")
    if isinstance(hierarchy, dict):
        name = hierarchy.get("Hierarchy") or hierarchy.get("Property") or hierarchy.get("Name")
        if name:
            return VisualField(
                table=_source_entity(hierarchy),
                name=str(name),
                kind="hierarchy",
                role=role,
                resolution="explicit",
            )

    calculation = node.get("NativeVisualCalculation") or node.get("VisualCalculation")
    if isinstance(calculation, dict):
        name = calculation.get("Name") or calculation.get("Property")
        if name:
            return VisualField(
                table=None,
                name=str(name),
                kind="visual_calculation",
                role=role,
                resolution="explicit",
            )
    return None


def _projection_field(projection: Any, role: str | None) -> VisualField | None:
    if not isinstance(projection, dict):
        return None
    query_ref = projection.get("queryRef") or projection.get("nativeQueryRef")
    field = _field_expression(projection.get("field"), role)
    if not field:
        field = _query_ref_field(str(query_ref) if query_ref else None, role)
    if not field:
        return None
    return replace(
        field,
        query_ref=str(query_ref) if query_ref else None,
        display_name=projection.get("displayName"),
        active=projection.get("active", True),
    )


def _scan_fields(node: Any, role: str | None = None) -> list[VisualField]:
    """Fallback for legacy/changed schemas; only accepts semantic wrappers."""
    fields: list[VisualField] = []
    if isinstance(node, list):
        for item in node:
            fields.extend(_scan_fields(item, role))
        return fields
    if not isinstance(node, dict):
        return fields
    direct = _field_expression(node, role)
    if direct:
        return [direct]
    if "field" in node:
        projection = _projection_field(node, role)
        if projection:
            fields.append(projection)
    for key, value in node.items():
        if key != "field":
            fields.extend(_scan_fields(value, role))
    return fields


def _dedupe_fields(fields: list[VisualField]) -> list[VisualField]:
    unique: list[VisualField] = []
    seen: set[tuple] = set()
    for item in fields:
        key = (
            (item.table or "").casefold(),
            item.name.casefold(),
            item.kind,
            item.role or "",
            item.aggregation or "",
            item.query_ref or "",
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _visual_fields(raw: dict) -> list[VisualField]:
    visual = _visual_config(raw)
    query = visual.get("query", {}) if isinstance(visual.get("query"), dict) else {}
    query_state = query.get("queryState") or visual.get("queryState") or {}
    fields: list[VisualField] = []
    if isinstance(query_state, dict):
        for role, state in query_state.items():
            if not isinstance(state, dict):
                continue
            projections = state.get("projections", [])
            for projection in projections if isinstance(projections, list) else []:
                field = _projection_field(projection, str(role))
                if field:
                    fields.append(field)

    sort_definition = query.get("sortDefinition", {})
    if isinstance(sort_definition, dict):
        for sort in sort_definition.get("sort", []):
            if isinstance(sort, dict):
                field = _field_expression(sort.get("field"), "Ordenação")
                if field:
                    fields.append(field)

    if not fields:
        legacy_query = visual.get("prototypeQuery") or query or visual.get("queryState")
        fields.extend(_scan_fields(legacy_query))
    return _dedupe_fields(fields)


def _literal_text(node: Any) -> str | None:
    if isinstance(node, dict):
        literal = node.get("Literal")
        if isinstance(literal, dict) and isinstance(literal.get("Value"), str):
            value = literal["Value"].strip()
            if len(value) >= 2 and value[0] == value[-1] == "'":
                value = value[1:-1].replace("''", "'")
            return value
        for value in node.values():
            found = _literal_text(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _literal_text(value)
            if found:
                return found
    return None


def _visual_title(raw: dict) -> str | None:
    visual = _visual_config(raw)
    direct = visual.get("title") or raw.get("title")
    if isinstance(direct, str):
        return direct
    objects = visual.get("visualContainerObjects") or visual.get("vcObjects") or {}
    if isinstance(objects, dict) and "title" in objects:
        return _literal_text(objects["title"])
    return None


def _filters(raw: Any, scope: str) -> list[ReportFilter]:
    raw = _decode(raw)
    if isinstance(raw, dict):
        raw = raw.get("filters", [])
    if not isinstance(raw, list):
        return []
    filters: list[ReportFilter] = []
    for index, item in enumerate(raw, start=1):
        item = _decode(item)
        if not isinstance(item, dict):
            continue
        fields = _scan_fields(item.get("field"))
        if not fields:
            fields = _scan_fields(item.get("expression") or item.get("condition"))
        filters.append(
            ReportFilter(
                name=str(item.get("name") or f"Filtro {index}"),
                scope=scope,
                filter_type=item.get("type"),
                display_name=item.get("displayName"),
                fields=_dedupe_fields(fields),
            )
        )
    return filters


def _parse_visual(raw: dict, fallback_name: str) -> ReportVisual:
    position = raw.get("position", {})
    numeric_position = (
        {
            key: float(value)
            for key, value in position.items()
            if key in {"x", "y", "z", "height", "width", "tabOrder"}
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        }
        if isinstance(position, dict)
        else {}
    )
    return ReportVisual(
        name=str(raw.get("name") or fallback_name),
        visual_type=_visual_type(raw),
        title=_visual_title(raw),
        fields=_visual_fields(raw),
        filters=_filters(raw.get("filterConfig") or raw.get("filters"), "visual"),
        hidden=bool(raw.get("isHidden", False)),
        position=numeric_position,
    )


def _parse_pbir(path: Path, name: str, warnings: list[str]) -> Report:
    definition = path / "definition"
    raw_report = _json(
        definition / "report.json", warnings, label="Definição do relatório"
    )
    themes = raw_report.get("themeCollection", {})
    custom_theme = themes.get("customTheme", {}) if isinstance(themes, dict) else {}
    base_theme = themes.get("baseTheme", {}) if isinstance(themes, dict) else {}
    theme = (
        custom_theme.get("name") if isinstance(custom_theme, dict) else None
    ) or (base_theme.get("name") if isinstance(base_theme, dict) else None)
    report = Report(
        name=name,
        theme=theme,
        filters=_filters(raw_report.get("filterConfig") or raw_report.get("filters"), "report"),
    )
    pages_root = definition / "pages"
    pages_index = _json(
        pages_root / "pages.json", warnings, label="Índice de páginas"
    )
    page_order = pages_index.get("pageOrder", [])
    page_paths = [
        pages_root / page_name
        for page_name in page_order
        if isinstance(page_name, str)
    ] if isinstance(page_order, list) else []
    if not page_paths:
        page_paths = sorted(p.parent for p in pages_root.rglob("page.json"))

    for order, page_path in enumerate(page_paths, start=1):
        raw_page = _json(
            page_path / "page.json",
            warnings,
            label=f"Página {page_path.name}",
        )
        if not raw_page:
            continue
        visuals: list[ReportVisual] = []
        visuals_root = page_path / "visuals"
        if visuals_root.exists():
            for visual_file in sorted(visuals_root.rglob("visual.json")):
                raw_visual = _json(
                    visual_file,
                    warnings,
                    label=f"Visual {visual_file.parent.name}",
                )
                if raw_visual:
                    try:
                        visuals.append(_parse_visual(raw_visual, visual_file.parent.name))
                    except (KeyError, TypeError, ValueError, AttributeError):
                        warnings.append(
                            f"Visual {visual_file.parent.name} possui uma estrutura não reconhecida."
                        )
        report.pages.append(
            ReportPage(
                name=raw_page.get("name", page_path.name),
                display_name=raw_page.get("displayName", raw_page.get("name", page_path.name)),
                visual_count=len(visuals),
                visual_types=[visual.visual_type for visual in visuals],
                hidden=raw_page.get("visibility") == "HiddenInViewMode",
                order=order,
                filters=_filters(raw_page.get("filterConfig") or raw_page.get("filters"), "page"),
                visuals=visuals,
            )
        )
    return report


def _parse_legacy(path: Path, name: str, warnings: list[str]) -> Report:
    raw = _json(path, warnings, label="Relatório legado")
    report = Report(
        name=name,
        filters=_filters(raw.get("filterConfig") or raw.get("filters"), "report"),
    )
    sections = raw.get("sections", [])
    if not isinstance(sections, list):
        warnings.append("O relatório legado possui uma lista de páginas não reconhecida.")
        sections = []
    for order, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            warnings.append(f"Página legada {order} possui uma estrutura não reconhecida.")
            continue
        visuals: list[ReportVisual] = []
        containers = section.get("visualContainers", [])
        if not isinstance(containers, list):
            warnings.append(
                f"Página {section.get('name', order)} possui visuais em formato não reconhecido."
            )
            containers = []
        for index, container in enumerate(containers, start=1):
            if not isinstance(container, dict):
                warnings.append(
                    f"Visual {index} da página {section.get('name', order)} não pôde ser interpretado."
                )
                continue
            config = _decode(container.get("config", {}))
            if not isinstance(config, dict):
                config = {}
            merged = {**config}
            merged.setdefault("name", container.get("name") or container.get("id"))
            merged.setdefault(
                "position",
                {
                    key: container[key]
                    for key in ("x", "y", "z", "height", "width")
                    if key in container
                },
            )
            if container.get("filters"):
                merged["filters"] = container["filters"]
            if container.get("query"):
                merged["query"] = _decode(container["query"])
            visuals.append(_parse_visual(merged, f"Visual {index}"))
        report.pages.append(
            ReportPage(
                name=section.get("name", "Unnamed page"),
                display_name=section.get("displayName", section.get("name", "Unnamed page")),
                visual_count=len(visuals),
                visual_types=[visual.visual_type for visual in visuals],
                hidden=section.get("visibility") == 1,
                order=order,
                filters=_filters(section.get("filters"), "page"),
                visuals=visuals,
            )
        )
    return report


def parse_report(
    path: Path,
    name: str | None = None,
    *,
    warnings: list[str] | None = None,
) -> Report:
    name = name or path.name.removesuffix(".Report")
    collected_warnings = warnings if warnings is not None else []
    if (path / "definition" / "pages").exists():
        return _parse_pbir(path, name, collected_warnings)
    candidates = [path / "report.json", path / "definition" / "report.json"]
    candidates.extend(path.rglob("report.json"))
    for candidate in candidates:
        if candidate.exists():
            return _parse_legacy(candidate, name, collected_warnings)
    raise FileNotFoundError(f"No PBIR definition or report.json found in {path}")

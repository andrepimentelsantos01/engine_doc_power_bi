"""Resolve report references and connect pages/visuals to semantic objects."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from ..models import Dependency, PBIPProject, ReportFilter, VisualField


def page_id(page_name: str) -> str:
    return f"page:{page_name}"


def report_id(report_name: str) -> str:
    return f"report:{report_name}"


def visual_id(page_name: str, visual_name: str) -> str:
    return f"visual:{page_name}/{visual_name}"


def object_id(field: VisualField) -> str:
    table = field.table or "?"
    if field.resolution == "undetermined":
        return f"unresolved:{table}[{field.name}]"
    return f"{field.kind}:{table}[{field.name}]"


def _all_report_fields(project: PBIPProject):
    if not project.report:
        return
    for report_filter in project.report.filters:
        yield from report_filter.fields
    for page in project.report.pages:
        for report_filter in page.filters:
            yield from report_filter.fields
        for visual in page.visuals:
            yield from visual.fields
            for report_filter in visual.filters:
                yield from report_filter.fields


def resolve_report_references(project: PBIPProject) -> None:
    """Validate parsed references against the model, without inventing matches."""
    if not project.model or not project.report:
        return
    columns = {
        (table.name.casefold(), column.name.casefold()): (table.name, column.name)
        for table in project.model.tables
        for column in table.columns
    }
    measures = {
        (table.name.casefold(), measure.name.casefold()): (table.name, measure.name)
        for table in project.model.tables
        for measure in table.measures
    }
    columns_by_name: dict[str, list[tuple[str, str]]] = defaultdict(list)
    measures_by_name: dict[str, list[tuple[str, str]]] = defaultdict(list)
    table_names = {table.name.casefold(): table.name for table in project.model.tables}
    for value in columns.values():
        columns_by_name[value[1].casefold()].append(value)
    for value in measures.values():
        measures_by_name[value[1].casefold()].append(value)

    for field in _all_report_fields(project):
        table_key = field.table.casefold() if field.table else None
        name_key = field.name.casefold()
        exact_key = (table_key, name_key) if table_key else None
        match: tuple[str, str] | None = None
        resolved_kind = field.kind
        if field.kind == "measure" and exact_key in measures:
            match = measures[exact_key]
        elif field.kind == "column" and exact_key in columns:
            match = columns[exact_key]
        elif field.kind == "unknown" and exact_key:
            if exact_key in measures:
                match, resolved_kind = measures[exact_key], "measure"
            elif exact_key in columns:
                match, resolved_kind = columns[exact_key], "column"
        elif field.kind == "unknown":
            candidates = measures_by_name.get(name_key, []) + columns_by_name.get(name_key, [])
            if len(candidates) == 1:
                match = candidates[0]
                resolved_kind = "measure" if candidates[0] in measures.values() else "column"
        elif field.kind == "hierarchy" and table_key in table_names:
            field.table = table_names[table_key]
            field.resolution = "reference"
            continue
        elif field.kind == "visual_calculation":
            continue

        if match:
            field.table, field.name = match
            field.kind = resolved_kind
            if field.resolution != "explicit":
                field.resolution = "reference"
        else:
            field.resolution = "undetermined"


def _filter_dependencies(
    source: str, report_filter: ReportFilter, prefix: str
) -> set[tuple[str, str, str]]:
    dependencies: set[tuple[str, str, str]] = set()
    for field in report_filter.fields:
        status = field.resolution
        dependencies.add((source, object_id(field), f"{prefix}_{status}"))
    return dependencies


def analyze_report_dependencies(project: PBIPProject) -> list[Dependency]:
    """Create explicit page → visual → semantic-object dependency edges."""
    if not project.report:
        return []
    resolve_report_references(project)
    dependencies: set[tuple[str, str, str]] = set()
    report_node = report_id(project.report.name)
    for report_filter in project.report.filters:
        dependencies.update(_filter_dependencies(report_node, report_filter, "report_filter"))
    for page in project.report.pages:
        page_node = page_id(page.name)
        for report_filter in page.filters:
            dependencies.update(_filter_dependencies(page_node, report_filter, "page_filter"))
        for visual in page.visuals:
            visual_node = visual_id(page.name, visual.name)
            dependencies.add((page_node, visual_node, "page_contains_visual"))
            for field in visual.fields:
                dependencies.add(
                    (
                        visual_node,
                        object_id(field),
                        f"visual_{field.kind}_{field.resolution}",
                    )
                )
            for report_filter in visual.filters:
                dependencies.update(
                    _filter_dependencies(visual_node, report_filter, "visual_filter")
                )
    return [Dependency(*item) for item in sorted(dependencies)]


@dataclass(frozen=True, slots=True)
class UsageReference:
    page_name: str
    page_display_name: str
    visual_name: str | None
    visual_title: str | None
    role: str | None
    scope: str


def collect_report_usage(project: PBIPProject) -> dict[str, list[UsageReference]]:
    usage: dict[str, list[UsageReference]] = defaultdict(list)
    if not project.report:
        return {}
    for report_filter in project.report.filters:
        for field in report_filter.fields:
            if field.resolution != "undetermined":
                usage[object_id(field)].append(
                    UsageReference("*", "Todo o relatório", None, None, None, "report_filter")
                )
    for page in project.report.pages:
        for report_filter in page.filters:
            for field in report_filter.fields:
                if field.resolution != "undetermined":
                    usage[object_id(field)].append(
                        UsageReference(
                            page.name,
                            page.display_name,
                            None,
                            None,
                            None,
                            "page_filter",
                        )
                    )
        for visual in page.visuals:
            for field in visual.fields:
                if field.resolution != "undetermined":
                    usage[object_id(field)].append(
                        UsageReference(
                            page.name,
                            page.display_name,
                            visual.name,
                            visual.title,
                            field.role,
                            "visual",
                        )
                    )
            for report_filter in visual.filters:
                for field in report_filter.fields:
                    if field.resolution != "undetermined":
                        usage[object_id(field)].append(
                            UsageReference(
                                page.name,
                                page.display_name,
                                visual.name,
                                visual.title,
                                None,
                                "visual_filter",
                            )
                        )
    return dict(usage)


def downstream_dependencies(project: PBIPProject, start: str) -> list[str]:
    """Return proven downstream model/report consumers of an object."""
    reverse: dict[str, set[str]] = defaultdict(set)
    for dependency in project.dependencies:
        if dependency.kind == "relationship" or "undetermined" in dependency.kind:
            continue
        reverse[dependency.target].add(dependency.source)
    found: list[str] = []
    visited = {start}
    queue = deque(sorted(reverse.get(start, ())))
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        found.append(current)
        queue.extend(sorted(reverse.get(current, ())))
    return found

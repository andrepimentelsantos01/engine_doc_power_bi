"""Extract best-effort object dependencies from DAX expressions."""

from __future__ import annotations

import re

from ..models import Dependency, SemanticModel


_QUALIFIED = re.compile(r"(?:'((?:''|[^'])+)'|([A-Za-z_][\w ]*))\s*\[([^\]]+)\]")
_BRACKETED = re.compile(r"(?<![\w'])\[([^\]]+)\]")


def _measure_id(table: str, name: str) -> str:
    return f"measure:{table}[{name}]"


def _column_id(table: str, name: str) -> str:
    return f"column:{table}[{name}]"


def _table_id(name: str) -> str:
    return f"table:{name}"


def analyze_dependencies(model: SemanticModel) -> list[Dependency]:
    """Infer dependencies from DAX references and model relationships.

    This intentionally stays conservative: dynamic references and DAX variables
    cannot always be resolved without a full DAX grammar.
    """
    known_columns = {
        (table.name.casefold(), column.name.casefold()): column
        for table in model.tables
        for column in table.columns
    }
    measures_by_name: dict[str, list[tuple[str, str]]] = {}
    for table in model.tables:
        for measure in table.measures:
            measures_by_name.setdefault(measure.name.casefold(), []).append(
                (table.name, measure.name)
            )

    dependencies: set[tuple[str, str, str]] = set()
    expressions: list[tuple[str, str, str]] = []
    for table in model.tables:
        for measure in table.measures:
            expressions.append((_measure_id(table.name, measure.name), table.name, measure.expression))
        for column in table.columns:
            if column.expression:
                expressions.append((_column_id(table.name, column.name), table.name, column.expression))
        if table.expression:
            expressions.append((_table_id(table.name), table.name, table.expression))

    for source, current_table, expression in expressions:
        qualified_spans: list[tuple[int, int]] = []
        for match in _QUALIFIED.finditer(expression or ""):
            table_name = (match.group(1) or match.group(2)).strip().replace("''", "'")
            object_name = match.group(3).strip()
            qualified_spans.append(match.span())
            if (table_name.casefold(), object_name.casefold()) in known_columns:
                target = _column_id(table_name, object_name)
                kind = "column_reference"
            else:
                matches = measures_by_name.get(object_name.casefold(), [])
                exact = next((item for item in matches if item[0].casefold() == table_name.casefold()), None)
                target = _measure_id(*(exact or (table_name, object_name)))
                kind = "measure_reference"
            if source != target:
                dependencies.add((source, target, kind))

        for match in _BRACKETED.finditer(expression or ""):
            if any(start <= match.start() < end for start, end in qualified_spans):
                continue
            object_name = match.group(1).strip()
            measure_matches = measures_by_name.get(object_name.casefold(), [])
            if len(measure_matches) == 1:
                target = _measure_id(*measure_matches[0])
                if source != target:
                    dependencies.add((source, target, "measure_reference"))
            elif (current_table.casefold(), object_name.casefold()) in known_columns:
                target = _column_id(current_table, object_name)
                if source != target:
                    dependencies.add((source, target, "column_reference"))

    for relationship in model.relationships:
        source = _column_id(relationship.from_table, relationship.from_column)
        target = _column_id(relationship.to_table, relationship.to_column)
        dependencies.add((source, target, "relationship"))

    return [Dependency(*item) for item in sorted(dependencies)]


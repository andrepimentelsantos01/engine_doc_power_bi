"""Semantic model parser for TMDL and legacy Tabular Model JSON."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Column, Measure, Partition, Relationship, SemanticModel, Table
from .tmdl import parse_tmdl_model


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_bim(path: Path, name: str) -> SemanticModel:
    raw = _read_json(path)
    source = raw.get("model", raw)
    model = SemanticModel(
        name=source.get("name", name),
        compatibility_level=raw.get("compatibilityLevel"),
        culture=source.get("culture"),
    )
    for raw_table in source.get("tables", []):
        table_name = raw_table.get("name", "Unnamed table")
        table = Table(
            name=table_name,
            description=raw_table.get("description"),
            hidden=raw_table.get("isHidden", False),
        )
        for raw_column in raw_table.get("columns", []):
            table.columns.append(
                Column(
                    name=raw_column.get("name", "Unnamed column"),
                    table=table_name,
                    data_type=raw_column.get("dataType", "unknown"),
                    expression=raw_column.get("expression"),
                    source_column=raw_column.get("sourceColumn"),
                    hidden=raw_column.get("isHidden", False),
                    description=raw_column.get("description"),
                    format_string=raw_column.get("formatString"),
                )
            )
        for raw_measure in raw_table.get("measures", []):
            expression = raw_measure.get("expression", "")
            if isinstance(expression, list):
                expression = "\n".join(expression)
            table.measures.append(
                Measure(
                    name=raw_measure.get("name", "Unnamed measure"),
                    table=table_name,
                    expression=expression,
                    description=raw_measure.get("description"),
                    format_string=raw_measure.get("formatString"),
                    hidden=raw_measure.get("isHidden", False),
                    display_folder=raw_measure.get("displayFolder"),
                )
            )
        for raw_partition in raw_table.get("partitions", []):
            source_data = raw_partition.get("source", {})
            expression = source_data.get("expression")
            if isinstance(expression, list):
                expression = "\n".join(expression)
            table.partitions.append(
                Partition(
                    name=raw_partition.get("name", table_name),
                    table=table_name,
                    mode=raw_partition.get("mode"),
                    source_type=source_data.get("type"),
                    expression=expression,
                )
            )
        model.tables.append(table)

    for raw_relationship in source.get("relationships", []):
        model.relationships.append(
            Relationship(
                name=raw_relationship.get("name", "Unnamed relationship"),
                from_table=raw_relationship.get("fromTable", ""),
                from_column=raw_relationship.get("fromColumn", ""),
                to_table=raw_relationship.get("toTable", ""),
                to_column=raw_relationship.get("toColumn", ""),
                cardinality=f"{raw_relationship.get('fromCardinality', 'many')}:"
                f"{raw_relationship.get('toCardinality', 'one')}",
                cross_filtering_behavior=raw_relationship.get("crossFilteringBehavior"),
                active=raw_relationship.get("isActive", True),
            )
        )
    return model


def parse_semantic_model(path: Path, name: str | None = None) -> SemanticModel:
    name = name or path.name.removesuffix(".SemanticModel")
    definition = path / "definition"
    if definition.exists() and any(definition.rglob("*.tmdl")):
        return parse_tmdl_model(definition, name)

    candidates = [path / "model.bim", path / "definition" / "model.bim"]
    candidates.extend(path.rglob("model.bim"))
    for candidate in candidates:
        if candidate.exists():
            return parse_bim(candidate, name)
    raise FileNotFoundError(f"No TMDL definition or model.bim found in {path}")


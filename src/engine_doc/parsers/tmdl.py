"""Small, dependency-free parser for the useful subset of TMDL."""

from __future__ import annotations

import re
from pathlib import Path

from ..models import Column, Measure, Partition, Relationship, SemanticModel, Table


_DECLARATION = re.compile(
    r"^(?P<indent>\s*)(?P<kind>table|column|measure|partition|relationship)\s+"
    r"(?P<name>'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[^:=]+?)"
    r"(?:\s*=\s*(?P<expression>.*))?$",
    re.IGNORECASE,
)
_PROPERTY = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z][\w.]*)\s*:\s*(?P<value>.*)$")


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('""', '"')
    return value


def _bool(value: str, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"true", "1", "yes"}


def _properties(lines: list[str], start: int, base_indent: int) -> tuple[dict[str, str], int]:
    props: dict[str, str] = {}
    body: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("//"):
            index += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= base_indent:
            break
        if _DECLARATION.match(line):
            break
        match = _PROPERTY.match(line)
        if match:
            key = match.group("key")
            value = match.group("value").strip()
            value_indent = len(match.group("indent"))
            continuation: list[str] = []
            lookahead = index + 1
            while lookahead < len(lines):
                next_line = lines[lookahead]
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_line.strip() and next_indent <= value_indent:
                    break
                if next_line.strip():
                    continuation.append(next_line.strip())
                lookahead += 1
            if continuation:
                value = "\n".join(([value] if value else []) + continuation)
                index = lookahead - 1
            props[key.lower()] = unquote(value)
        elif line.strip():
            body.append(line.strip())
        index += 1
    if body:
        props["__body__"] = "\n".join(body)
    return props, index


def parse_table_file(path: Path) -> Table | None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    table: Table | None = None
    index = 0
    while index < len(lines):
        match = _DECLARATION.match(lines[index])
        if not match:
            index += 1
            continue
        kind = match.group("kind").lower()
        name = unquote(match.group("name"))
        expression = (match.group("expression") or "").strip() or None
        indent = len(match.group("indent"))
        props, next_index = _properties(lines, index + 1, indent)

        if kind == "table":
            table = Table(
                name=name,
                description=props.get("description"),
                hidden=_bool(props.get("ishidden", "")),
                is_calculated=bool(expression),
                expression=expression,
            )
        elif table and kind == "column":
            column_expression = expression or props.get("expression") or props.get("__body__")
            table.columns.append(
                Column(
                    name=name,
                    table=table.name,
                    data_type=props.get("datatype", "unknown"),
                    expression=column_expression,
                    source_column=props.get("sourcecolumn"),
                    hidden=_bool(props.get("ishidden", "")),
                    description=props.get("description"),
                    format_string=props.get("formatstring"),
                )
            )
        elif table and kind == "measure":
            table.measures.append(
                Measure(
                    name=name,
                    table=table.name,
                    expression=expression or props.get("expression") or props.get("__body__", ""),
                    description=props.get("description"),
                    format_string=props.get("formatstring"),
                    hidden=_bool(props.get("ishidden", "")),
                    display_folder=props.get("displayfolder"),
                )
            )
        elif table and kind == "partition":
            table.partitions.append(
                Partition(
                    name=name,
                    table=table.name,
                    mode=props.get("mode"),
                    source_type=props.get("sourcetype"),
                    expression=(expression or props.get("source") or props.get("expression") or props.get("__body__")),
                )
            )
        index = max(index + 1, next_index)
    return table


def _split_object_reference(value: str) -> tuple[str, str]:
    value = value.strip()
    match = re.match(r"^(?:'((?:''|[^'])+)'|([^.'\[]+))\s*[.[]\s*([^\]]+)\]?$", value)
    if match:
        return unquote(match.group(1) or match.group(2)), unquote(match.group(3))
    if "." in value:
        table, column = value.rsplit(".", 1)
        return unquote(table), unquote(column)
    return "", unquote(value)


def parse_relationships(path: Path) -> list[Relationship]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    relationships: list[Relationship] = []
    for index, line in enumerate(lines):
        match = _DECLARATION.match(line)
        if not match or match.group("kind").lower() != "relationship":
            continue
        indent = len(match.group("indent"))
        props, _ = _properties(lines, index + 1, indent)
        from_table, from_column = _split_object_reference(props.get("fromcolumn", ""))
        to_table, to_column = _split_object_reference(props.get("tocolumn", ""))
        relationships.append(
            Relationship(
                name=unquote(match.group("name")),
                from_table=from_table,
                from_column=from_column,
                to_table=to_table,
                to_column=to_column,
                cardinality=props.get("fromcardinality") and (
                    f"{props['fromcardinality']}:{props.get('tocardinality', '?')}"
                ),
                cross_filtering_behavior=props.get("crossfilteringbehavior"),
                active=not (props.get("isactive", "true").lower() == "false"),
            )
        )
    return relationships


def parse_tmdl_model(definition_dir: Path, name: str) -> SemanticModel:
    model = SemanticModel(name=name)
    tables_dir = definition_dir / "tables"
    table_files = sorted(tables_dir.glob("*.tmdl")) if tables_dir.exists() else []
    if not table_files:
        table_files = [
            path
            for path in sorted(definition_dir.rglob("*.tmdl"))
            if path.name.lower() not in {"relationships.tmdl", "model.tmdl", "database.tmdl"}
        ]
    for path in table_files:
        table = parse_table_file(path)
        if table:
            model.tables.append(table)

    relationships_file = next(iter(definition_dir.rglob("relationships.tmdl")), None)
    if relationships_file:
        model.relationships = parse_relationships(relationships_file)

    model_file = next(iter(definition_dir.rglob("model.tmdl")), None)
    if model_file:
        text = model_file.read_text(encoding="utf-8-sig")
        culture = re.search(r"^\s*culture\s*:\s*([^\r\n]+)", text, re.MULTILINE | re.IGNORECASE)
        if culture:
            model.culture = unquote(culture.group(1))
    database_file = next(iter(definition_dir.rglob("database.tmdl")), None)
    if database_file:
        text = database_file.read_text(encoding="utf-8-sig")
        compatibility = re.search(
            r"^\s*compatibilityLevel\s*:\s*(\d+)", text, re.MULTILINE | re.IGNORECASE
        )
        if compatibility:
            model.compatibility_level = int(compatibility.group(1))
    return model

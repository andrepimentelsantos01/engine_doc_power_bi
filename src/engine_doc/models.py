"""Domain objects shared by parsers, analyzers, and exporters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Column:
    name: str
    table: str
    data_type: str = "unknown"
    expression: str | None = None
    source_column: str | None = None
    hidden: bool = False
    description: str | None = None
    format_string: str | None = None

    @property
    def calculated(self) -> bool:
        return bool(self.expression)


@dataclass(slots=True)
class Measure:
    name: str
    table: str
    expression: str
    description: str | None = None
    format_string: str | None = None
    hidden: bool = False
    display_folder: str | None = None


@dataclass(slots=True)
class Partition:
    name: str
    table: str
    mode: str | None = None
    source_type: str | None = None
    expression: str | None = None


@dataclass(slots=True)
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    measures: list[Measure] = field(default_factory=list)
    partitions: list[Partition] = field(default_factory=list)
    description: str | None = None
    hidden: bool = False
    is_calculated: bool = False
    expression: str | None = None


@dataclass(slots=True)
class Relationship:
    name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str | None = None
    cross_filtering_behavior: str | None = None
    active: bool = True


@dataclass(slots=True)
class ReportPage:
    name: str
    display_name: str
    visual_count: int = 0
    visual_types: list[str] = field(default_factory=list)
    hidden: bool = False


@dataclass(slots=True)
class Report:
    name: str
    pages: list[ReportPage] = field(default_factory=list)
    theme: str | None = None


@dataclass(slots=True)
class Dependency:
    source: str
    target: str
    kind: str


@dataclass(slots=True)
class SemanticModel:
    name: str
    tables: list[Table] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    compatibility_level: int | None = None
    culture: str | None = None


@dataclass(slots=True)
class PBIPProject:
    name: str
    root: Path
    descriptor: Path | None = None
    semantic_model_path: Path | None = None
    report_path: Path | None = None
    model: SemanticModel | None = None
    report: Report | None = None
    dependencies: list[Dependency] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["root"] = str(self.root)
        data["descriptor"] = str(self.descriptor) if self.descriptor else None
        data["semantic_model_path"] = (
            str(self.semantic_model_path) if self.semantic_model_path else None
        )
        data["report_path"] = str(self.report_path) if self.report_path else None
        return data


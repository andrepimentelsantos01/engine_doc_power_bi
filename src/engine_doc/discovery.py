"""Discover Power BI Project (PBIP) artifacts without assuming a fixed layout."""

from __future__ import annotations

import json
from pathlib import Path

from .models import PBIPProject


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _resolve_reference(descriptor: Path, data: dict, key: str) -> Path | None:
    artifacts = data.get("artifacts", {})
    if isinstance(artifacts, list):
        artifact = next(
            (item.get(key, {}) for item in artifacts if isinstance(item, dict) and key in item),
            {},
        )
    elif isinstance(artifacts, dict):
        artifact = artifacts.get(key, {})
    else:
        artifact = {}
    relative = artifact.get("path") if isinstance(artifact, dict) else None
    if not relative:
        return None
    candidate = (descriptor.parent / relative).resolve()
    return candidate if candidate.exists() else None


def _first_artifact(root: Path, suffix: str) -> Path | None:
    candidates = sorted(p for p in root.rglob(f"*{suffix}") if p.is_dir())
    return candidates[0] if candidates else None


def discover_projects(input_dir: Path) -> list[PBIPProject]:
    """Return projects found below *input_dir*.

    A descriptor is preferred, but loose ``*.SemanticModel`` and ``*.Report``
    folders are accepted so partially copied PBIP projects can still be read.
    """
    input_dir = input_dir.resolve()
    if not input_dir.exists():
        return []

    projects: list[PBIPProject] = []
    descriptors = sorted(input_dir.rglob("*.pbip"))
    claimed: set[Path] = set()

    for descriptor in descriptors:
        data = _load_json(descriptor)
        semantic = _resolve_reference(descriptor, data, "semanticModel")
        report = _resolve_reference(descriptor, data, "report")
        base = descriptor.parent
        semantic = semantic or _first_artifact(base, ".SemanticModel")
        report = report or _first_artifact(base, ".Report")
        if semantic:
            claimed.add(semantic.resolve())
        if report:
            claimed.add(report.resolve())
        projects.append(
            PBIPProject(
                name=descriptor.stem,
                root=base,
                descriptor=descriptor,
                semantic_model_path=semantic,
                report_path=report,
            )
        )

    loose_semantic = sorted(input_dir.rglob("*.SemanticModel"))
    loose_reports = sorted(input_dir.rglob("*.Report"))
    loose_by_parent: dict[Path, dict[str, Path]] = {}
    for path in loose_semantic:
        if path.is_dir() and path.resolve() not in claimed:
            loose_by_parent.setdefault(path.parent, {})["semantic"] = path
    for path in loose_reports:
        if path.is_dir() and path.resolve() not in claimed:
            loose_by_parent.setdefault(path.parent, {})["report"] = path

    for parent, artifacts in loose_by_parent.items():
        seed = artifacts.get("semantic") or artifacts.get("report")
        assert seed is not None
        name = seed.name.rsplit(".", 1)[0]
        projects.append(
            PBIPProject(
                name=name,
                root=parent,
                semantic_model_path=artifacts.get("semantic"),
                report_path=artifacts.get("report"),
            )
        )

    return projects

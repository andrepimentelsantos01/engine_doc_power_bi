"""Report parser supporting PBIR folders and legacy report.json files."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Report, ReportPage


def _json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _visual_type(raw: dict) -> str:
    visual = raw.get("visual", raw)
    return (
        visual.get("visualType")
        or visual.get("singleVisual", {}).get("visualType")
        or raw.get("visualType")
        or "unknown"
    )


def _parse_pbir(path: Path, name: str) -> Report:
    report = Report(name=name)
    definition = path / "definition"
    pages_root = definition / "pages"
    pages_index = _json(pages_root / "pages.json")
    page_order = pages_index.get("pageOrder", [])
    page_paths = [pages_root / page_name for page_name in page_order]
    if not page_paths:
        page_paths = sorted(p.parent for p in pages_root.rglob("page.json"))

    for page_path in page_paths:
        raw_page = _json(page_path / "page.json")
        if not raw_page:
            continue
        types: list[str] = []
        visuals_root = page_path / "visuals"
        if visuals_root.exists():
            for visual_file in sorted(visuals_root.rglob("visual.json")):
                types.append(_visual_type(_json(visual_file)))
        report.pages.append(
            ReportPage(
                name=raw_page.get("name", page_path.name),
                display_name=raw_page.get("displayName", raw_page.get("name", page_path.name)),
                visual_count=len(types),
                visual_types=types,
                hidden=raw_page.get("visibility") == "HiddenInViewMode",
            )
        )
    return report


def _parse_legacy(path: Path, name: str) -> Report:
    raw = _json(path)
    report = Report(name=name)
    for section in raw.get("sections", []):
        visual_types: list[str] = []
        for container in section.get("visualContainers", []):
            config = container.get("config", {})
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except json.JSONDecodeError:
                    config = {}
            visual_types.append(_visual_type(config))
        report.pages.append(
            ReportPage(
                name=section.get("name", "Unnamed page"),
                display_name=section.get("displayName", section.get("name", "Unnamed page")),
                visual_count=len(visual_types),
                visual_types=visual_types,
                hidden=section.get("visibility") == 1,
            )
        )
    return report


def parse_report(path: Path, name: str | None = None) -> Report:
    name = name or path.name.removesuffix(".Report")
    if (path / "definition" / "pages").exists():
        return _parse_pbir(path, name)
    candidates = [path / "report.json", path / "definition" / "report.json"]
    candidates.extend(path.rglob("report.json"))
    for candidate in candidates:
        if candidate.exists():
            return _parse_legacy(candidate, name)
    raise FileNotFoundError(f"No PBIR definition or report.json found in {path}")

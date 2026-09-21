"""Render lineage as a Mermaid flowchart."""

from __future__ import annotations

import hashlib

from ..models import PBIPProject


def _node_id(value: str) -> str:
    return "n" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def _label(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ")


def build_mermaid(project: PBIPProject) -> str:
    lines = ["flowchart LR"]
    nodes: set[str] = set()
    for dependency in project.dependencies:
        for value in (dependency.source, dependency.target):
            if value not in nodes:
                nodes.add(value)
                lines.append(f'    {_node_id(value)}["{_label(value)}"]')
        arrow = "-.->" if dependency.kind == "relationship" else "-->"
        lines.append(
            f'    {_node_id(dependency.source)} {arrow}|{dependency.kind}| '
            f'{_node_id(dependency.target)}'
        )
    if len(lines) == 1:
        lines.append('    empty["No dependencies detected"]')
    return "\n".join(lines) + "\n"


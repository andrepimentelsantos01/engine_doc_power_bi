"""Generate a lightweight static landing page for the local preview."""

from __future__ import annotations

import html
import json
from pathlib import Path

from ..models import PBIPProject
from .text import safe_filename


def _project_card(project: PBIPProject, relative_path: str) -> str:
    tables = project.model.tables if project.model else []
    measures = sum(len(table.measures) for table in tables)
    columns = sum(len(table.columns) for table in tables)
    pages = len(project.report.pages) if project.report else 0
    name = html.escape(project.name)
    href = html.escape(relative_path.replace("\\", "/"))
    stem = safe_filename(project.name)
    return f"""
    <article class="card">
      <div><span class="status"></span> DOCUMENTED</div>
      <h2>{name}</h2>
      <div class="stats">
        <span><b>{len(tables)}</b> tables</span><span><b>{columns}</b> columns</span>
        <span><b>{measures}</b> measures</span><span><b>{pages}</b> pages</span>
      </div>
      <div class="links">
        <a href="{href}/{stem}_raio_x.txt">Raio-X TXT</a>
        <a href="{href}/README.md">Markdown</a>
        <a href="{href}/metadata.json">JSON</a>
      </div>
    </article>"""


def write_index(output_root: Path, projects: list[tuple[PBIPProject, Path]]) -> None:
    cards = "\n".join(
        _project_card(project, str(target.relative_to(output_root)))
        for project, target in projects
    )
    if not cards:
        cards = """
        <article class="card empty">
          <h2>No PBIP project found</h2>
          <p>Place a <code>.pbip</code> project inside <code>input/</code> and run the command again.</p>
        </article>"""
    payload = json.dumps([project.name for project, _ in projects], ensure_ascii=False)
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Engine Doc Power BI</title>
  <style>
    :root{{--bg:#071018;--panel:#0e1b26;--line:#1d3444;--text:#e8f1f7;--muted:#8ea6b5;--accent:#f2c811}}
    *{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 85% -20%,#17364a,transparent 42%),var(--bg);color:var(--text);font:15px/1.55 Inter,Segoe UI,sans-serif;min-height:100vh}}
    main{{max-width:1080px;margin:auto;padding:64px 24px}} header{{margin-bottom:42px}} .eyebrow{{color:var(--accent);font-weight:800;letter-spacing:.16em;font-size:12px}} h1{{font-size:clamp(38px,6vw,68px);line-height:1;margin:12px 0}} header p{{color:var(--muted);font-size:18px;max-width:700px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}} .card{{background:linear-gradient(145deg,#10202c,#0b1720);border:1px solid var(--line);border-radius:18px;padding:26px;box-shadow:0 24px 70px #0005}} .card>div:first-child{{font-size:11px;letter-spacing:.12em;color:var(--muted)}} .status{{display:inline-block;width:7px;height:7px;border-radius:50%;background:#52d273;box-shadow:0 0 12px #52d273;margin-right:7px}} h2{{font-size:24px;margin:14px 0 20px}} .stats{{display:grid;grid-template-columns:1fr 1fr;gap:10px;color:var(--muted)}} .stats span{{background:#07131b;padding:10px;border-radius:9px}} .stats b{{color:var(--text);font-size:18px;margin-right:4px}} .links{{display:flex;gap:10px;margin-top:22px}} a{{color:#071018;background:var(--accent);font-weight:750;text-decoration:none;padding:9px 14px;border-radius:8px}} a+ a{{background:#1a2c38;color:var(--text)}} code{{color:var(--accent)}} footer{{color:var(--muted);margin-top:38px;border-top:1px solid var(--line);padding-top:20px}}
  </style>
</head>
<body><main>
  <header><div class="eyebrow">ENGINE DOC POWER BI</div><h1>PBIP, documented.</h1><p>Automatic technical inventory, dependencies, and lineage generated locally from your Power BI project.</p></header>
  <section class="grid">{cards}</section>
  <footer>PBIP → automatic analysis → technical documentation</footer>
  <script>window.engineDocProjects={payload};</script>
</main></body></html>"""
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "index.html").write_text(document, encoding="utf-8")

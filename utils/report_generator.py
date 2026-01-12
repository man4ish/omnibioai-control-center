#!/usr/bin/env python3
"""
OmniBioAI Platform — Interactive Architecture + Codebase Statistics Report (Plotly)

What it does
------------
1) Runs `cloc` (JSON) over multiple repos/files with strict excludes
2) Produces an INTERACTIVE HTML report containing:
   - Architecture diagram (interactive graph)
   - Project-wise contribution (pie + bar)
   - Language-wise contribution overall (pie + bar)
   - Summary tables (projects + languages)

Usage
-----
# From repo root (e.g. ~/Desktop/machine):
python utils/cloc_multi_report.py

# Or specify paths:
python utils/cloc_multi_report.py omnibioai omnibioai-tool-exec ragbio lims-x

Requirements
------------
- cloc installed and on PATH
- plotly installed: pip install plotly

Output
------
- out/reports/omnibioai_codebase_report.html
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Union

# Plotly (interactive HTML)
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ------------------------------------------------------------------------------
# cloc exclusions (keep aligned with your safe excludes)
# ------------------------------------------------------------------------------
EXCLUDE_DIRS = (
    "obsolete,staticfiles,node_modules,.venv,env,__pycache__,migrations,"
    "admin,venv,gnn_env,venv_sys,work,input,demo"
)
EXCLUDE_EXTS = "svg,json,txt,csv,lock,min.js,map,md"
NOT_MATCH_D = r"(data|uploads|downloads|cache|results|logs)"


# ------------------------------------------------------------------------------
# Data model
# ------------------------------------------------------------------------------
@dataclass
class Totals:
    files: int = 0
    blank: int = 0
    comment: int = 0
    code: int = 0

    def add(self, other: "Totals") -> None:
        self.files += other.files
        self.blank += other.blank
        self.comment += other.comment
        self.code += other.code


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def fmt_int(n: int) -> str:
    return f"{n:,}"


def safe_div(a: float, b: float) -> float:
    return (a / b) if b else 0.0


def ensure_cloc() -> None:
    if shutil.which("cloc") is None:
        print("ERROR: cloc is not installed or not on PATH.", file=sys.stderr)
        print("Install: sudo apt-get install cloc  (or: conda install -c conda-forge cloc)", file=sys.stderr)
        raise SystemExit(2)


def run_cloc(path: Path) -> Tuple[Totals, Dict[str, Totals]]:
    """
    Returns:
      - overall totals
      - per-language totals dict
    """
    cmd = [
        "cloc",
        str(path),
        "--exclude-dir",
        EXCLUDE_DIRS,
        "--exclude-ext",
        EXCLUDE_EXTS,
        "--fullpath",
        "--not-match-d",
        NOT_MATCH_D,
        "--json",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"cloc failed for {path}:\n{proc.stderr.strip()}")

    data = json.loads(proc.stdout)

    if "SUM" not in data:
        raise RuntimeError(f"Unexpected cloc JSON output for {path} (missing SUM).")

    sum_row = data["SUM"]
    overall = Totals(
        files=int(sum_row.get("nFiles", 0)),
        blank=int(sum_row.get("blank", 0)),
        comment=int(sum_row.get("comment", 0)),
        code=int(sum_row.get("code", 0)),
    )

    per_lang: Dict[str, Totals] = {}
    for k, v in data.items():
        if k in ("header", "SUM"):
            continue
        if isinstance(v, dict) and "code" in v:
            per_lang[k] = Totals(
                files=int(v.get("nFiles", 0)),
                blank=int(v.get("blank", 0)),
                comment=int(v.get("comment", 0)),
                code=int(v.get("code", 0)),
            )

    return overall, per_lang


def validate_paths(paths: List[Path]) -> None:
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print("ERROR: These paths do not exist:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        raise SystemExit(2)


# ------------------------------------------------------------------------------
# Architecture diagram (Plotly graph)
# ------------------------------------------------------------------------------
def build_architecture_spec(existing_projects: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Returns:
      nodes: list of node ids (strings)
      edges: list of (src, dst)
    Notes:
      - This is intentionally opinionated but easy to adjust.
      - It only includes nodes that exist in `existing_projects`.
    """
    # Canonical node names we will use in the diagram.
    # Keep these aligned with your repo folder names.
    nodes_wanted = [
        "omnibioai",              # Django workbench
        "lims-x",                 # LIMS
        "ragbio",                 # RAG assistant
        "omnibioai-toolserver",   # FastAPI toolserver
        "omnibioai-tool-exec",    # TES execution service
        "omnibioai_sdk",          # SDK
        "aws-tools",              # tool images / runners
        "k8s",                    # infra
        "ai-dev-docker",          # dev infra
        "db-init",                # DB init/seed
        "docker-compose.yml",
        "start_stack_tmux.sh",
        "smoke_test_stack.sh",
    ]

    nodes = [n for n in nodes_wanted if n in existing_projects]

    # Directed edges: "who uses who"
    edges_wanted = [
        ("omnibioai", "lims-x"),
        ("omnibioai", "ragbio"),
        ("omnibioai", "omnibioai-toolserver"),
        ("omnibioai-toolserver", "omnibioai-tool-exec"),
        ("omnibioai-tool-exec", "aws-tools"),
        ("omnibioai_sdk", "omnibioai"),
        ("omnibioai_sdk", "omnibioai-toolserver"),
        ("db-init", "omnibioai"),
        ("k8s", "omnibioai"),
        ("k8s", "omnibioai-toolserver"),
        ("k8s", "omnibioai-tool-exec"),
        ("ai-dev-docker", "omnibioai"),
        ("docker-compose.yml", "omnibioai"),
        ("docker-compose.yml", "omnibioai-toolserver"),
        ("docker-compose.yml", "omnibioai-tool-exec"),
        ("start_stack_tmux.sh", "docker-compose.yml"),
        ("smoke_test_stack.sh", "docker-compose.yml"),
    ]
    edges = [(a, b) for (a, b) in edges_wanted if a in nodes and b in nodes]
    return nodes, edges


def circular_layout(nodes: List[str], radius: float = 1.0) -> Dict[str, Tuple[float, float]]:
    """
    Simple deterministic layout to avoid extra deps (no networkx).
    """
    import math

    n = max(len(nodes), 1)
    pos: Dict[str, Tuple[float, float]] = {}
    for i, node in enumerate(nodes):
        angle = 2 * math.pi * (i / n)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        pos[node] = (x, y)
    return pos


def architecture_figure(
    nodes: List[str],
    edges: List[Tuple[str, str]],
    project_totals: Dict[str, Totals],
) -> go.Figure:
    """
    Interactive architecture diagram with:
      - Node size proportional to code lines
      - Hover shows project metrics
      - Edges rendered as lines with arrow-like direction marker (lightweight)
    """
    # Layout
    pos = circular_layout(nodes, radius=1.0)

    # Node sizing: scale code lines into marker size
    codes = [project_totals.get(n, Totals()).code for n in nodes]
    max_code = max(codes) if codes else 1
    min_size, max_size = 18, 55
    sizes = [
        min_size + (max_size - min_size) * safe_div(c, max_code)
        for c in codes
    ]

    # Edge traces (lines)
    edge_x: List[float] = []
    edge_y: List[float] = []
    for a, b in edges:
        x0, y0 = pos[a]
        x1, y1 = pos[b]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1),
        hoverinfo="none",
        mode="lines",
        name="dependencies",
    )

    # Node trace
    node_x = [pos[n][0] for n in nodes]
    node_y = [pos[n][1] for n in nodes]

    hover_text = []
    for n in nodes:
        t = project_totals.get(n, Totals())
        hover_text.append(
            f"<b>{n}</b><br>"
            f"Files: {fmt_int(t.files)}<br>"
            f"Blank: {fmt_int(t.blank)}<br>"
            f"Comment: {fmt_int(t.comment)}<br>"
            f"Code: {fmt_int(t.code)}"
        )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=nodes,
        textposition="top center",
        hovertext=hover_text,
        hoverinfo="text",
        marker=dict(
            size=sizes,
            line=dict(width=1),
            opacity=0.95,
        ),
        name="components",
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title="Architecture (interactive) — node size ~ code lines",
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=60, b=20),
        height=520,
    )
    return fig


# ------------------------------------------------------------------------------
# Charts + tables
# ------------------------------------------------------------------------------
def pie_figure(labels: List[str], values: List[int], title: str) -> go.Figure:
    fig = go.Figure(
        data=[go.Pie(labels=labels, values=values, hole=0.35)]
    )
    fig.update_layout(title=title, height=420, margin=dict(l=20, r=20, t=60, b=20))
    return fig


def bar_figure(x: List[str], y: List[int], title: str, ytitle: str = "Code lines") -> go.Figure:
    fig = go.Figure(data=[go.Bar(x=x, y=y)])
    fig.update_layout(
        title=title,
        xaxis_title="",
        yaxis_title=ytitle,
        height=420,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


def table_figure(rows: List[Dict[str, Union[str, int]]], title: str) -> go.Figure:
    if not rows:
        return go.Figure()

    cols = list(rows[0].keys())
    values = [[r[c] for r in rows] for c in cols]

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(values=[f"<b>{c}</b>" for c in cols], align="left"),
                cells=dict(values=values, align="left"),
            )
        ]
    )
    fig.update_layout(title=title, height=420, margin=dict(l=20, r=20, t=60, b=20))
    return fig


# ------------------------------------------------------------------------------
# Report composer
# ------------------------------------------------------------------------------
def build_report(
    out_html: Path,
    title: str,
    timestamp: str,
    grand: Totals,
    project_totals: Dict[str, Totals],
    language_totals: Dict[str, Totals],
) -> None:
    # Sort projects by code desc
    proj_sorted = sorted(project_totals.items(), key=lambda kv: kv[1].code, reverse=True)
    proj_labels = [k for k, _ in proj_sorted]
    proj_values = [v.code for _, v in proj_sorted]

    # Sort languages by code desc
    lang_sorted = sorted(language_totals.items(), key=lambda kv: kv[1].code, reverse=True)
    lang_labels = [k for k, _ in lang_sorted]
    lang_values = [v.code for _, v in lang_sorted]

    # Figures
    nodes, edges = build_architecture_spec(existing_projects=list(project_totals.keys()))
    fig_arch = architecture_figure(nodes, edges, project_totals)

    fig_proj_pie = pie_figure(proj_labels, proj_values, "Project contribution (by code lines)")
    fig_proj_bar = bar_figure(proj_labels, proj_values, "Project contribution (bar)", "Code lines")

    fig_lang_pie = pie_figure(lang_labels[:14], lang_values[:14], "Top languages (by code lines)")
    fig_lang_bar = bar_figure(lang_labels[:20], lang_values[:20], "Top languages (bar)", "Code lines")

    # Tables
    proj_rows = []
    for name, t in proj_sorted:
        proj_rows.append(
            {
                "Project": name,
                "Files": t.files,
                "Blank": t.blank,
                "Comment": t.comment,
                "Code": t.code,
                "Code %": round(100.0 * safe_div(t.code, grand.code), 2),
            }
        )
    fig_proj_table = table_figure(proj_rows, "Per-project totals")

    lang_rows = []
    for name, t in lang_sorted:
        lang_rows.append(
            {
                "Language": name,
                "Files": t.files,
                "Blank": t.blank,
                "Comment": t.comment,
                "Code": t.code,
                "Code %": round(100.0 * safe_div(t.code, grand.code), 2),
            }
        )
    fig_lang_table = table_figure(lang_rows, "Language totals (overall)")

    # Combine into a single HTML report by concatenating figure HTML fragments.
    # This avoids Dash and keeps it as a portable file.
    out_html.parent.mkdir(parents=True, exist_ok=True)

    # Small HTML shell
    summary_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 1200px; margin: 18px auto;">
      <h1 style="margin-bottom: 6px;">{title}</h1>
      <div style="color: #555; margin-bottom: 16px;">
        <div><b>Generated:</b> {timestamp}</div>
        <div><b>Grand total:</b> Files {fmt_int(grand.files)} · Blank {fmt_int(grand.blank)} · Comment {fmt_int(grand.comment)} · Code {fmt_int(grand.code)}</div>
      </div>
      <hr/>
      <h2>Architecture</h2>
      <p style="color:#555; margin-top: -6px;">
        Interactive dependency view (opinionated). Node size is proportional to code lines; hover nodes for metrics.
      </p>
    </div>
    """

    # Plotly figure HTML fragments (include plotly.js once)
    arch_html = fig_arch.to_html(full_html=False, include_plotlyjs="cdn")
    proj_pie_html = fig_proj_pie.to_html(full_html=False, include_plotlyjs=False)
    proj_bar_html = fig_proj_bar.to_html(full_html=False, include_plotlyjs=False)
    lang_pie_html = fig_lang_pie.to_html(full_html=False, include_plotlyjs=False)
    lang_bar_html = fig_lang_bar.to_html(full_html=False, include_plotlyjs=False)
    proj_table_html = fig_proj_table.to_html(full_html=False, include_plotlyjs=False)
    lang_table_html = fig_lang_table.to_html(full_html=False, include_plotlyjs=False)

    # Two-column responsive layout sections
    sections_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 1200px; margin: 18px auto;">
      {arch_html}
      <hr style="margin: 22px 0;"/>

      <h2>Project contributions</h2>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 18px;">
        <div>{proj_pie_html}</div>
        <div>{proj_bar_html}</div>
      </div>
      <div style="margin-top: 14px;">{proj_table_html}</div>

      <hr style="margin: 22px 0;"/>

      <h2>Language contributions (overall)</h2>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 18px;">
        <div>{lang_pie_html}</div>
        <div>{lang_bar_html}</div>
      </div>
      <div style="margin-top: 14px;">{lang_table_html}</div>

      <hr style="margin: 22px 0;"/>
      <div style="color:#777; font-size: 12px;">
        Notes: counts exclude vendored/runtime dirs and selected file extensions per your cloc policy.
      </div>
    </div>
    """

    full_html = f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body>{summary_html}{sections_html}</body></html>"
    out_html.write_text(full_html, encoding="utf-8")


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
def main() -> int:
    ensure_cloc()

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = "OmniBioAI Platform — Architecture + Codebase Statistics (Interactive)"

    # Default dirs (same spirit as your current script)
    if len(sys.argv) > 1:
        targets = [Path(p) for p in sys.argv[1:]]
    else:
        targets = [
            Path("omnibioai-tool-exec"),
            Path("omnibioai"),
            Path("ragbio"),
            Path("lims-x"),
            Path("omnibioai-toolserver"),
            Path("aws-tools"),
            Path("db-init"),
            Path("ai-dev-docker"),
            Path("k8s"),
            Path("docker-compose.yml"),
            Path("start_stack_tmux.sh"),
            Path("smoke_test_stack.sh"),
            Path("omnibioai_sdk"),
        ]

    validate_paths(targets)

    project_totals: Dict[str, Totals] = {}
    language_totals: Dict[str, Totals] = {}
    grand = Totals()

    for t in targets:
        overall, per_lang = run_cloc(t)

        key = str(t)
        project_totals[key] = overall
        grand.add(overall)

        for lang, tot in per_lang.items():
            language_totals.setdefault(lang, Totals()).add(tot)

    out_html = Path("out/reports/omnibioai_codebase_report.html")
    build_report(
        out_html=out_html,
        title=title,
        timestamp=ts,
        grand=grand,
        project_totals=project_totals,
        language_totals=language_totals,
    )

    print(f"\nOK: wrote interactive report: {out_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

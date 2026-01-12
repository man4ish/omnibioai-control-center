#!/usr/bin/env python3
"""
Run cloc on multiple directories and print per-dir + grand-total stats.

Usage:
  python utils/cloc_multi.py omnibioai-tool-exec/ omnibioai/ ragbio/ lims-x/
  # or, if you run it from ~/Desktop/machine:
  python utils/cloc_multi.py

Requires:
  cloc installed and available on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


# Keep this aligned with your "safe" cloc excludes (to avoid counting vendored envs / admin trees)
EXCLUDE_DIRS = (
    "obsolete,staticfiles,node_modules,.venv,env,__pycache__,migrations,"
    "admin,venv,gnn_env,venv_sys,work,input,demo"
)
EXCLUDE_EXTS = "svg,json,txt,csv,lock,min.js,map,md"
NOT_MATCH_D = r"(data|uploads|downloads|cache|results|logs)"


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


def print_header() -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "=" * 80)
    print("OmniBioAI Platform — Codebase Statistics")
    print("=" * 80)
    print("Unified metrics across the OmniBioAI ecosystem")
    print("Generated using cloc with strict exclusions (no vendored/runtime data)")
    print(f"Timestamp: {ts}")
    print("=" * 80)


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

    # cloc JSON has a "SUM" entry with totals
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
        # language rows look like {"code":..., "comment":..., "blank":..., "nFiles":...}
        if isinstance(v, dict) and "code" in v:
            per_lang[k] = Totals(
                files=int(v.get("nFiles", 0)),
                blank=int(v.get("blank", 0)),
                comment=int(v.get("comment", 0)),
                code=int(v.get("code", 0)),
            )

    return overall, per_lang


def fmt_int(n: int) -> str:
    return f"{n:,}"


def main() -> int:
    if shutil.which("cloc") is None:
        print("ERROR: cloc is not installed or not on PATH.", file=sys.stderr)
        print("Install: sudo apt-get install cloc  (or: conda install -c conda-forge cloc)", file=sys.stderr)
        return 2

    print_header()

    # Default to the repos you showed (plus LIMS-X)
    if len(sys.argv) > 1:
        dirs = [Path(p) for p in sys.argv[1:]]
    else:
        dirs = [
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

    # Validate
    missing = [str(d) for d in dirs if not d.exists()]
    if missing:
        print("ERROR: These paths do not exist:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 2

    grand = Totals()

    print("\nPer-project totals (from cloc JSON SUM):")
    print("-" * 78)
    print(f"{'Project':40} {'Files':>8} {'Blank':>10} {'Comment':>10} {'Code':>10}")
    print("-" * 78)

    per_project_langs: List[Tuple[str, Dict[str, Totals]]] = []

    for d in dirs:
        overall, per_lang = run_cloc(d)
        grand.add(overall)
        per_project_langs.append((str(d), per_lang))

        print(
            f"{str(d):40} {fmt_int(overall.files):>8} {fmt_int(overall.blank):>10} "
            f"{fmt_int(overall.comment):>10} {fmt_int(overall.code):>10}"
        )

    print("-" * 78)
    print(
        f"{'GRAND TOTAL':40} {fmt_int(grand.files):>8} {fmt_int(grand.blank):>10} "
        f"{fmt_int(grand.comment):>10} {fmt_int(grand.code):>10}"
    )
    print("-" * 78)

    # Optional: top languages across all projects (by code)
    lang_totals: Dict[str, Totals] = {}
    for _, per_lang in per_project_langs:
        for lang, t in per_lang.items():
            lang_totals.setdefault(lang, Totals()).add(t)

    top = sorted(lang_totals.items(), key=lambda kv: kv[1].code, reverse=True)[:12]
    if top:
        print("\nTop languages (combined, by code lines):")
        print("-" * 78)
        print(f"{'Language':25} {'Files':>8} {'Blank':>10} {'Comment':>10} {'Code':>10}")
        print("-" * 78)
        for lang, t in top:
            print(
                f"{lang:25} {fmt_int(t.files):>8} {fmt_int(t.blank):>10} "
                f"{fmt_int(t.comment):>10} {fmt_int(t.code):>10}"
            )
        print("-" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

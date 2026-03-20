"""
control_center/api/routes_report.py

Serves the ecosystem HTML report at GET /report.

The report is generated on-demand (or served from cache if the pre-generated
file exists at WORKSPACE_ROOT/out/reports/omnibioai_ecosystem_report.html).

Environment variables
---------------------
WORKSPACE_ROOT          Root of the ecosystem checkout (default: /workspace)
CONTROL_CENTER_BASE_URL Base URL of this control center for health data
                        (default: http://127.0.0.1:7070)
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_REPORT_RELPATH = "out/reports/omnibioai_ecosystem_report.html"
_PLACEHOLDER = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>OmniBioAI — Report not yet generated</title>
  <style>
    body {{
      font-family: 'IBM Plex Sans', Arial, sans-serif;
      background: #F1F5F9;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }}
    .box {{
      background: white;
      border: 1px solid #E5E7EB;
      border-radius: 16px;
      padding: 40px 48px;
      text-align: center;
      max-width: 480px;
    }}
    h1 {{ font-size: 18px; color: #0F172A; margin-bottom: 12px; }}
    p  {{ font-size: 13px; color: #6B7280; line-height: 1.7; margin-bottom: 20px; }}
    code {{
      background: #F8FAFC;
      border: 1px solid #E5E7EB;
      border-radius: 6px;
      padding: 10px 16px;
      font-size: 12px;
      display: block;
      text-align: left;
      color: #374151;
    }}
  </style>
</head>
<body>
  <div class="box">
    <h1>Report not yet generated</h1>
    <p>
      The ecosystem report has not been generated yet.<br>
      Run the following command from the ecosystem root:
    </p>
    <code>python scripts/generate_report.py</code>
  </div>
</body>
</html>
"""


def _workspace_root() -> Path:
    return Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))


@router.get("/report", response_class=HTMLResponse)
def report() -> str:
    """
    Serve the pre-generated ecosystem HTML report.
    Returns a friendly placeholder page if the report has not been generated yet.
    """
    report_path = _workspace_root() / _REPORT_RELPATH
    if report_path.exists():
        return report_path.read_text(encoding="utf-8")
    return _PLACEHOLDER
"""
control_center/api/routes_report.py

Routes for the ecosystem HTML report.

GET /report  → redirects to / which serves the report with the injected
               OmniBioAI header (Regenerate button, live service status).

Environment variables
---------------------
WORKSPACE_ROOT          Root of the ecosystem checkout (default: /workspace)
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

_REPORT_RELPATH = "out/reports/omnibioai_ecosystem_report.html"


def _workspace_root() -> Path:
    return Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))


def _report_path() -> Path:
    return _workspace_root() / _REPORT_RELPATH


def report_exists() -> bool:
    return _report_path().exists()


@router.get("/report")
def report() -> RedirectResponse:
    """
    Redirect /report → / which injects the OmniBioAI header
    (Regenerate button, live service status chip, Dashboard link)
    before serving the report HTML.

    Uses 302 (temporary) so browsers don't cache the redirect —
    important during development when the route may change.
    """
    return RedirectResponse(url="/", status_code=302)
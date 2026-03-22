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

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


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
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from control_center.core.settings import load_settings
from control_center.core.runner import run_all_checks

router = APIRouter()


@router.get("/services")
def services() -> JSONResponse:
    try:
        settings = load_settings()
        results = run_all_checks(settings)
        return JSONResponse({"services": results})
    except FileNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
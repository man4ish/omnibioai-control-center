from __future__ import annotations

from fastapi import APIRouter

from control_center.core.settings import load_settings
from control_center.core.runner import run_all_checks

router = APIRouter()


@router.get("/services")
def services() -> dict:
    settings = load_settings()
    results = run_all_checks(settings)
    return {"services": results}

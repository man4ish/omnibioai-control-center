from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from control_center.core.settings import load_settings
from control_center.core.runner import run_all_checks
from control_center.checks.disk import run_disk_checks

router = APIRouter()


@router.get("/summary")
def summary() -> dict:
    settings = load_settings()
    service_results = run_all_checks(settings)
    disk_results = run_disk_checks(settings)

    overall = "UP"
    for r in service_results + disk_results:
        if r["status"] == "DOWN":
            overall = "DOWN"
            break
        if r["status"] == "WARN" and overall != "DOWN":
            overall = "WARN"

    return {
        "overall_status": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "services": service_results,
        "system": {
            "disk": disk_results,
        },
    }

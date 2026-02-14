from __future__ import annotations

import shutil
from typing import Any


def run_disk_checks(settings: Any) -> list[dict]:
    system = settings.system or {}
    disk_cfgs = (system.get("disk_checks") or []) if isinstance(system, dict) else []
    results: list[dict] = []

    for cfg in disk_cfgs:
        path = cfg.get("path")
        warn_pct_free_below = float(cfg.get("warn_pct_free_below", 10))

        if not path:
            continue

        try:
            usage = shutil.disk_usage(path)
            free_pct = (usage.free / usage.total) * 100.0 if usage.total else 0.0

            status = "UP"
            msg = f"{free_pct:.1f}% free"
            if free_pct < warn_pct_free_below:
                status = "WARN"
                msg = f"Low disk: {free_pct:.1f}% free (< {warn_pct_free_below:.1f}%)"

            results.append(
                {
                    "name": f"disk:{path}",
                    "type": "disk",
                    "target": path,
                    "status": status,
                    "latency_ms": None,
                    "message": msg,
                }
            )
        except Exception as e:
            results.append(
                {
                    "name": f"disk:{path}",
                    "type": "disk",
                    "target": path,
                    "status": "WARN",
                    "latency_ms": None,
                    "message": f"{type(e).__name__}: {e}",
                }
            )

    return results

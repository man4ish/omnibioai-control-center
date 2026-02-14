from __future__ import annotations

from typing import Any

from control_center.checks.http import check_http
from control_center.checks.tcp import check_tcp


def run_all_checks(settings: Any) -> list[dict]:
    results: list[dict] = []

    for name, cfg in (settings.services or {}).items():
        ctype = (cfg.get("type") or "").lower()

        if ctype == "http":
            results.append(check_http(name=name, cfg=cfg))
        elif ctype == "mysql":
            results.append(check_tcp(name=name, host=cfg.get("host"), port=int(cfg.get("port", 3306)), kind="mysql"))
        elif ctype == "redis":
            results.append(check_tcp(name=name, host=cfg.get("host"), port=int(cfg.get("port", 6379)), kind="redis"))
        else:
            results.append(
                {
                    "name": name,
                    "type": ctype or "unknown",
                    "target": cfg.get("url") or f'{cfg.get("host")}:{cfg.get("port")}',
                    "status": "WARN",
                    "latency_ms": None,
                    "message": f"Unknown check type: {ctype!r}",
                }
            )

    return results

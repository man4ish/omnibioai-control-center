from __future__ import annotations

import os
import time
from typing import Any, Dict

import httpx
from fastapi import FastAPI

app = FastAPI(title="OmniBioAI Control Center", version="0.1.0")


def env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


# Defaults assume Control Center is running on HOST (not in Docker).
# Therefore, services must be reachable via 127.0.0.1 + published ports.
SERVICES: Dict[str, Dict[str, str]] = {
    "workbench": {
        "base": env("WORKBENCH_URL", "http://127.0.0.1:8001"),
        "health_path": env("WORKBENCH_HEALTH_PATH", "/health/"),
    },
    "tes": {
        "base": env("TES_URL", "http://127.0.0.1:8081"),
        "health_path": env("TES_HEALTH_PATH", "/health"),
    },
    "toolserver": {
        "base": env("TOOLSERVER_URL", "http://127.0.0.1:9090"),
        "health_path": env("TOOLSERVER_HEALTH_PATH", "/health"),
    },
    "model_registry": {
        "base": env("MODEL_REGISTRY_URL", "http://127.0.0.1:8095"),
        "health_path": env("MODEL_REGISTRY_HEALTH_PATH", "/health"),
    },
    "lims_x": {
        "base": env("LIMSX_URL", "http://127.0.0.1:7000"),
        "health_path": env("LIMSX_HEALTH_PATH", "/"),   # <-- change default
    },
}


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True, "service": "omnibioai-control-center"}


@app.get("/status")
async def status() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": True,
        "services": {},
    }

    async with httpx.AsyncClient(timeout=2.0, follow_redirects=True) as client:
        for name, cfg in SERVICES.items():
            base = cfg["base"].rstrip("/")
            health_path = cfg["health_path"]
            url = f"{base}{health_path}"

            t0 = time.perf_counter()
            try:
                r = await client.get(url)
                dt_ms = int((time.perf_counter() - t0) * 1000)

                out["services"][name] = {
                    "ok": r.status_code == 200,
                    "status_code": r.status_code,
                    "latency_ms": dt_ms,
                    "url": url,
                }
            except Exception as e:
                dt_ms = int((time.perf_counter() - t0) * 1000)
                out["services"][name] = {
                    "ok": False,
                    "status_code": None,
                    "latency_ms": dt_ms,
                    "url": url,
                    "error": str(e),
                }

    return out

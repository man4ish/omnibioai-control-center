from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

APP_NAME = "omnibioai-control-center"
APP_VERSION = os.getenv("CONTROL_CENTER_VERSION", "0.1.0")

# ---- timeouts ----
HTTP_TIMEOUT_SECONDS = float(os.getenv("CONTROL_CENTER_HTTP_TIMEOUT", "2.0"))
TOTAL_TIMEOUT_SECONDS = float(os.getenv("CONTROL_CENTER_TOTAL_TIMEOUT", "4.0"))

# ---- service URLs (inside compose network) ----
WORKBENCH_URL = os.getenv("WORKBENCH_URL", "http://omnibioai:8000")
TES_URL = os.getenv("TES_URL", "http://tes:8081")
TOOLSERVER_URL = os.getenv("TOOLSERVER_URL", "http://toolserver:9090")
MODEL_REGISTRY_URL = os.getenv("MODEL_REGISTRY_URL", "http://model-registry:8095")
LIMSX_URL = os.getenv("LIMSX_URL", "http://lims-x:7000")

# Optional: DB checks (network-level)
MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# ---- paths ----
WORKBENCH_HEALTH_PATH = os.getenv("WORKBENCH_HEALTH_PATH", "/")          # your Django root
TES_HEALTH_PATH = os.getenv("TES_HEALTH_PATH", "/health")               # FastAPI
TOOLSERVER_HEALTH_PATH = os.getenv("TOOLSERVER_HEALTH_PATH", "/health") # FastAPI
MODEL_REGISTRY_HEALTH_PATH = os.getenv("MODEL_REGISTRY_HEALTH_PATH", "/health")
LIMSX_HEALTH_PATH = os.getenv("LIMSX_HEALTH_PATH", "/")                  # Django root


@dataclass(frozen=True)
class ServiceCheck:
    name: str
    kind: str  # "http" or "tcp"
    target: str
    path: Optional[str] = None


def _now_ms() -> int:
    return int(time.time() * 1000)


async def _check_http(client: httpx.AsyncClient, name: str, base: str, path: str) -> Dict[str, Any]:
    url = base.rstrip("/") + path
    start = _now_ms()
    try:
        r = await client.get(url)
        latency_ms = _now_ms() - start
        ok = 200 <= r.status_code < 300
        # Try JSON if possible (don’t fail if not JSON)
        body: Any = None
        ctype = r.headers.get("content-type", "")
        if "application/json" in ctype:
            try:
                body = r.json()
            except Exception:
                body = None

        return {
            "name": name,
            "type": "http",
            "url": url,
            "ok": ok,
            "status_code": r.status_code,
            "latency_ms": latency_ms,
            "response": body,
            "error": None if ok else f"HTTP {r.status_code}",
        }
    except Exception as e:
        latency_ms = _now_ms() - start
        return {
            "name": name,
            "type": "http",
            "url": url,
            "ok": False,
            "status_code": None,
            "latency_ms": latency_ms,
            "response": None,
            "error": str(e),
        }


async def _check_tcp(name: str, host: str, port: int) -> Dict[str, Any]:
    import asyncio

    start = _now_ms()
    try:
        # Attempt TCP connect
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

        latency_ms = _now_ms() - start
        return {
            "name": name,
            "type": "tcp",
            "host": host,
            "port": port,
            "ok": True,
            "latency_ms": latency_ms,
            "error": None,
        }
    except Exception as e:
        latency_ms = _now_ms() - start
        return {
            "name": name,
            "type": "tcp",
            "host": host,
            "port": port,
            "ok": False,
            "latency_ms": latency_ms,
            "error": str(e),
        }


def _checks() -> List[ServiceCheck]:
    return [
        ServiceCheck("workbench", "http", WORKBENCH_URL, WORKBENCH_HEALTH_PATH),
        ServiceCheck("tes", "http", TES_URL, TES_HEALTH_PATH),
        ServiceCheck("toolserver", "http", TOOLSERVER_URL, TOOLSERVER_HEALTH_PATH),
        ServiceCheck("model-registry", "http", MODEL_REGISTRY_URL, MODEL_REGISTRY_HEALTH_PATH),
        ServiceCheck("lims-x", "http", LIMSX_URL, LIMSX_HEALTH_PATH),
        ServiceCheck("mysql", "tcp", f"{MYSQL_HOST}:{MYSQL_PORT}"),
        ServiceCheck("redis", "tcp", f"{REDIS_HOST}:{REDIS_PORT}"),
    ]


app = FastAPI(title="OmniBioAI Control Center", version=APP_VERSION)


@app.get("/health")
async def health() -> Dict[str, Any]:
    details = await _run_checks()
    ok = all(s["ok"] for s in details["services"])
    details["ok"] = ok
    return details


@app.get("/health/services")
async def health_services() -> Dict[str, Any]:
    details = await _run_checks()
    return {"ok": all(s["ok"] for s in details["services"]), "services": details["services"]}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> str:
    details = await _run_checks()
    services = details["services"]

    # Simple HTML (no external deps)
    rows = []
    for s in services:
        status = "OK" if s["ok"] else "DOWN"
        latency = f"{s.get('latency_ms', '-')}" if s.get("latency_ms") is not None else "-"
        target = s.get("url") or f"{s.get('host')}:{s.get('port')}"
        err = s.get("error") or ""
        rows.append(
            f"<tr>"
            f"<td>{s['name']}</td>"
            f"<td>{s['type']}</td>"
            f"<td><code>{target}</code></td>"
            f"<td>{status}</td>"
            f"<td>{latency}</td>"
            f"<td><code>{err}</code></td>"
            f"</tr>"
        )

    overall = "HEALTHY" if all(s["ok"] for s in services) else "DEGRADED"

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>OmniBioAI Control Center</title>
  <style>
    body {{ font-family: Arial, sans-serif; padding: 20px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; }}
    th {{ background: #f5f5f5; text-align: left; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
  </style>
</head>
<body>
  <h2>OmniBioAI Control Center</h2>
  <p><b>Overall:</b> {overall}</p>
  <p><b>Timestamp (UTC):</b> {details["timestamp_utc"]}</p>

  <table>
    <thead>
      <tr>
        <th>Service</th>
        <th>Type</th>
        <th>Target</th>
        <th>Status</th>
        <th>Latency (ms)</th>
        <th>Error</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>

  <p style="margin-top:12px;">
    JSON: <a href="/health">/health</a> | <a href="/health/services">/health/services</a>
  </p>
</body>
</html>
"""


async def _run_checks() -> Dict[str, Any]:
    import asyncio
    from datetime import datetime, timezone

    checks = _checks()

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        tasks = []
        for c in checks:
            if c.kind == "http":
                tasks.append(_check_http(client, c.name, c.target, c.path or "/health"))
            else:
                host, port_str = c.target.split(":")
                tasks.append(_check_tcp(c.name, host, int(port_str)))

        results: List[Dict[str, Any]] = await asyncio.wait_for(
            asyncio.gather(*tasks),
            timeout=TOTAL_TIMEOUT_SECONDS,
        )

    return {
        "ok": all(r["ok"] for r in results),
        "service": APP_NAME,
        "version": APP_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "services": results,
    }

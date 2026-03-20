"""
control_center/utils/summary_client.py

Fetches the /summary payload from a running Control Center instance.
Used by the report generator to populate the Health Status tab.
All I/O is synchronous (urllib only — no extra deps beyond stdlib).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ServiceHealth:
    name: str
    type: str
    target: str
    status: str          # "UP" | "DOWN" | "WARN"
    latency_ms: Optional[int]
    message: str


@dataclass
class DiskHealth:
    name: str
    target: str
    status: str
    message: str


@dataclass
class EcosystemHealth:
    overall_status: str              # "UP" | "DOWN" | "WARN"
    generated_at: str
    services: List[ServiceHealth] = field(default_factory=list)
    disk: List[DiskHealth] = field(default_factory=list)
    error: Optional[str] = None      # set when the API is unreachable


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_service(raw: Dict[str, Any]) -> ServiceHealth:
    return ServiceHealth(
        name=str(raw.get("name", "unknown")),
        type=str(raw.get("type", "unknown")),
        target=str(raw.get("target", "-")),
        status=str(raw.get("status", "DOWN")).upper(),
        latency_ms=raw.get("latency_ms"),
        message=str(raw.get("message", "")),
    )


def _parse_disk(raw: Dict[str, Any]) -> DiskHealth:
    return DiskHealth(
        name=str(raw.get("name", "disk")),
        target=str(raw.get("target", "-")),
        status=str(raw.get("status", "WARN")).upper(),
        message=str(raw.get("message", "")),
    )


def parse_summary(payload: Dict[str, Any]) -> EcosystemHealth:
    """
    Convert a raw /summary JSON dict into an EcosystemHealth dataclass.
    Safe against missing or malformed keys.
    """
    services = [_parse_service(s) for s in (payload.get("services") or [])]
    disk_raw = (payload.get("system") or {}).get("disk") or []
    disk = [_parse_disk(d) for d in disk_raw]

    return EcosystemHealth(
        overall_status=str(payload.get("overall_status", "WARN")).upper(),
        generated_at=str(payload.get("generated_at", "")),
        services=services,
        disk=disk,
    )


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def fetch_summary(
    base_url: str = "http://127.0.0.1:7070",
    timeout_s: float = 5.0,
) -> EcosystemHealth:
    """
    GET {base_url}/summary and return a parsed EcosystemHealth.

    If the control center is unreachable or returns an error, returns an
    EcosystemHealth with overall_status="UNREACHABLE" and error set —
    never raises so the report can still be generated.
    """
    url = base_url.rstrip("/") + "/summary"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "omnibioai-control-center-report/0.1"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        return parse_summary(raw)

    except urllib.error.URLError as e:
        return EcosystemHealth(
            overall_status="UNREACHABLE",
            generated_at="",
            error=f"URLError: {e.reason}",
        )
    except Exception as e:
        return EcosystemHealth(
            overall_status="UNREACHABLE",
            generated_at="",
            error=f"{type(e).__name__}: {e}",
        )
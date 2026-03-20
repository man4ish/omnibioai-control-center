# backend/src/control_center/main.py

from __future__ import annotations

import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from control_center.api.routes_health import router as health_router
from control_center.api.routes_report import router as report_router
from control_center.api.routes_services import router as services_router
from control_center.api.routes_summary import router as summary_router

app = FastAPI(
    title="OmniBioAI Control Center",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(services_router)
app.include_router(summary_router)
app.include_router(report_router)


# ==============================================================================
# Report generation — background job state
# ==============================================================================

class _JobState:
    """Thread-safe state for the background report generation job."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.status: str = "idle"       # idle | running | done | error
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None
        self.message: str = ""

    def start(self) -> None:
        with self._lock:
            self.status = "running"
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.finished_at = None
            self.message = ""

    def finish(self, message: str = "") -> None:
        with self._lock:
            self.status = "done"
            self.finished_at = datetime.now(timezone.utc).isoformat()
            self.message = message

    def fail(self, message: str) -> None:
        with self._lock:
            self.status = "error"
            self.finished_at = datetime.now(timezone.utc).isoformat()
            self.message = message

    def as_dict(self) -> dict:
        with self._lock:
            return {
                "status": self.status,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "message": self.message,
            }


_job = _JobState()


def _workspace_root() -> Path:
    return Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))


def _run_report_job() -> None:
    """
    Background thread: runs generate_report.py against WORKSPACE_ROOT.
    Updates _job state so the UI can poll /report/status.
    """
    workspace = _workspace_root()
    script = workspace / "omnibioai-control-center" / "scripts" / "generate_report.py"

    if not script.exists():
        _job.fail(f"Report script not found: {script}")
        return

    cmd = [
        "python3", str(script),
        "--root", str(workspace),
        "--control-center-url", f"http://127.0.0.1:{os.environ.get('CONTROL_CENTER_PORT', '7070')}",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,   # 10 min hard limit
        )
        if proc.returncode == 0:
            _job.finish(proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "Done")
        else:
            _job.fail(proc.stderr.strip() or proc.stdout.strip() or "Unknown error")
    except subprocess.TimeoutExpired:
        _job.fail("Report generation timed out after 10 minutes")
    except Exception as e:
        _job.fail(f"{type(e).__name__}: {e}")


@app.post("/report/generate")
def report_generate() -> JSONResponse:
    """Trigger background report generation. Returns 409 if already running."""
    if _job.as_dict()["status"] == "running":
        return JSONResponse({"error": "Report generation already in progress"}, status_code=409)
    _job.start()
    thread = threading.Thread(target=_run_report_job, daemon=True)
    thread.start()
    return JSONResponse({"status": "started"})


@app.get("/report/status")
def report_status() -> JSONResponse:
    """Poll job state. Frontend polls this every 2s while running."""
    state = _job.as_dict()
    # Also tell the frontend if the report file actually exists
    report_path = _workspace_root() / "out" / "reports" / "omnibioai_ecosystem_report.html"
    state["report_exists"] = report_path.exists()
    if report_path.exists():
        mtime = datetime.fromtimestamp(report_path.stat().st_mtime, tz=timezone.utc)
        state["report_generated_at"] = mtime.isoformat()
    else:
        state["report_generated_at"] = None
    return JSONResponse(state)


# ==============================================================================
# Dashboard UI
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    """
    Live health dashboard with:
    - Overall status banner
    - Per-service health cards (auto-refresh every 10s)
    - Generate Report button (triggers background job, polls /report/status)
    - View Report button (links to /report once generated)
    """
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OmniBioAI Control Center</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'IBM Plex Sans', ui-sans-serif, system-ui, Arial, sans-serif;
      background: #F1F5F9; color: #111827;
      padding: 28px 24px 48px;
    }
    .wrap { max-width: 1200px; margin: 0 auto; }

    /* Header */
    .header { margin-bottom: 20px; }
    .header h1 { font-size: 20px; font-weight: 700; color: #0F172A; margin-bottom: 3px; }
    .header .sub { font-size: 12px; color: #9CA3AF; }

    /* Top bar */
    .topbar {
      display: flex; align-items: center; gap: 10px;
      margin-bottom: 18px; flex-wrap: wrap;
    }
    .btn {
      border: 1px solid #E5E7EB; border-radius: 8px;
      padding: 8px 16px; background: white; cursor: pointer;
      font-size: 13px; font-weight: 600; color: #374151;
      font-family: inherit; text-decoration: none;
      display: inline-flex; align-items: center; gap: 6px;
    }
    .btn:hover { background: #F8FAFC; }
    .btn-primary { background: #0F172A; color: white; border-color: #0F172A; }
    .btn-primary:hover { background: #1E293B; }
    .btn-primary:disabled {
      background: #94A3B8; border-color: #94A3B8;
      cursor: not-allowed; opacity: .7;
    }
    .btn-green { background: #ECFDF5; color: #065F46; border-color: #6EE7B7; }
    .btn-green:hover { background: #D1FAE5; }
    .last-checked { font-size: 12px; color: #9CA3AF; margin-left: auto; }

    /* Report panel */
    .report-panel {
      background: white; border: 1px solid #E5E7EB;
      border-radius: 12px; padding: 16px 20px;
      margin-bottom: 18px;
      display: flex; align-items: center;
      justify-content: space-between; flex-wrap: wrap; gap: 12px;
    }
    .report-info { flex: 1; min-width: 200px; }
    .report-title { font-size: 13px; font-weight: 600; color: #111827; margin-bottom: 3px; }
    .report-sub { font-size: 11px; color: #9CA3AF; }
    .report-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .spinner {
      width: 14px; height: 14px;
      border: 2px solid #E5E7EB;
      border-top-color: #374151;
      border-radius: 50%;
      animation: spin .8s linear infinite;
      display: inline-block; flex-shrink: 0;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .progress-msg { font-size: 11px; color: #6B7280; }

    /* Banner */
    .banner {
      border-radius: 12px; padding: 14px 18px;
      margin-bottom: 18px;
      display: flex; align-items: center; gap: 12px;
      border: 1px solid transparent;
    }
    .banner-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
    .banner-title { font-size: 14px; font-weight: 600; }
    .banner-sub { font-size: 11px; margin-top: 2px; }
    .banner-up   { background: #ECFDF5; border-color: #6EE7B733; }
    .banner-down { background: #FEF2F2; border-color: #FCA5A533; }
    .banner-warn { background: #FFFBEB; border-color: #FCD34D33; }

    /* Section label */
    .section-label {
      font-size: 11px; font-weight: 600; color: #9CA3AF;
      text-transform: uppercase; letter-spacing: .06em;
      margin-bottom: 12px;
    }

    /* Cards */
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 12px; margin-bottom: 24px;
    }
    .card {
      background: white; border-radius: 12px;
      padding: 16px; border: 1px solid #E5E7EB;
    }
    .card-header {
      display: flex; justify-content: space-between;
      align-items: flex-start; margin-bottom: 10px;
    }
    .card-name { font-size: 13px; font-weight: 600; color: #111827; }
    .badge {
      padding: 3px 10px; border-radius: 99px;
      font-size: 11px; font-weight: 600;
    }
    .badge-up   { background: #EAF3DE; color: #3B6D11; }
    .badge-down { background: #FCEBEB; color: #A32D2D; }
    .badge-warn { background: #FAEEDA; color: #854F0B; }
    .kv {
      display: grid; grid-template-columns: auto 1fr;
      gap: 3px 10px; font-size: 11px; color: #6B7280;
    }
    .kv-label { color: #9CA3AF; white-space: nowrap; }
    .kv-val { word-break: break-all; }

    /* Raw JSON */
    .raw-toggle {
      font-size: 12px; color: #9CA3AF; cursor: pointer;
      background: none; border: none; padding: 0;
      text-decoration: underline; margin-bottom: 8px;
    }
    pre {
      background: #F8FAFC; border: 1px solid #E5E7EB;
      border-radius: 10px; padding: 14px;
      overflow: auto; font-size: 11px; color: #374151;
      display: none;
    }
  </style>
</head>
<body>
<div class="wrap">

  <div class="header">
    <h1>OmniBioAI Control Center</h1>
    <div class="sub">Stateless health dashboard · auto-refreshes every 10 s</div>
  </div>

  <!-- Report panel -->
  <div class="report-panel">
    <div class="report-info">
      <div class="report-title">Ecosystem Report</div>
      <div class="report-sub" id="report-sub">Architecture · Projects · Languages · Coverage · Health</div>
    </div>
    <div class="report-actions">
      <span id="report-spinner" style="display:none;" class="spinner"></span>
      <span id="report-progress" class="progress-msg" style="display:none;"></span>
      <button class="btn btn-primary" id="btn-generate" onclick="generateReport()">
        Generate Report
      </button>
      <a class="btn btn-green" id="btn-view" href="/report" target="_blank"
         style="display:none;">
        View Report ↗
      </a>
    </div>
  </div>

  <!-- Health banner -->
  <div id="banner" class="banner" style="display:none;"></div>

  <!-- Top bar -->
  <div class="topbar">
    <button class="btn" onclick="loadHealth()">Refresh</button>
    <span class="last-checked" id="last"></span>
  </div>

  <div class="section-label">Services</div>
  <div class="grid" id="cards"></div>

  <button class="raw-toggle" onclick="toggleRaw()">Show raw JSON</button>
  <pre id="raw"></pre>

</div>

<script>
  var rawVisible = false;
  var pollTimer = null;

  function toggleRaw() {
    rawVisible = !rawVisible;
    document.getElementById('raw').style.display = rawVisible ? 'block' : 'none';
    document.querySelector('.raw-toggle').textContent =
      rawVisible ? 'Hide raw JSON' : 'Show raw JSON';
  }

  function esc(s) {
    return String(s)
      .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  }

  function badgeClass(status) {
    if (status === 'UP')   return 'badge badge-up';
    if (status === 'WARN') return 'badge badge-warn';
    return 'badge badge-down';
  }

  function setBanner(overall) {
    var el = document.getElementById('banner');
    var configs = {
      'UP':   ['banner-up',   '#10B981', 'All systems operational'],
      'DOWN': ['banner-down', '#EF4444', 'One or more services are down'],
      'WARN': ['banner-warn', '#F59E0B', 'One or more services need attention'],
    };
    var cfg = configs[overall] || ['banner-warn', '#F59E0B', overall];
    el.className = 'banner ' + cfg[0];
    el.style.display = 'flex';
    el.innerHTML =
      '<div class="banner-dot" style="background:' + cfg[1] + '"></div>' +
      '<div>' +
        '<div class="banner-title">' + esc(cfg[2]) + '</div>' +
        '<div class="banner-sub" style="color:' + cfg[1] + '">Overall: ' + esc(overall) + '</div>' +
      '</div>';
  }

  async function loadHealth() {
    try {
      var res = await fetch('/summary');
      var data = await res.json();
      document.getElementById('last').textContent =
        'Last checked: ' + (data.generated_at || '(unknown)');
      document.getElementById('raw').textContent = JSON.stringify(data, null, 2);
      setBanner(data.overall_status || 'WARN');
      var cards = document.getElementById('cards');
      cards.innerHTML = '';
      for (var i = 0; i < (data.services || []).length; i++) {
        var s = data.services[i];
        var latency = s.latency_ms != null ? s.latency_ms + ' ms' : '—';
        var border = s.status === 'UP' ? '#D1FAE5'
                   : s.status === 'DOWN' ? '#FEE2E2' : '#FEF3C7';
        var el = document.createElement('div');
        el.className = 'card';
        el.style.borderColor = border;
        el.innerHTML =
          '<div class="card-header">' +
            '<div class="card-name">' + esc(s.name) + '</div>' +
            '<span class="' + badgeClass(s.status) + '">' + esc(s.status) + '</span>' +
          '</div>' +
          '<div class="kv">' +
            '<span class="kv-label">Type</span><span class="kv-val">' + esc(s.type||'—') + '</span>' +
            '<span class="kv-label">Target</span><span class="kv-val">' + esc(s.target||'—') + '</span>' +
            '<span class="kv-label">Latency</span><span class="kv-val">' + esc(latency) + '</span>' +
            '<span class="kv-label">Message</span><span class="kv-val">' + esc(s.message||'—') + '</span>' +
          '</div>';
        cards.appendChild(el);
      }
    } catch(e) {
      var banner = document.getElementById('banner');
      banner.className = 'banner banner-down';
      banner.style.display = 'flex';
      banner.innerHTML =
        '<div class="banner-dot" style="background:#EF4444"></div>' +
        '<div><div class="banner-title">Could not reach /summary</div>' +
        '<div class="banner-sub" style="color:#EF4444">' + esc(String(e)) + '</div></div>';
    }
  }

  // ── Report generation ──────────────────────────────────────────────────────

  function setReportUI(state) {
    var btnGen  = document.getElementById('btn-generate');
    var btnView = document.getElementById('btn-view');
    var spinner = document.getElementById('report-spinner');
    var progress= document.getElementById('report-progress');
    var sub     = document.getElementById('report-sub');

    if (state.status === 'running') {
      btnGen.disabled = true;
      spinner.style.display = 'inline-block';
      progress.style.display = 'inline';
      progress.textContent = 'Generating… this takes 2–5 minutes';
      btnView.style.display = 'none';
    } else if (state.status === 'done') {
      btnGen.disabled = false;
      spinner.style.display = 'none';
      progress.style.display = 'none';
      if (state.report_generated_at) {
        sub.textContent = 'Last generated: ' + new Date(state.report_generated_at).toLocaleString();
      }
      if (state.report_exists) {
        btnView.style.display = 'inline-flex';
      }
    } else if (state.status === 'error') {
      btnGen.disabled = false;
      spinner.style.display = 'none';
      progress.style.display = 'inline';
      progress.textContent = 'Error: ' + (state.message || 'unknown');
      progress.style.color = '#A32D2D';
    } else {
      // idle
      btnGen.disabled = false;
      spinner.style.display = 'none';
      progress.style.display = 'none';
      if (state.report_exists && state.report_generated_at) {
        sub.textContent = 'Last generated: ' + new Date(state.report_generated_at).toLocaleString();
        btnView.style.display = 'inline-flex';
      }
    }
  }

  async function pollReportStatus() {
    try {
      var res = await fetch('/report/status');
      var state = await res.json();
      setReportUI(state);
      if (state.status === 'running') {
        pollTimer = setTimeout(pollReportStatus, 2000);
      } else {
        pollTimer = null;
      }
    } catch(e) {
      pollTimer = null;
    }
  }

  async function generateReport() {
    try {
      var res = await fetch('/report/generate', { method: 'POST' });
      if (res.status === 409) {
        return; // already running
      }
      setReportUI({ status: 'running' });
      pollTimer = setTimeout(pollReportStatus, 2000);
    } catch(e) {
      console.error('Failed to start report generation:', e);
    }
  }

  // ── Boot ───────────────────────────────────────────────────────────────────
  loadHealth();
  setInterval(loadHealth, 10000);
  pollReportStatus(); // check initial state on load
</script>
</body>
</html>
"""
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
def dashboard() -> str:  # pragma: no cover
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'IBM Plex Sans', Arial, sans-serif;
      background: #F1F5F9; color: #111827;
      padding: 32px 28px 48px;
    }
    .wrap { max-width: 1320px; margin: 0 auto; }

    /* ── Page header ── */
    .page-header { margin-bottom: 6px; }
    .page-title { font-size: 20px; font-weight: 700; color: #0F172A; }
    .page-sub { font-size: 12px; color: #9CA3AF; margin-bottom: 24px; }

    /* ── KPI strip ── */
    .kpi-strip {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px; margin-bottom: 20px;
    }
    .kpi-card {
      background: white; border: 1px solid #E5E7EB;
      border-radius: 12px; padding: 16px 18px 14px;
      position: relative; overflow: hidden;
    }
    .kpi-card::before {
      content: ''; position: absolute;
      top: 0; left: 0; right: 0; height: 3px;
      border-radius: 12px 12px 0 0;
    }
    .kpi-card.c-gray::before  { background: #D1D5DB; }
    .kpi-card.c-green::before { background: #639922; }
    .kpi-card.c-red::before   { background: #E24B4A; }
    .kpi-card.c-amber::before { background: #BA7517; }
    .kpi-card.c-blue::before  { background: #378ADD; }
    .kpi-label { font-size: 11px; color: #9CA3AF; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 8px; }
    .kpi-value { font-size: 26px; font-weight: 700; color: #0F172A; line-height: 1; margin-bottom: 4px; }
    .kpi-sub   { font-size: 11px; color: #9CA3AF; }

    /* ── Report panel ── */
    .report-panel {
      background: white; border: 1px solid #E5E7EB;
      border-radius: 12px; padding: 18px 20px;
      margin-bottom: 16px;
      display: flex; align-items: center;
      justify-content: space-between; flex-wrap: wrap; gap: 14px;
    }
    .report-left { display: flex; align-items: center; gap: 14px; }
    .report-icon {
      width: 38px; height: 38px; border-radius: 10px;
      background: #F1F5F9; border: 1px solid #E5E7EB;
      display: flex; align-items: center; justify-content: center;
      font-size: 18px; flex-shrink: 0;
    }
    .report-title { font-size: 13px; font-weight: 600; color: #111827; margin-bottom: 3px; }
    .report-sub   { font-size: 11px; color: #9CA3AF; }
    .report-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .spinner {
      width: 14px; height: 14px;
      border: 2px solid #E5E7EB; border-top-color: #374151;
      border-radius: 50%; animation: spin .8s linear infinite;
      display: inline-block; flex-shrink: 0;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .progress-msg { font-size: 11px; color: #6B7280; }

    /* ── Buttons ── */
    .btn {
      border: 1px solid #E5E7EB; border-radius: 8px;
      padding: 8px 16px; background: white; cursor: pointer;
      font-size: 13px; font-weight: 600; color: #374151;
      font-family: inherit; text-decoration: none;
      display: inline-flex; align-items: center; gap: 6px;
      transition: background .12s;
    }
    .btn:hover { background: #F8FAFC; }
    .btn-dark { background: #0F172A; color: white; border-color: #0F172A; }
    .btn-dark:hover { background: #1E293B; }
    .btn-dark:disabled { background: #94A3B8; border-color: #94A3B8; cursor: not-allowed; }
    .btn-green { background: #ECFDF5; color: #065F46; border-color: #A7F3D0; }
    .btn-green:hover { background: #D1FAE5; }

    /* ── Banner ── */
    .banner {
      border-radius: 12px; padding: 14px 18px; margin-bottom: 20px;
      display: flex; align-items: center; gap: 12px;
      border: 1px solid transparent;
    }
    .banner-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
    .banner-title { font-size: 14px; font-weight: 600; }
    .banner-sub   { font-size: 11px; margin-top: 2px; }
    .banner-up   { background: #ECFDF5; border-color: #6EE7B733; }
    .banner-down { background: #FEF2F2; border-color: #FCA5A533; }
    .banner-warn { background: #FFFBEB; border-color: #FCD34D33; }

    /* ── Top bar ── */
    .topbar {
      display: flex; align-items: center; gap: 10px;
      margin-bottom: 16px; flex-wrap: wrap;
    }
    .section-label {
      font-size: 11px; font-weight: 600; color: #9CA3AF;
      text-transform: uppercase; letter-spacing: .08em; margin-bottom: 12px;
    }
    .last-checked { font-size: 12px; color: #9CA3AF; margin-left: auto; }

    /* ── Service grid ── */
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 12px; margin-bottom: 24px;
    }
    .card {
      background: white; border-radius: 12px;
      padding: 16px; border: 1px solid #E5E7EB;
      transition: box-shadow .15s;
    }
    .card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
    .card-header {
      display: flex; justify-content: space-between;
      align-items: flex-start; margin-bottom: 12px;
    }
    .card-name-row { display: flex; align-items: center; gap: 8px; }
    .card-name { font-size: 13px; font-weight: 600; color: #111827; }
    .badge {
      padding: 3px 10px; border-radius: 99px;
      font-size: 11px; font-weight: 600;
    }
    .badge-up   { background: #EAF3DE; color: #3B6D11; }
    .badge-down { background: #FCEBEB; color: #A32D2D; }
    .badge-warn { background: #FAEEDA; color: #854F0B; }
    .ui-link {
      font-size: 11px; color: #378ADD; text-decoration: none;
      font-weight: 600; padding: 2px 8px;
      border: 1px solid #B5D4F4; border-radius: 6px;
      background: #E6F1FB; white-space: nowrap;
    }
    .ui-link:hover { background: #B5D4F4; }
    .kv {
      display: grid; grid-template-columns: 72px 1fr;
      gap: 4px 8px; font-size: 11px;
    }
    .kv-k { color: #9CA3AF; }
    .kv-v { color: #374151; word-break: break-all; }

    /* ── Disk section ── */
    .disk-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 12px; margin-bottom: 24px;
    }
    .disk-card {
      background: white; border-radius: 12px;
      padding: 14px 16px; border: 1px solid #E5E7EB;
    }
    .disk-header {
      display: flex; justify-content: space-between;
      align-items: center; margin-bottom: 8px;
    }
    .disk-name { font-size: 12px; font-weight: 600; color: #111827; }
    .disk-path { font-size: 11px; color: #9CA3AF; margin-bottom: 6px; }
    .disk-bar-track {
      height: 5px; background: #E5E7EB;
      border-radius: 99px; overflow: hidden; margin-bottom: 5px;
    }
    .disk-bar-fill { height: 100%; border-radius: 99px; }
    .disk-msg { font-size: 11px; color: #6B7280; }

    /* ── Raw JSON ── */
    .raw-toggle {
      font-size: 12px; color: #9CA3AF; cursor: pointer;
      background: none; border: none; padding: 0;
      text-decoration: underline; margin-bottom: 8px;
      font-family: inherit;
    }
    pre {
      background: #F8FAFC; border: 1px solid #E5E7EB;
      border-radius: 10px; padding: 14px;
      overflow: auto; font-size: 11px; color: #374151;
      display: none; line-height: 1.6;
    }

    /* ── Footer ── */
    .footer {
      margin-top: 32px; padding-top: 16px;
      border-top: 1px solid #E5E7EB;
      font-size: 11px; color: #9CA3AF; line-height: 1.8;
    }
  </style>
</head>
<body>
<div class="wrap">

  <div class="page-header">
    <div class="page-title">OmniBioAI Control Center</div>
  </div>
  <div class="page-sub">Stateless health dashboard &middot; auto-refreshes every 10 s</div>

  <!-- KPI strip -->
  <div class="kpi-strip" id="kpi-strip">
    <div class="kpi-card c-gray"><div class="kpi-label">Services</div><div class="kpi-value" id="kpi-total">—</div><div class="kpi-sub">monitored</div></div>
    <div class="kpi-card c-green"><div class="kpi-label">Healthy</div><div class="kpi-value" id="kpi-up">—</div><div class="kpi-sub">UP</div></div>
    <div class="kpi-card c-red"><div class="kpi-label">Down</div><div class="kpi-value" id="kpi-down">—</div><div class="kpi-sub">need attention</div></div>
    <div class="kpi-card c-amber"><div class="kpi-label">Degraded</div><div class="kpi-value" id="kpi-warn">—</div><div class="kpi-sub">WARN</div></div>
    <div class="kpi-card c-blue"><div class="kpi-label">Disk warnings</div><div class="kpi-value" id="kpi-disk">—</div><div class="kpi-sub">paths checked</div></div>
  </div>

  <!-- Report panel -->
  <div class="report-panel">
    <div class="report-left">
      <div class="report-icon">&#128196;</div>
      <div>
        <div class="report-title">Ecosystem Report</div>
        <div class="report-sub" id="report-sub">Architecture &middot; Projects &middot; Languages &middot; Coverage &middot; Health</div>
      </div>
    </div>
    <div class="report-actions">
      <span id="report-spinner" style="display:none;" class="spinner"></span>
      <span id="report-progress" class="progress-msg" style="display:none;"></span>
      <button class="btn btn-dark" id="btn-generate" onclick="generateReport()">Generate Report</button>
      <a class="btn btn-green" id="btn-view" href="/report" target="_blank" style="display:none;">View Report ↗</a>
    </div>
  </div>

  <!-- Health banner -->
  <div id="banner" class="banner" style="display:none;"></div>

  <!-- Top bar -->
  <div class="topbar">
    <button class="btn" onclick="loadHealth()">&#8635; Refresh</button>
    <span class="last-checked" id="last"></span>
  </div>

  <div class="section-label">Services</div>
  <div class="grid" id="cards"></div>

  <div class="section-label" id="disk-label" style="display:none;">Disk checks</div>
  <div class="disk-grid" id="disk-cards"></div>

  <button class="raw-toggle" onclick="toggleRaw()">Show raw JSON</button>
  <pre id="raw"></pre>

  <div class="footer">
    Health checks run on every refresh and auto-refresh every 10 s.<br>
    Disk thresholds and service endpoints are configured in <code>control_center.yaml</code>.
  </div>

</div>
<script>
  var rawVisible = false;
  var pollTimer = null;

  function toggleRaw() {
    rawVisible = !rawVisible;
    document.getElementById('raw').style.display = rawVisible ? 'block' : 'none';
    document.querySelector('.raw-toggle').textContent = rawVisible ? 'Hide raw JSON' : 'Show raw JSON';
  }

  function esc(s) {
    return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  }

  function badgeClass(status) {
    if (status === 'UP')   return 'badge badge-up';
    if (status === 'WARN') return 'badge badge-warn';
    return 'badge badge-down';
  }

  function cardBorder(status) {
    if (status === 'UP')   return '#D1FAE5';
    if (status === 'DOWN') return '#FEE2E2';
    return '#FEF3C7';
  }

  function setBanner(overall) {
    var el = document.getElementById('banner');
    var cfg = {
      'UP':   ['banner-up',   '#10B981', 'All systems operational',        'Overall: UP'],
      'DOWN': ['banner-down', '#EF4444', 'One or more services are down',  'Overall: DOWN'],
      'WARN': ['banner-warn', '#F59E0B', 'One or more services need attention', 'Overall: WARN'],
    }[overall] || ['banner-warn', '#F59E0B', overall, ''];
    el.className = 'banner ' + cfg[0];
    el.style.display = 'flex';
    el.innerHTML =
      '<div class="banner-dot" style="background:' + cfg[1] + '"></div>' +
      '<div><div class="banner-title">' + esc(cfg[2]) + '</div>' +
      '<div class="banner-sub" style="color:' + cfg[1] + '">' + esc(cfg[3]) + '</div></div>';
  }

  function renderKpis(services, disk) {
    var up   = services.filter(function(s){ return s.status==='UP'; }).length;
    var down = services.filter(function(s){ return s.status==='DOWN'; }).length;
    var warn = services.filter(function(s){ return s.status==='WARN'; }).length;
    var dw   = (disk||[]).filter(function(d){ return d.status!=='UP'; }).length;
    document.getElementById('kpi-total').textContent = services.length;
    document.getElementById('kpi-up').textContent    = up;
    document.getElementById('kpi-down').textContent  = down;
    document.getElementById('kpi-warn').textContent  = warn;
    document.getElementById('kpi-disk').textContent  = dw;
  }

  function renderServices(services) {
    var cards = document.getElementById('cards');
    cards.innerHTML = '';
    for (var i = 0; i < services.length; i++) {
      var s = services[i];
      var latency = s.latency_ms != null ? s.latency_ms + ' ms' : '—';
      var uiLink = s.ui_url
        ? '<a class="ui-link" href="' + esc(s.ui_url) + '" target="_blank">Open UI ↗</a>'
        : '';
      var el = document.createElement('div');
      el.className = 'card';
      el.style.borderColor = cardBorder(s.status);
      el.innerHTML =
        '<div class="card-header">' +
          '<div class="card-name-row">' +
            '<div class="card-name">' + esc(s.name) + '</div>' + uiLink +
          '</div>' +
          '<span class="' + badgeClass(s.status) + '">' + esc(s.status) + '</span>' +
        '</div>' +
        '<div class="kv">' +
          '<span class="kv-k">Type</span><span class="kv-v">' + esc(s.type||'—') + '</span>' +
          '<span class="kv-k">Target</span><span class="kv-v">' + esc(s.target||'—') + '</span>' +
          '<span class="kv-k">Latency</span><span class="kv-v">' + esc(latency) + '</span>' +
          '<span class="kv-k">Message</span><span class="kv-v">' + esc(s.message||'—') + '</span>' +
        '</div>';
      cards.appendChild(el);
    }
  }

  function renderDisk(disk) {
    var label = document.getElementById('disk-label');
    var grid  = document.getElementById('disk-cards');
    if (!disk || !disk.length) { label.style.display = 'none'; grid.innerHTML = ''; return; }
    label.style.display = 'block';
    grid.innerHTML = '';
    for (var i = 0; i < disk.length; i++) {
      var d = disk[i];
      var pctMatch = d.message ? d.message.match(/([0-9.]+)%/) : null;
      var pct = pctMatch ? parseFloat(pctMatch[1]) : null;
      var fillColor = d.status === 'UP' ? '#639922' : d.status === 'WARN' ? '#BA7517' : '#E24B4A';
      var border = d.status === 'UP' ? '#D1FAE5' : d.status === 'WARN' ? '#FEF3C7' : '#FEE2E2';
      var barHtml = pct !== null
        ? '<div class="disk-bar-track"><div class="disk-bar-fill" style="width:' + pct.toFixed(1) + '%;background:' + fillColor + ';"></div></div>'
        : '';
      var el = document.createElement('div');
      el.className = 'disk-card';
      el.style.borderColor = border;
      el.innerHTML =
        '<div class="disk-header">' +
          '<div class="disk-name">' + esc(d.name.replace('disk:','')) + '</div>' +
          '<span class="' + badgeClass(d.status) + '">' + esc(d.status) + '</span>' +
        '</div>' +
        '<div class="disk-path">' + esc(d.target||'') + '</div>' +
        barHtml +
        '<div class="disk-msg">' + esc(d.message||'—') + '</div>';
      grid.appendChild(el);
    }
  }

  async function loadHealth() {
    try {
      var res  = await fetch('/summary');
      var data = await res.json();
      document.getElementById('last').textContent = 'Last checked: ' + (data.generated_at||'').replace('T',' ').substring(0,19) + ' UTC';
      document.getElementById('raw').textContent  = JSON.stringify(data, null, 2);
      setBanner(data.overall_status || 'WARN');
      var svcs = data.services || [];
      var disk = (data.system||{}).disk || [];
      renderKpis(svcs, disk);
      renderServices(svcs);
      renderDisk(disk);
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

  function setReportUI(state) {
    var btnGen   = document.getElementById('btn-generate');
    var btnView  = document.getElementById('btn-view');
    var spinner  = document.getElementById('report-spinner');
    var progress = document.getElementById('report-progress');
    var sub      = document.getElementById('report-sub');
    if (state.status === 'running') {
      btnGen.disabled = true;
      spinner.style.display = 'inline-block';
      progress.style.display = 'inline';
      progress.textContent = 'Generating\u2026 this takes 2\u20135 minutes';
      btnView.style.display = 'none';
    } else if (state.status === 'done') {
      btnGen.disabled = false;
      spinner.style.display = 'none';
      progress.style.display = 'none';
      if (state.report_generated_at) {
        sub.textContent = 'Last generated: ' + new Date(state.report_generated_at).toLocaleString();
      }
      if (state.report_exists) btnView.style.display = 'inline-flex';
    } else if (state.status === 'error') {
      btnGen.disabled = false;
      spinner.style.display = 'none';
      progress.style.display = 'inline';
      progress.textContent = 'Error: ' + (state.message||'unknown');
      progress.style.color = '#A32D2D';
    } else {
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
      var res   = await fetch('/report/status');
      var state = await res.json();
      setReportUI(state);
      pollTimer = state.status === 'running' ? setTimeout(pollReportStatus, 2000) : null;
    } catch(e) { pollTimer = null; }
  }

  async function generateReport() {
    try {
      var res = await fetch('/report/generate', { method: 'POST' });
      if (res.status === 409) return;
      setReportUI({ status: 'running' });
      pollTimer = setTimeout(pollReportStatus, 2000);
    } catch(e) { console.error(e); }
  }

  loadHealth();
  setInterval(loadHealth, 10000);
  pollReportStatus();
</script>
</body>
</html>
"""
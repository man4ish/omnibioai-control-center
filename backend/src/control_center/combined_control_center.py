

===== FILE: main.py =====

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


def _reset_job_to_idle(delay_s: int = 5) -> None:
    """Reset job status to idle after a short delay so reloaded pages see 'idle'."""
    import time as _time
    _time.sleep(delay_s)
    with _job._lock:
        if _job.status in ("done", "error"):
            _job.status = "idle"


def _run_report_job() -> None:
    workspace = _workspace_root()
    script = workspace / "omnibioai-control-center" / "scripts" / "generate_report.py"

    if not script.exists():
        _job.fail(f"Report script not found: {script}")
        threading.Thread(target=_reset_job_to_idle, daemon=True).start()
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
            timeout=600,
        )
        if proc.returncode == 0:
            _job.finish(proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "Done")
        else:
            _job.fail(proc.stderr.strip() or proc.stdout.strip() or "Unknown error")
    except subprocess.TimeoutExpired:
        _job.fail("Report generation timed out after 10 minutes")
    except Exception as e:
        _job.fail(f"{type(e).__name__}: {e}")

    # Reset to idle after 30s so subsequent page loads don't see 'done'
    # and trigger another reload loop.
    threading.Thread(target=_reset_job_to_idle, daemon=True).start()


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
def root() -> HTMLResponse:
    report_path = _workspace_root() / "out" / "reports" / "omnibioai_ecosystem_report.html"

    if report_path.exists():
        report_html = report_path.read_text(encoding="utf-8")
        port = os.environ.get("CONTROL_CENTER_PORT", "7070")
        sticky_bar = f"""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  @keyframes omni-spin {{ to {{ transform:rotate(360deg); }} }}
  body {{ padding-top: 62px !important; }}
  #omni-header {{
    position:fixed;top:0;left:0;right:0;z-index:9999;
    display:flex;align-items:center;justify-content:space-between;
    padding:10px 28px;
    background:white;
    box-shadow:0 2px 8px rgba(0,0,0,.1);
    font-family:'Inter','Segoe UI',system-ui,sans-serif;
    gap:12px;
  }}
  #omni-header .logo {{ display:flex;align-items:center;gap:10px; }}
  #omni-header .logo-text {{ font-size:18px;font-weight:700;color:#2563eb;letter-spacing:-.01em; }}
  #omni-header .logo-text span {{ font-weight:400; }}
  #omni-header .logo-sub {{ font-size:11px;color:#9ca3af;margin-top:1px; }}
  #omni-header .hdr-right {{ display:flex;align-items:center;gap:10px;flex-wrap:wrap; }}
  #omni-header .status-chip {{ font-size:12px;font-weight:600;padding:5px 13px;border-radius:99px;display:inline-flex;align-items:center;gap:6px; }}
  #omni-header .chip-green {{ background:#ecfdf5;color:#059669;border:1px solid #a7f3d0; }}
  #omni-header .chip-amber {{ background:#fffbeb;color:#d97706;border:1px solid #fde68a; }}
  #omni-header .chip-red {{ background:#fef2f2;color:#dc2626;border:1px solid #fecaca; }}
  #omni-header .chip-dot {{ width:7px;height:7px;border-radius:50%;background:#10b981; }}
  #omni-header .hdr-btn {{ font-size:13px;font-weight:600;padding:7px 15px;border-radius:8px;cursor:pointer;border:1px solid;display:inline-flex;align-items:center;gap:6px;font-family:inherit;text-decoration:none;transition:opacity .12s; }}
  #omni-header .hdr-btn:hover {{ opacity:.88; }}
  #omni-header .btn-outline {{ background:white;border-color:#d1d5db;color:#374151; }}
  #omni-header .btn-primary {{ background:#2563eb;border-color:#2563eb;color:white; }}
  #omni-header .btn-primary:disabled {{ background:#93c5fd;border-color:#93c5fd;cursor:not-allowed; }}
  #omni-spin {{ width:14px;height:14px;border:2px solid #e5e7eb;border-top-color:#2563eb;border-radius:50%;animation:omni-spin .8s linear infinite;display:none; }}
</style>
<header id="omni-header">
  <div class="logo">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 34" width="36" height="36">
      <polygon points="16,2 28,8 28,22 16,28 4,22 4,8" fill="none" stroke="#2563eb" stroke-width="1.8"/>
      <path d="M11 9 C16 13,14 17,20 20 M20 9 C15 13,17 17,11 20" stroke="#2563eb" stroke-width="1.6" fill="none" stroke-linecap="round"/>
      <circle cx="16" cy="15" r="2.2" fill="#2563eb"/>
    </svg>
    <div>
      <div class="logo-text">Omni<span>BioAI</span></div>
      <div class="logo-sub">Ecosystem Report</div>
    </div>
  </div>
  <div class="hdr-right">
    <div class="status-chip chip-green" id="omni-svc-badge" style="display:none;"></div>
    <span id="omni-rpt-ts" style="font-size:11px;color:#9ca3af;"></span>
    <span id="omni-spin"></span>
    <span id="omni-prog" style="font-size:11px;color:#6b7280;display:none;"></span>
    <button id="omni-btn-regen" onclick="omniGenerate()" class="hdr-btn btn-primary">&#8635; Regenerate</button>
    <a href="/dashboard" class="hdr-btn btn-outline">&#9881; Dashboard</a>
  </div>
</header>
<script>
(function() {{
  // ── Reload-loop prevention ────────────────────────────────────────────────
  // We use sessionStorage so the "we already reloaded once" signal survives
  // the page reload itself.  The flag is written immediately before calling
  // window.location.reload() and consumed (and deleted) on the very next
  // page load, so a second load never triggers another reload.
  var RELOAD_KEY = 'omni_gen_reloaded';
  var _justReloaded = sessionStorage.getItem(RELOAD_KEY) === '1';
  if (_justReloaded) {{ sessionStorage.removeItem(RELOAD_KEY); }}

  // _omniWasGenerating is still needed so we know the *current* page
  // triggered the generation (vs. arriving on a page where status happens
  // to be 'done' from an earlier run).
  var _omniWasGenerating = false;

  // Single timer handle — guarantees only one omniPollStatus chain runs at
  // a time regardless of how many times omniGenerate is called.
  var _pollTimer = null;

  function _schedulePoll(ms) {{
    clearTimeout(_pollTimer);
    _pollTimer = setTimeout(omniPollStatus, ms === undefined ? 2000 : ms);
  }}

  async function omniLoadStatus() {{
    try {{
      var res = await fetch('/summary');
      var data = await res.json();
      var svcs = data.services || [];
      var up = svcs.filter(function(s){{return s.status==='UP';}}).length;
      var badge = document.getElementById('omni-svc-badge');
      var dot = '<div class="chip-dot" style="background:' + (up===svcs.length?'#10b981':'#f59e0b') + ';"></div>';
      badge.innerHTML = dot + up + '/' + svcs.length + ' UP';
      badge.style.display = 'inline-flex';
      badge.className = 'status-chip ' + (up===svcs.length?'chip-green':'chip-amber');
    }} catch(e) {{}}
  }}

  async function omniPollStatus() {{
    _pollTimer = null;
    try {{
      var res = await fetch('/report/status');
      var state = await res.json();
      var btn = document.getElementById('omni-btn-regen');
      var spin = document.getElementById('omni-spin');
      var prog = document.getElementById('omni-prog');
      var ts = document.getElementById('omni-rpt-ts');
      if(state.status === 'running') {{
        btn.disabled = true;
        spin.style.display = 'inline-block';
        prog.style.display = 'inline';
        prog.textContent = 'Generating\u2026';
        _schedulePoll();
      }} else if(state.status === 'done') {{
        btn.disabled = false;
        spin.style.display = 'none';
        prog.style.display = 'none';
        // Reload only when:
        //   1. The user clicked Regenerate in *this* page session, AND
        //   2. We have not already reloaded once after this generation.
        if(_omniWasGenerating && !_justReloaded) {{
          _omniWasGenerating = false;
          sessionStorage.setItem(RELOAD_KEY, '1');
          window.location.reload();
        }}
        // No further polling needed — we are done or already reloaded.
      }} else if(state.status === 'error') {{
        btn.disabled = false;
        spin.style.display = 'none';
        prog.style.display = 'inline';
        prog.style.color = '#dc2626';
        prog.textContent = 'Error: ' + (state.message || 'unknown');
      }} else {{
        // idle — show last generated timestamp
        btn.disabled = false;
        spin.style.display = 'none';
        prog.style.display = 'none';
        if(state.report_generated_at) {{
          ts.textContent = 'Generated: ' + new Date(state.report_generated_at).toLocaleString();
        }}
      }}
    }} catch(e) {{}}
  }}

  window.omniGenerate = async function() {{
    try {{
      var res = await fetch('/report/generate', {{method:'POST'}});
      if(res.status === 409) return;
      _omniWasGenerating = true;
      var btn = document.getElementById('omni-btn-regen');
      var spin = document.getElementById('omni-spin');
      var prog = document.getElementById('omni-prog');
      btn.disabled = true;
      spin.style.display = 'inline-block';
      prog.style.display = 'inline';
      prog.style.color = '#6b7280';
      prog.textContent = 'Generating\u2026 (2\u20135 min)';
      _schedulePoll();
    }} catch(e) {{ console.error(e); }}
  }};

  omniLoadStatus();
  setInterval(omniLoadStatus, 15000);

  // On page load: poll once to show the timestamp.
  // If _justReloaded is true we already consumed the flag above, so this poll
  // will see 'done' or 'idle' but _omniWasGenerating is false → no second reload.
  omniPollStatus();
}})();
</script>
"""
        if '<body>' in report_html:
            report_html = report_html.replace('<body>', '<body>' + sticky_bar, 1)
        else:
            report_html = sticky_bar + report_html

        return HTMLResponse(content=report_html)

    # No report yet — show landing page
    return HTMLResponse(content="""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OmniBioAI — Generate Report</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:'Inter',system-ui,sans-serif;background:#f9fafb;display:flex;align-items:center;justify-content:center;min-height:100vh;}
    .card{background:white;border:1px solid #e5e7eb;border-radius:14px;padding:48px;max-width:480px;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.06);}
    .logo{font-size:22px;font-weight:700;color:#2563eb;margin-bottom:8px;}
    .sub{font-size:14px;color:#9ca3af;margin-bottom:32px;}
    .btn{font-size:14px;font-weight:600;padding:12px 28px;border-radius:9px;cursor:pointer;border:none;background:#2563eb;color:white;font-family:inherit;display:inline-flex;align-items:center;gap:8px;}
    .btn:disabled{background:#93c5fd;cursor:not-allowed;}
    .btn-outline{background:white;border:1px solid #d1d5db;color:#374151;margin-top:10px;}
    .msg{font-size:12px;color:#6b7280;margin-top:16px;}
    .spin{width:16px;height:16px;border:2px solid rgba(255,255,255,.4);border-top-color:white;border-radius:50%;animation:spin .8s linear infinite;display:none;}
    @keyframes spin{to{transform:rotate(360deg);}}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">OmniBioAI</div>
    <div class="sub">No ecosystem report found. Generate one to get started.</div>
    <button class="btn" id="btn" onclick="generate()">
      <span class="spin" id="spin"></span>
      &#128196; Generate Report
    </button>
    <br>
    <a href="/dashboard" class="btn btn-outline" style="margin-top:12px;display:inline-flex;">&#9881; View Dashboard</a>
    <div class="msg" id="msg"></div>
  </div>
<script>
  async function generate() {
    var btn=document.getElementById('btn'),spin=document.getElementById('spin'),msg=document.getElementById('msg');
    btn.disabled=true;spin.style.display='inline-block';msg.textContent='Generating report\u2026 this takes 2\u20135 minutes';
    try{
      await fetch('/report/generate',{method:'POST'});
      poll();
    }catch(e){msg.textContent='Error: '+e;btn.disabled=false;spin.style.display='none';}
  }
  async function poll(){
    try{
      var res=await fetch('/report/status'),state=await res.json();
      if(state.status==='done'){window.location.reload();}
      else if(state.status==='error'){
        document.getElementById('msg').textContent='Error: '+(state.message||'unknown');
        document.getElementById('btn').disabled=false;
        document.getElementById('spin').style.display='none';
      }else{setTimeout(poll,2000);}
    }catch(e){setTimeout(poll,3000);}
  }
</script>
</body>
</html>
""")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OmniBioAI Control Center</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Inter','Segoe UI',system-ui,Arial,sans-serif; background:#f9fafb; color:#111827; min-height:100vh; display:flex; flex-direction:column; }
    a { text-decoration:none; color:inherit; }
    .site-header { display:flex; align-items:center; justify-content:space-between; padding:10px 28px; background:white; box-shadow:0 2px 8px rgba(0,0,0,.1); gap:12px; flex-shrink:0; }
    .logo { display:flex; align-items:center; gap:10px; }
    .logo-text { font-size:18px; font-weight:700; color:#2563eb; letter-spacing:-.01em; }
    .logo-text span { font-weight:400; }
    .logo-sub { font-size:11px; color:#9ca3af; margin-top:1px; }
    .header-right { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
    .status-chip { font-size:12px; font-weight:600; padding:5px 13px; border-radius:99px; display:inline-flex; align-items:center; gap:6px; }
    .chip-green { background:#ecfdf5; color:#059669; border:1px solid #a7f3d0; }
    .chip-red   { background:#fef2f2; color:#dc2626; border:1px solid #fecaca; }
    .chip-amber { background:#fffbeb; color:#d97706; border:1px solid #fde68a; }
    .chip-dot { width:7px; height:7px; border-radius:50%; }
    .dot-green { background:#10b981; } .dot-red { background:#ef4444; } .dot-amber { background:#f59e0b; }
    .btn { font-size:13px; font-weight:600; padding:7px 15px; border-radius:8px; cursor:pointer; border:1px solid; display:inline-flex; align-items:center; gap:6px; font-family:inherit; text-decoration:none; transition:opacity .12s; }
    .btn:hover { opacity:.88; }
    .btn-outline { background:white; border-color:#d1d5db; color:#374151; }
    .btn-primary { background:#2563eb; border-color:#2563eb; color:white; }
    .btn-primary:disabled { background:#93c5fd; border-color:#93c5fd; cursor:not-allowed; }
    .btn-light { background:#eff6ff; border-color:#bfdbfe; color:#1d4ed8; }
    .btn-sm { font-size:12px; padding:5px 12px; }
    .omni-wrap { max-width:1280px; margin:0 auto; padding:24px 28px 48px; width:100%; flex:1; }
    .omni-hero { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:24px; padding-bottom:20px; border-bottom:1px solid #e5e7eb; }
    .omni-title { font-size:22px; font-weight:700; color:#111827; margin-bottom:4px; }
    .omni-sub { font-size:13px; color:#6b7280; margin-bottom:10px; }
    .omni-meta { display:flex; gap:8px; flex-wrap:wrap; }
    .meta-pill { font-size:11px; font-weight:600; padding:3px 10px; border-radius:99px; background:#f3f4f6; color:#6b7280; border:1px solid #e5e7eb; }
    .meta-pill.blue { background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe; }
    .omni-actions { display:flex; align-items:center; gap:8px; flex-shrink:0; padding-top:4px; }
    .kpi-strip { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:20px; }
    .kpi-card { background:white; border:1px solid #e5e7eb; border-radius:10px; padding:16px 18px; position:relative; overflow:hidden; }
    .kpi-card::before { content:''; position:absolute; top:0; left:0; right:0; height:3px; }
    .kpi-gray::before  { background:#d1d5db; } .kpi-green::before { background:#10b981; }
    .kpi-red::before   { background:#ef4444; } .kpi-amber::before { background:#f59e0b; }
    .kpi-blue::before  { background:#2563eb; }
    .kpi-label { font-size:10px; font-weight:600; color:#9ca3af; text-transform:uppercase; letter-spacing:.07em; margin-bottom:8px; }
    .kpi-val { font-size:28px; font-weight:700; color:#111827; line-height:1; margin-bottom:3px; }
    .kpi-val.g { color:#059669; } .kpi-val.r { color:#dc2626; }
    .kpi-sub { font-size:11px; color:#9ca3af; }
    .omni-card { background:white; border:1px solid #e5e7eb; border-radius:10px; margin-bottom:16px; overflow:hidden; }
    .omni-card-h { padding:11px 18px; border-bottom:1px solid #f3f4f6; display:flex; align-items:center; justify-content:space-between; background:#fafafa; }
    .omni-card-t { font-size:13px; font-weight:700; color:#111827; }
    .omni-card-b { padding:16px 18px; }
    .spinner { width:14px; height:14px; border:2px solid #e5e7eb; border-top-color:#2563eb; border-radius:50%; animation:spin .8s linear infinite; display:inline-block; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .progress-msg { font-size:11px; color:#6b7280; }
    .progress-msg.err { color:#dc2626; }
    .svc-table { width:100%; border-collapse:collapse; }
    .svc-table th { font-size:10px; font-weight:700; color:#9ca3af; text-transform:uppercase; letter-spacing:.07em; padding:9px 14px; border-bottom:1px solid #f3f4f6; text-align:left; background:#fafafa; white-space:nowrap; }
    .svc-table td { font-size:12px; color:#374151; padding:10px 14px; border-bottom:1px solid #f9fafb; vertical-align:middle; }
    .svc-table tr:last-child td { border-bottom:none; }
    .svc-table tr:hover td { background:#fafafa; }
    .svc-name { font-weight:700; color:#111827; font-size:13px; white-space:nowrap; }
    .badge { font-size:10px; font-weight:700; padding:3px 9px; border-radius:99px; white-space:nowrap; }
    .badge-up { background:#dcfce7; color:#15803d; } .badge-dn { background:#fee2e2; color:#b91c1c; } .badge-wn { background:#fef3c7; color:#92400e; }
    .type-pill { font-size:10px; color:#6b7280; background:#f9fafb; border:1px solid #f3f4f6; border-radius:5px; padding:2px 7px; white-space:nowrap; }
    .latency { font-family:'IBM Plex Mono',monospace; font-size:11px; color:#374151; white-space:nowrap; }
    .lat-fast { color:#059669; font-weight:600; }
    .ui-link { font-size:11px; font-weight:600; color:#2563eb; background:#eff6ff; border:1px solid #bfdbfe; border-radius:6px; padding:3px 9px; white-space:nowrap; text-decoration:none; }
    .ui-link:hover { background:#dbeafe; }
    .target-cell { font-size:11px; color:#9ca3af; font-family:monospace; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .msg-cell { font-size:11px; color:#6b7280; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .disk-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
    .disk-item { background:#fafafa; border:1px solid #f3f4f6; border-radius:8px; padding:12px 14px; border-left-width:3px; }
    .disk-ok { border-left-color:#10b981; } .disk-warn { border-left-color:#f59e0b; } .disk-down { border-left-color:#ef4444; }
    .disk-hdr { display:flex; justify-content:space-between; align-items:center; margin-bottom:3px; }
    .disk-name { font-size:12px; font-weight:700; color:#111827; }
    .disk-path { font-size:10px; color:#9ca3af; margin-bottom:7px; }
    .track { height:5px; background:#e5e7eb; border-radius:99px; overflow:hidden; margin-bottom:4px; }
    .fill { height:100%; border-radius:99px; }
    .fill-ok { background:#10b981; } .fill-warn { background:#f59e0b; } .fill-down { background:#ef4444; }
    .raw-toggle { font-size:12px; color:#9ca3af; cursor:pointer; background:none; border:none; font-family:inherit; text-decoration:underline; padding:0; }
    pre { background:#f8fafc; border:1px solid #e5e7eb; border-radius:8px; padding:14px; overflow:auto; font-size:11px; color:#374151; display:none; line-height:1.6; margin-top:8px; }
    footer { text-align:center; padding:20px; font-size:11px; color:#9ca3af; border-top:1px solid #f3f4f6; margin-top:auto; }
  </style>
</head>
<body>

<header class="site-header">
  <div class="logo">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 34" width="36" height="36">
      <polygon points="16,2 28,8 28,22 16,28 4,22 4,8" fill="none" stroke="#2563eb" stroke-width="1.8"/>
      <path d="M11 9 C16 13,14 17,20 20 M20 9 C15 13,17 17,11 20" stroke="#2563eb" stroke-width="1.6" fill="none" stroke-linecap="round"/>
      <circle cx="16" cy="15" r="2.2" fill="#2563eb"/>
    </svg>
    <div>
      <div class="logo-text">Omni<span>BioAI</span></div>
      <div class="logo-sub">Control Center v0.1.0</div>
    </div>
  </div>
  <div class="header-right">
    <div class="status-chip chip-green" id="header-status">
      <div class="chip-dot dot-green" id="header-dot"></div>
      <span id="header-status-text">Checking&hellip;</span>
    </div>
    <button class="btn btn-outline btn-sm" onclick="loadHealth()">&#8635; Refresh</button>
    <span id="rpt-spinner-hdr" class="spinner" style="display:none;"></span>
    <span id="rpt-progress-hdr" class="progress-msg" style="display:none;font-size:11px;"></span>
    <button class="btn btn-primary btn-sm" id="btn-generate-hdr" onclick="generateReport()">Generate Report</button>
    <a class="btn btn-light btn-sm" id="btn-view-hdr" href="/" style="display:none;">View Report &#8599;</a>
  </div>
</header>

<div class="omni-wrap">
  <div class="omni-hero">
    <div>
      <div class="omni-title">Health Dashboard</div>
      <div class="omni-sub">OmniBioAI Ecosystem &middot; Stateless health monitoring</div>
      <div class="omni-meta">
        <span class="meta-pill blue">v0.1.0</span>
        <span class="meta-pill">auto-refreshes every 10 s</span>
        <span class="meta-pill" id="meta-checked">Last checked: &mdash;</span>
      </div>
    </div>
    <div class="omni-actions">
      <button class="btn btn-outline btn-sm" onclick="loadHealth()">&#8635; Refresh</button>
    </div>
  </div>

  <div class="kpi-strip">
    <div class="kpi-card kpi-gray"><div class="kpi-label">Services</div><div class="kpi-val" id="kpi-total">&mdash;</div><div class="kpi-sub">monitored</div></div>
    <div class="kpi-card kpi-green"><div class="kpi-label">Healthy</div><div class="kpi-val g" id="kpi-up">&mdash;</div><div class="kpi-sub">UP</div></div>
    <div class="kpi-card kpi-red"><div class="kpi-label">Down</div><div class="kpi-val" id="kpi-down">&mdash;</div><div class="kpi-sub">need attention</div></div>
    <div class="kpi-card kpi-amber"><div class="kpi-label">Degraded</div><div class="kpi-val" id="kpi-warn">&mdash;</div><div class="kpi-sub">WARN</div></div>
    <div class="kpi-card kpi-blue"><div class="kpi-label">Disk warnings</div><div class="kpi-val" id="kpi-disk">&mdash;</div><div class="kpi-sub">paths checked</div></div>
  </div>

  <div class="omni-card">
    <div class="omni-card-h">
      <span class="omni-card-t">Services</span>
      <span class="meta-pill" id="last-checked-pill">Last checked: &mdash;</span>
    </div>
    <div class="omni-card-b" style="padding:0;">
      <table class="svc-table">
        <thead><tr><th>Service</th><th>Type</th><th>Target</th><th>Latency</th><th>Message</th><th>Status</th><th>UI</th></tr></thead>
        <tbody id="svc-tbody"><tr><td colspan="7" style="text-align:center;padding:24px;color:#9ca3af;font-size:12px;">Loading&hellip;</td></tr></tbody>
      </table>
    </div>
  </div>

  <div class="omni-card" id="disk-card" style="display:none;">
    <div class="omni-card-h"><span class="omni-card-t">Disk Checks</span></div>
    <div class="omni-card-b"><div class="disk-grid" id="disk-grid"></div></div>
  </div>

  <button class="raw-toggle" onclick="toggleRaw()">Show raw JSON</button>
  <pre id="raw"></pre>
</div>

<footer>&copy; 2025 Manish Kumar &middot; OmniBioAI Platform</footer>

<script>
  var rawVisible=false,pollTimer=null,_dashWasGenerating=false;
  function toggleRaw(){rawVisible=!rawVisible;document.getElementById('raw').style.display=rawVisible?'block':'none';document.querySelector('.raw-toggle').textContent=rawVisible?'Hide raw JSON':'Show raw JSON';}
  function esc(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');}
  function badgeHtml(st){var c=st==='UP'?'badge-up':st==='WARN'?'badge-wn':'badge-dn';return '<span class="badge '+c+'">'+esc(st)+'</span>';}
  function setHeaderStatus(overall){
    var h=document.getElementById('header-status'),d=document.getElementById('header-dot'),t=document.getElementById('header-status-text');
    if(overall==='UP'){h.className='status-chip chip-green';d.className='chip-dot dot-green';t.textContent='All systems operational';}
    else if(overall==='DOWN'){h.className='status-chip chip-red';d.className='chip-dot dot-red';t.textContent='One or more services down';}
    else{h.className='status-chip chip-amber';d.className='chip-dot dot-amber';t.textContent='Services degraded';}
  }
  function renderKpis(s,d){
    var up=s.filter(function(x){return x.status==='UP';}).length;
    var dn=s.filter(function(x){return x.status==='DOWN';}).length;
    var wn=s.filter(function(x){return x.status==='WARN';}).length;
    var dw=(d||[]).filter(function(x){return x.status!=='UP';}).length;
    document.getElementById('kpi-total').textContent=s.length;
    document.getElementById('kpi-up').textContent=up;
    document.getElementById('kpi-down').textContent=dn;
    document.getElementById('kpi-warn').textContent=wn;
    document.getElementById('kpi-disk').textContent=dw;
  }
  function renderServices(services){
    var tb=document.getElementById('svc-tbody');
    if(!services.length){tb.innerHTML='<tr><td colspan="7" style="text-align:center;padding:24px;color:#9ca3af;font-size:12px;">No services configured</td></tr>';return;}
    var rows='';
    for(var i=0;i<services.length;i++){
      var s=services[i];
      var lat=s.latency_ms!=null?'<span class="latency'+(s.latency_ms<10?' lat-fast':'')+'">'+s.latency_ms+' ms</span>':'<span class="latency" style="color:#d1d5db;">&mdash;</span>';
      var ui=s.ui_url?'<a class="ui-link" href="'+esc(s.ui_url)+'" target="_blank">Open UI &#8599;</a>':'<span style="color:#d1d5db;font-size:11px;">&mdash;</span>';
      rows+='<tr><td class="svc-name">'+esc(s.name)+'</td><td><span class="type-pill">'+esc(s.type||'—')+'</span></td><td class="target-cell">'+esc(s.target||'—')+'</td><td>'+lat+'</td><td class="msg-cell">'+esc(s.message||'—')+'</td><td>'+badgeHtml(s.status)+'</td><td>'+ui+'</td></tr>';
    }
    tb.innerHTML=rows;
  }
  function renderDisk(disk){
    var card=document.getElementById('disk-card'),grid=document.getElementById('disk-grid');
    if(!disk||!disk.length){card.style.display='none';return;}
    card.style.display='block';
    var html='';
    for(var i=0;i<disk.length;i++){
      var d=disk[i],m=d.message?d.message.match(/([0-9.]+)%/):null,pct=m?parseFloat(m[1]):null;
      var cls=d.status==='UP'?'disk-ok':d.status==='WARN'?'disk-warn':'disk-down';
      var fcls=d.status==='UP'?'fill-ok':d.status==='WARN'?'fill-warn':'fill-down';
      var pcss=d.status==='UP'?'color:#059669':d.status==='WARN'?'color:#d97706':'color:#dc2626';
      var bar=pct!==null?'<div class="track"><div class="fill '+fcls+'" style="width:'+pct.toFixed(1)+'%"></div></div>':'';
      html+='<div class="disk-item '+cls+'"><div class="disk-hdr"><div class="disk-name">'+esc(d.name.replace('disk:',''))+'</div><div style="font-size:12px;font-weight:700;'+pcss+'">'+esc(d.message||'')+'</div></div><div class="disk-path">'+esc(d.target||'')+'</div>'+bar+'</div>';
    }
    grid.innerHTML=html;
  }
  async function loadHealth(){
    try{
      var res=await fetch('/summary'),data=await res.json();
      var ts=(data.generated_at||'').replace('T',' ').substring(0,19)+' UTC';
      document.getElementById('meta-checked').textContent='Last checked: '+ts;
      document.getElementById('last-checked-pill').textContent='Last checked: '+ts;
      document.getElementById('raw').textContent=JSON.stringify(data,null,2);
      setHeaderStatus(data.overall_status||'WARN');
      var svcs=data.services||[],disk=(data.system||{}).disk||[];
      renderKpis(svcs,disk);renderServices(svcs);renderDisk(disk);
    }catch(e){
      setHeaderStatus('DOWN');
      document.getElementById('svc-tbody').innerHTML='<tr><td colspan="7" style="text-align:center;padding:24px;color:#dc2626;font-size:12px;">Could not reach /summary: '+esc(String(e))+'</td></tr>';
    }
  }
  function setReportUI(state){
    var bgh=document.getElementById('btn-generate-hdr');
    var bvh=document.getElementById('btn-view-hdr');
    var sp=document.getElementById('rpt-spinner-hdr'),pg=document.getElementById('rpt-progress-hdr');
    if(state.status==='running'){
      bgh.disabled=true;sp.style.display='inline-block';pg.style.display='inline';pg.className='progress-msg';pg.textContent='Generating\u2026 (2\u20135 min)';bvh.style.display='none';
    }else if(state.status==='done'){
      bgh.disabled=false;sp.style.display='none';pg.style.display='none';
      if(state.report_exists){bvh.style.display='inline-flex';}
      // Only redirect if user clicked Generate in this session
      if(_dashWasGenerating){ _dashWasGenerating=false; window.location.href='/'; }
    }else if(state.status==='error'){
      bgh.disabled=false;sp.style.display='none';pg.style.display='inline';pg.className='progress-msg err';pg.textContent='Error: '+(state.message||'unknown');
    }else{
      bgh.disabled=false;sp.style.display='none';pg.style.display='none';
      if(state.report_exists){bvh.style.display='inline-flex';}
    }
  }
  async function pollReportStatus(){
    try{
      var res=await fetch('/report/status'),state=await res.json();
      setReportUI(state);
      pollTimer=state.status==='running'?setTimeout(pollReportStatus,2000):null;
    }catch(e){pollTimer=null;}
  }
  async function generateReport(){
    try{
      var res=await fetch('/report/generate',{method:'POST'});
      if(res.status===409)return;
      _dashWasGenerating=true;
      setReportUI({status:'running'});
      pollTimer=setTimeout(pollReportStatus,2000);
    }catch(e){console.error(e);}
  }
  loadHealth();setInterval(loadHealth,10000);pollReportStatus();
</script>
</body>
</html>
"""

===== FILE: core/settings.py =====

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class Settings:
    services: dict[str, dict[str, Any]]
    system: dict[str, Any]


def _default_config_path() -> str:
    return os.environ.get("CONTROL_CENTER_CONFIG", "/config/control_center.yaml")


def load_settings() -> Settings:
    path = _default_config_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Control Center config not found: {path}. "
            f"Mount it and/or set CONTROL_CENTER_CONFIG."
        )

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    services = raw.get("services", {}) or {}
    system = raw.get("system", {}) or {}

    return Settings(services=services, system=system)


===== FILE: core/runner.py =====

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


===== FILE: checks/disk.py =====

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


===== FILE: checks/http.py =====

from __future__ import annotations

import time
import urllib.request
from typing import Any


def check_http(name: str, cfg: dict[str, Any]) -> dict:
    url = cfg.get("url")
    timeout_s = float(cfg.get("timeout_s", 2))

    if not url:
        return {
            "name": name,
            "type": "http",
            "target": "-",
            "status": "DOWN",
            "latency_ms": None,
            "message": "Missing 'url' in config",
        }

    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "omnibioai-control-center/0.1"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            _ = resp.read(64)  # small read just to validate response body exists
            code = getattr(resp, "status", 200)
        latency_ms = int((time.perf_counter() - start) * 1000)

        if 200 <= int(code) < 400:
            return {
                "name": name,
                "type": "http",
                "target": url,
                "status": "UP",
                "latency_ms": latency_ms,
                "message": f"HTTP {code}",
            }

        return {
            "name": name,
            "type": "http",
            "target": url,
            "status": "WARN",
            "latency_ms": latency_ms,
            "message": f"HTTP {code}",
        }

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "name": name,
            "type": "http",
            "target": url,
            "status": "DOWN",
            "latency_ms": latency_ms,
            "message": f"{type(e).__name__}: {e}",
        }


===== FILE: checks/tcp.py =====

from __future__ import annotations

import socket
import time


def check_tcp(name: str, host: str | None, port: int, kind: str) -> dict:
    target = f"{host}:{port}"
    if not host:
        return {
            "name": name,
            "type": kind,
            "target": target,
            "status": "DOWN",
            "latency_ms": None,
            "message": "Missing host",
        }

    start = time.perf_counter()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect((host, port))
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "name": name,
            "type": kind,
            "target": target,
            "status": "UP",
            "latency_ms": latency_ms,
            "message": "TCP connect ok",
        }
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "name": name,
            "type": kind,
            "target": target,
            "status": "DOWN",
            "latency_ms": latency_ms,
            "message": f"{type(e).__name__}: {e}",
        }
    finally:
        try:
            s.close()
        except Exception:
            pass


===== FILE: api/routes_health.py =====

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


===== FILE: api/routes_report.py =====

"""
control_center/api/routes_report.py

Routes for the ecosystem HTML report.

GET /report  → redirects to / which serves the report with the injected
               OmniBioAI header (Regenerate button, live service status).

Environment variables
---------------------
WORKSPACE_ROOT          Root of the ecosystem checkout (default: /workspace)
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/report")
def report() -> RedirectResponse:
    """
    Redirect /report → / which injects the OmniBioAI header
    (Regenerate button, live service status chip, Dashboard link)
    before serving the report HTML.

    Uses 302 (temporary) so browsers don't cache the redirect —
    important during development when the route may change.
    """
    return RedirectResponse(url="/", status_code=302)

===== FILE: api/routes_services.py =====

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from control_center.core.settings import load_settings
from control_center.core.runner import run_all_checks
from control_center.api.routes_summary import _inject_ui_urls

router = APIRouter()


@router.get("/services")
def services() -> JSONResponse:
    try:
        settings = load_settings()
        results = run_all_checks(settings)
        results = _inject_ui_urls(results, settings.services)
        return JSONResponse({"services": results})
    except FileNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=500)

===== FILE: api/routes_summary.py =====

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from control_center.core.settings import load_settings
from control_center.core.runner import run_all_checks
from control_center.checks.disk import run_disk_checks

router = APIRouter()


def _inject_ui_urls(
    service_results: list[dict],
    services_cfg: dict,
) -> list[dict]:
    """
    Enrich each service result with ui_url from config (if present).
    ui_url is optional — services without it (mysql, redis) get None.
    """
    for result in service_results:
        cfg = services_cfg.get(result["name"], {})
        result["ui_url"] = cfg.get("ui_url") or None
    return service_results


@router.get("/summary")
def summary() -> JSONResponse:
    try:
        settings = load_settings()
    except FileNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    service_results = run_all_checks(settings)
    service_results = _inject_ui_urls(service_results, settings.services)
    disk_results = run_disk_checks(settings)

    overall = "UP"
    for r in service_results + disk_results:
        if r["status"] == "DOWN":
            overall = "DOWN"
            break
        if r["status"] == "WARN" and overall != "DOWN":
            overall = "WARN"

    return JSONResponse({
        "overall_status": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "services": service_results,
        "system": {
            "disk": disk_results,
        },
    })

===== FILE: utils/summary_client.py =====

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
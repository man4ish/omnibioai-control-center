# backend/src/control_center/main.py

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    """
    Minimal live health dashboard (v1).
    Data is fetched from /summary every 10 seconds.
    The full ecosystem report (code stats + coverage + health) is at /report.
    """
    return """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width,initial-scale=1"/>
    <title>OmniBioAI Control Center</title>
    <style>
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        font-family: 'IBM Plex Sans', ui-sans-serif, system-ui, Arial, sans-serif;
        background: #F1F5F9;
        color: #111827;
        padding: 28px 24px 48px;
      }
      .page-wrap { max-width: 1200px; margin: 0 auto; }

      /* ── Header ── */
      .header { margin-bottom: 22px; }
      .header h1 { font-size: 20px; font-weight: 700; color: #0F172A; margin-bottom: 4px; }
      .header .sub { font-size: 12px; color: #9CA3AF; }

      /* ── Top bar ── */
      .topbar {
        display: flex; align-items: center; gap: 10px;
        margin-bottom: 20px; flex-wrap: wrap;
      }
      .btn {
        border: 1px solid #E5E7EB; border-radius: 8px;
        padding: 7px 14px; background: white; cursor: pointer;
        font-size: 13px; font-weight: 600; color: #374151;
      }
      .btn:hover { background: #F8FAFC; }
      .btn-report {
        background: #0F172A; color: white;
        border-color: #0F172A; text-decoration: none;
        display: inline-flex; align-items: center; gap: 6px;
      }
      .btn-report:hover { background: #1E293B; }
      .last-checked { font-size: 12px; color: #9CA3AF; margin-left: auto; }

      /* ── Overall banner ── */
      .banner {
        border-radius: 12px; padding: 14px 18px;
        margin-bottom: 20px;
        display: flex; align-items: center; gap: 12px;
        border: 1px solid transparent;
      }
      .banner-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
      .banner-title { font-size: 14px; font-weight: 600; }
      .banner-sub { font-size: 11px; margin-top: 2px; }
      .banner-up    { background: #ECFDF5; border-color: #6EE7B733; }
      .banner-down  { background: #FEF2F2; border-color: #FCA5A533; }
      .banner-warn  { background: #FFFBEB; border-color: #FCD34D33; }

      /* ── Service cards ── */
      .section-label {
        font-size: 11px; font-weight: 600; color: #9CA3AF;
        text-transform: uppercase; letter-spacing: .06em;
        margin-bottom: 12px;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 12px;
        margin-bottom: 24px;
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

      /* ── Raw summary ── */
      .raw-section { margin-top: 8px; }
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
  <div class="page-wrap">

    <div class="header">
      <h1>OmniBioAI Control Center</h1>
      <div class="sub">Stateless health dashboard · auto-refreshes every 10 s</div>
    </div>

    <div class="topbar">
      <button class="btn" onclick="load()">Refresh</button>
      <a class="btn btn-report" href="/report" target="_blank">
        Ecosystem Report ↗
      </a>
      <span class="last-checked" id="last"></span>
    </div>

    <div id="banner" class="banner" style="display:none;"></div>

    <div class="section-label">Services</div>
    <div class="grid" id="cards"></div>

    <div class="raw-section">
      <button class="raw-toggle" onclick="toggleRaw()">Show raw JSON</button>
      <pre id="raw"></pre>
    </div>

  </div>

  <script>
    var rawVisible = false;

    function toggleRaw() {
      rawVisible = !rawVisible;
      document.getElementById('raw').style.display = rawVisible ? 'block' : 'none';
      document.querySelector('.raw-toggle').textContent =
        rawVisible ? 'Hide raw JSON' : 'Show raw JSON';
    }

    function esc(s) {
      return String(s)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    }

    function badgeClass(status) {
      if (status === 'UP')   return 'badge badge-up';
      if (status === 'WARN') return 'badge badge-warn';
      return 'badge badge-down';
    }

    function setBanner(overall) {
      var banner = document.getElementById('banner');
      var cls = 'banner-warn';
      var dot = '#F59E0B';
      var msg = 'One or more services need attention';
      var sub = 'Overall: ' + overall;
      if (overall === 'UP') {
        cls = 'banner-up'; dot = '#10B981';
        msg = 'All systems operational';
      } else if (overall === 'DOWN') {
        cls = 'banner-down'; dot = '#EF4444';
        msg = 'One or more services are down';
      }
      banner.className = 'banner ' + cls;
      banner.style.display = 'flex';
      banner.innerHTML =
        '<div class="banner-dot" style="background:' + dot + '"></div>' +
        '<div><div class="banner-title">' + esc(msg) + '</div>' +
        '<div class="banner-sub" style="color:' + dot + '">' + esc(sub) + '</div></div>';
    }

    async function load() {
      try {
        var res = await fetch('/summary');
        var data = await res.json();

        document.getElementById('last').textContent =
          'Last checked: ' + (data.generated_at || '(unknown)');

        document.getElementById('raw').textContent =
          JSON.stringify(data, null, 2);

        setBanner(data.overall_status || 'WARN');

        var cards = document.getElementById('cards');
        cards.innerHTML = '';

        var items = (data.services || []);
        for (var i = 0; i < items.length; i++) {
          var s = items[i];
          var latency = s.latency_ms !== null && s.latency_ms !== undefined
            ? s.latency_ms + ' ms' : '—';
          var border = s.status === 'UP'
            ? '#D1FAE5' : s.status === 'DOWN' ? '#FEE2E2' : '#FEF3C7';

          var el = document.createElement('div');
          el.className = 'card';
          el.style.borderColor = border;
          el.innerHTML =
            '<div class="card-header">' +
              '<div class="card-name">' + esc(s.name) + '</div>' +
              '<span class="' + badgeClass(s.status) + '">' + esc(s.status) + '</span>' +
            '</div>' +
            '<div class="kv">' +
              '<span class="kv-label">Type</span><span class="kv-val">' + esc(s.type || '—') + '</span>' +
              '<span class="kv-label">Target</span><span class="kv-val">' + esc(s.target || '—') + '</span>' +
              '<span class="kv-label">Latency</span><span class="kv-val">' + esc(latency) + '</span>' +
              '<span class="kv-label">Message</span><span class="kv-val">' + esc(s.message || '—') + '</span>' +
            '</div>';
          cards.appendChild(el);
        }
      } catch(e) {
        document.getElementById('banner').className = 'banner banner-down';
        document.getElementById('banner').style.display = 'flex';
        document.getElementById('banner').innerHTML =
          '<div class="banner-dot" style="background:#EF4444"></div>' +
          '<div><div class="banner-title">Could not reach /summary</div>' +
          '<div class="banner-sub" style="color:#EF4444">' + esc(String(e)) + '</div></div>';
      }
    }

    load();
    setInterval(load, 10000);
  </script>
  </body>
</html>
"""
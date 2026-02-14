from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from control_center.api.routes_health import router as health_router
from control_center.api.routes_services import router as services_router
from control_center.api.routes_summary import router as summary_router

app = FastAPI(
    title="OmniBioAI Control Center",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(services_router)
app.include_router(summary_router)


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    # Minimal HTML UI (v1). The data comes from /summary.
    return """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width,initial-scale=1"/>
    <title>OmniBioAI Control Center</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; }
      h1 { margin: 0 0 8px; font-size: 22px; }
      .meta { color: #555; margin-bottom: 18px; }
      .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
      .card { border: 1px solid #ddd; border-radius: 12px; padding: 14px; background: #fff; }
      .row { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
      .name { font-weight: 600; }
      .badge { padding: 2px 10px; border-radius: 999px; font-size: 12px; border: 1px solid #ccc; }
      .up { background: #e9f7ef; border-color: #bfe7cf; }
      .down { background: #fdecea; border-color: #f5c2c7; }
      .warn { background: #fff4e5; border-color: #ffe0b2; }
      .kv { margin-top: 8px; font-size: 13px; color: #333; }
      .kv div { margin: 3px 0; }
      .small { color: #666; font-size: 12px; }
      .topbar { display:flex; gap: 12px; align-items:center; margin: 10px 0 18px; }
      button { border: 1px solid #ccc; border-radius: 10px; padding: 8px 12px; background: #fafafa; cursor: pointer; }
      button:hover { background: #f4f4f4; }
      pre { background:#f6f8fa; padding: 12px; border-radius: 10px; overflow:auto; }
    </style>
  </head>
  <body>
    <h1>OmniBioAI Control Center</h1>
    <div class="meta">Stateless health dashboard for the local stack</div>

    <div class="topbar">
      <button onclick="load()">Refresh</button>
      <span class="small" id="last"></span>
    </div>

    <div class="grid" id="cards"></div>

    <h2 style="margin-top:22px;font-size:16px;">Raw summary</h2>
    <pre id="raw">(loading...)</pre>

    <script>
      function esc(s){ return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;"); }

      function badgeClass(status){
        if(status === "UP") return "badge up";
        if(status === "WARN") return "badge warn";
        return "badge down";
      }

      async function load(){
        const res = await fetch("/summary");
        const data = await res.json();

        document.getElementById("last").textContent =
          "Last checked: " + (data.generated_at || "(unknown)");

        document.getElementById("raw").textContent = JSON.stringify(data, null, 2);

        const cards = document.getElementById("cards");
        cards.innerHTML = "";

        const items = data.services || [];
        for(const s of items){
          const el = document.createElement("div");
          el.className = "card";

          const badge = `<span class="${badgeClass(s.status)}">${esc(s.status)}</span>`;

          el.innerHTML = `
            <div class="row">
              <div class="name">${esc(s.name)}</div>
              ${badge}
            </div>
            <div class="kv">
              <div><span class="small">Type:</span> ${esc(s.type || "-")}</div>
              <div><span class="small">Target:</span> ${esc(s.target || "-")}</div>
              <div><span class="small">Latency:</span> ${esc(s.latency_ms ?? "-")} ms</div>
              <div><span class="small">Message:</span> ${esc(s.message || "-")}</div>
            </div>
          `;
          cards.appendChild(el);
        }
      }

      load();
      setInterval(load, 10000); // auto refresh every 10s
    </script>
  </body>
</html>
"""

# OmniBioAI Control Center

**Operational health dashboard and ecosystem report server for the OmniBioAI stack.**

The Control Center is a lightweight FastAPI service that aggregates health status across all OmniBioAI components and serves the interactive ecosystem report covering architecture, codebase statistics, code coverage, and live service health.

---

## What It Does

- **Health monitoring** — TCP, HTTP, and disk checks across all ecosystem services
- **Live dashboard** — auto-refreshing browser UI at `/` with per-service status cards
- **Ecosystem report** — interactive HTML report (architecture · projects · languages · coverage · health) served at `/report`
- **JSON API** — machine-readable health summary at `/summary` for CI/CD and external monitoring

---

## Repository Structure

```text
omnibioai-control-center/
│
├── scripts/
│   └── generate_report.py          # Ecosystem report generator (CLI)
│
├── backend/
│   ├── pyproject.toml              # Package definition and dependencies
│   ├── src/control_center/
│   │   ├── main.py                 # FastAPI app — registers all routers
│   │   ├── api/
│   │   │   ├── routes_health.py    # GET /health
│   │   │   ├── routes_services.py  # GET /services
│   │   │   ├── routes_summary.py   # GET /summary
│   │   │   └── routes_report.py    # GET /report
│   │   ├── checks/
│   │   │   ├── http.py             # HTTP health checks
│   │   │   ├── tcp.py              # TCP health checks (MySQL, Redis)
│   │   │   └── disk.py             # Disk usage checks
│   │   ├── core/
│   │   │   ├── runner.py           # Dispatches checks per service type
│   │   │   └── settings.py         # Loads control_center.yaml
│   │   └── utils/
│   │       └── summary_client.py   # Fetches /summary for report generation
│   └── tests/
│       ├── test_checks.py          # Unit tests — tcp/http/disk
│       ├── test_runner.py          # Unit tests — runner + settings
│       └── test_summary_client.py  # Unit tests — health data parsing
│
├── compose/
│   └── docker-compose.control-center.yml
├── config/
│   ├── control_center.yaml         # Active configuration
│   └── control_center.example.yaml # Reference configuration
└── docker/
    └── Dockerfile
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Live health dashboard (auto-refreshes every 10s) |
| `/health` | GET | Control Center self-check |
| `/services` | GET | Per-service health status (JSON) |
| `/summary` | GET | Full ecosystem summary — services + disk (JSON) |
| `/report` | GET | Pre-generated ecosystem HTML report |

### `/health`

```json
{ "status": "ok" }
```

### `/summary`

```json
{
  "overall_status": "UP",
  "generated_at": "2026-03-20T02:44:00+00:00",
  "services": [
    {
      "name": "omnibioai",
      "type": "http",
      "target": "http://omnibioai:8000/",
      "status": "UP",
      "latency_ms": 12,
      "message": "HTTP 200"
    },
    {
      "name": "mysql",
      "type": "mysql",
      "target": "mysql:3306",
      "status": "UP",
      "latency_ms": 3,
      "message": "TCP connect ok"
    }
  ],
  "system": {
    "disk": [
      {
        "name": "disk:/workspace/out",
        "type": "disk",
        "target": "/workspace/out",
        "status": "UP",
        "latency_ms": null,
        "message": "45.2% free"
      }
    ]
  }
}
```

Status values: `UP` | `DOWN` | `WARN`

---

## Configuration

All monitored services and disk paths are defined in `config/control_center.yaml`.

```yaml
services:
  mysql:
    type: mysql
    host: mysql
    port: 3306

  redis:
    type: redis
    host: redis
    port: 6379

  toolserver:
    type: http
    url: http://toolserver:9090/health
    timeout_s: 2

  tes:
    type: http
    url: http://tes:8081/health
    timeout_s: 2

  omnibioai:
    type: http
    url: http://omnibioai:8000/
    timeout_s: 2

  lims-x:
    type: http
    url: http://lims-x:7000/
    timeout_s: 2

  model-registry:
    type: http
    url: http://model-registry:8095/health
    timeout_s: 2

system:
  disk_checks:
    - path: /workspace/out
      warn_pct_free_below: 15
    - path: /workspace/tmpdata
      warn_pct_free_below: 10
    - path: /workspace/local_registry
      warn_pct_free_below: 10
```

### Supported check types

| Type | Required fields | Description |
|------|----------------|-------------|
| `http` | `url`, `timeout_s` | HTTP GET — UP if 2xx, WARN if 3xx/4xx/5xx |
| `mysql` | `host`, `port` | TCP connect to MySQL port |
| `redis` | `host`, `port` | TCP connect to Redis port |

### Adding a new service

Add a block to `config/control_center.yaml` and restart the container:

```yaml
services:
  my-new-service:
    type: http
    url: http://my-service:8080/health
    timeout_s: 2
```

No code changes required.

---

## Running

### Via Docker Compose (recommended)

```bash
# From the ecosystem root (~/Desktop/machine)
docker compose \
  --project-directory . \
  -f omnibioai-control-center/compose/docker-compose.control-center.yml \
  up -d
```

Access at: `http://localhost:7070`

### Standalone (development)

```bash
cd backend
pip install -e ".[dev]"

CONTROL_CENTER_CONFIG=../config/control_center.yaml \
WORKSPACE_ROOT=~/Desktop/machine \
uvicorn control_center.main:app --host 0.0.0.0 --port 7070 --reload
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTROL_CENTER_CONFIG` | `/config/control_center.yaml` | Path to YAML config |
| `WORKSPACE_ROOT` | `/workspace` | Ecosystem root — used to locate the report file |

---

## Ecosystem Report

The report is a single interactive HTML file with five tabs:

| Tab | Contents |
|-----|----------|
| Architecture | SVG lane diagram of all services and connections |
| Projects | Code line distribution across all repositories |
| Languages | Language breakdown across the ecosystem |
| Code Coverage | Per-repo pytest coverage with progress bars |
| Health Status | Live service and disk health snapshot |

### Generate

```bash
# From the ecosystem root — with live health data
python omnibioai-control-center/scripts/generate_report.py \
    --root ~/Desktop/machine

# Skip health check (faster, offline)
python omnibioai-control-center/scripts/generate_report.py \
    --root ~/Desktop/machine \
    --skip-health

# Skip coverage collection (code stats only, very fast)
python omnibioai-control-center/scripts/generate_report.py \
    --root ~/Desktop/machine \
    --skip-coverage

# All options
python omnibioai-control-center/scripts/generate_report.py \
    --root ~/Desktop/machine \
    --control-center-url http://127.0.0.1:7070 \
    --out out/reports/omnibioai_ecosystem_report.html \
    --title "OmniBioAI Ecosystem Report"
```

### Requirements

```bash
# cloc for code counting
sudo apt-get install cloc        # Ubuntu/Debian
conda install -c conda-forge cloc  # Conda

# Python dependencies
pip install pandas

# For coverage collection (best-effort)
pip install pytest pytest-cov
```

### View

- **File:** `~/Desktop/machine/out/reports/omnibioai_ecosystem_report.html`
- **Browser:** Open directly — no server needed
- **Live:** `http://localhost:7070/report` when Control Center is running

The report generates gracefully even if the Control Center is offline or coverage collection fails — those tabs show a clear unavailable state rather than breaking the whole report.

---

## Running Tests

```bash
cd backend
pip install -e ".[dev]"
pytest tests/ -v
```

### Test coverage

| File | What it tests |
|------|--------------|
| `test_checks.py` | TCP, HTTP, and disk check modules |
| `test_runner.py` | Service type routing, settings loading |
| `test_summary_client.py` | Health data parsing, `/summary` fetch |

Tests use in-process HTTP servers — no external dependencies or running services required.

---

## Design Principles

- **Stateless** — no database, no persistent state
- **Config-driven** — add services via YAML, no code changes
- **Graceful degradation** — unreachable services show `DOWN`, never crash the dashboard
- **Zero mandatory cloud** — runs fully offline and air-gapped
- **Minimal dependencies** — FastAPI, uvicorn, PyYAML, pydantic only
- **stdlib HTTP in report** — `urllib` used for health fetching in report generator, no extra deps

---

## Planned Enhancements (Post-Beta)

- Prometheus metrics endpoint (`/metrics`)
- Scheduled report generation via cron or Celery
- Historical uptime tracking
- Alert hooks (Slack, email)
- Authentication layer for the dashboard
- Trend view — coverage and health over time

---

## Current Status — v0.1.0

| Feature | Status |
|---------|--------|
| HTTP health checks | ✓ Stable |
| TCP checks (MySQL, Redis) | ✓ Stable |
| Disk usage checks | ✓ Stable |
| Live dashboard UI | ✓ Stable |
| JSON summary API | ✓ Stable |
| Ecosystem report — Architecture | ✓ Stable |
| Ecosystem report — Projects | ✓ Stable |
| Ecosystem report — Languages | ✓ Stable |
| Ecosystem report — Coverage | ✓ Stable |
| Ecosystem report — Health tab | ✓ Stable |
| Unit tests | ✓ Stable |
| Docker Compose deployment | ✓ Stable |
| Prometheus metrics | Planned |
| Historical tracking | Planned |

---

## License

Apache License 2.0
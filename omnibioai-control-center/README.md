# OmniBioAI Control Center

**OmniBioAI Control Center** is a lightweight FastAPI service that provides centralized health monitoring for the entire OmniBioAI ecosystem.

It aggregates service health, latency, and status codes across all core components and exposes a unified `/status` endpoint for observability and diagnostics.

---

## Purpose

The Control Center acts as the operational visibility layer of OmniBioAI.

It monitors:

* OmniBioAI Workbench (Django)
* TES (Task Execution Service)
* ToolServer
* Model Registry
* LIMS-X
* Redis
* MySQL (indirectly via service health)

It is designed to:

* Provide a single health endpoint for dashboards
* Support deployment validation
* Assist debugging in local, Docker, HPC, or cloud environments
* Enable future monitoring integration (Prometheus, Grafana, etc.)

---

## Architecture

```
Client (Browser / curl)
        |
        v
Control Center (FastAPI :8100)
        |
        +--> Workbench        (/health/)
        +--> TES              (/health)
        +--> ToolServer       (/health)
        +--> Model Registry   (/health)
        +--> LIMS-X           (/ or /health)
```

The Control Center does **not** execute workflows.
It only monitors services.

---

## Endpoints

### Health

```
GET /health
```

Response:

```json
{
  "ok": true,
  "service": "omnibioai-control-center"
}
```

---

### Status

```
GET /status
```

Example response:

```json
{
  "ok": true,
  "services": {
    "workbench": {
      "ok": true,
      "status_code": 200,
      "latency_ms": 4,
      "url": "http://omnibioai:8000/health/"
    },
    "tes": {
      "ok": true,
      "status_code": 200,
      "latency_ms": 2,
      "url": "http://tes:8081/health"
    }
  }
}
```

Each service reports:

* `ok` (boolean)
* `status_code`
* `latency_ms`
* `url`
* `error` (if unreachable)

---

## Configuration (Environment Variables)

Control Center is fully configurable via environment variables.

### Core Service URLs

| Variable              | Default                                        | Description               |
| --------------------- | ---------------------------------------------- | ------------------------- |
| WORKBENCH_URL         | [http://127.0.0.1:8001](http://127.0.0.1:8001) | Django Workbench base URL |
| WORKBENCH_HEALTH_PATH | /health/                                       | Health path               |
| TES_URL               | [http://127.0.0.1:8081](http://127.0.0.1:8081) | TES base URL              |
| TOOLSERVER_URL        | [http://127.0.0.1:9090](http://127.0.0.1:9090) | ToolServer base URL       |
| MODEL_REGISTRY_URL    | [http://127.0.0.1:8095](http://127.0.0.1:8095) | Model Registry base URL   |
| LIMSX_URL             | [http://127.0.0.1:7000](http://127.0.0.1:7000) | LIMS-X base URL           |
| LIMSX_HEALTH_PATH     | /health                                        | Health path override      |

---

## Docker Usage

### Build

```bash
docker build -t omnibioai-control-center .
```

### Run (Standalone)

```bash
docker run -p 8100:8100 omnibioai-control-center
```

### Run with custom URLs

```bash
docker run \
  -e WORKBENCH_URL=http://omnibioai:8000 \
  -e TES_URL=http://tes:8081 \
  -e TOOLSERVER_URL=http://toolserver:9090 \
  -e MODEL_REGISTRY_URL=http://model-registry:8095 \
  -e LIMSX_URL=http://lims-x:7000 \
  -p 8100:8100 \
  omnibioai-control-center
```

---

## Docker Compose Integration

Example service block:

```yaml
control-center:
  build:
    context: ../../omnibioai-control-center
  container_name: omnibioai-control-center
  environment:
    WORKBENCH_URL: http://omnibioai:8000
    WORKBENCH_HEALTH_PATH: /health/
    TES_URL: http://tes:8081
    TOOLSERVER_URL: http://toolserver:9090
    MODEL_REGISTRY_URL: http://model-registry:8095
    LIMSX_URL: http://lims-x:7000
    LIMSX_HEALTH_PATH: /
  ports:
    - "8100:8100"
```

Access:

```
http://localhost:8100/status
```

---

## Running Without Docker

```bash
pip install -e .
uvicorn omnibioai_control_center.app.main:app --host 0.0.0.0 --port 8100
```

---

## Design Principles

* Stateless
* Async HTTP checks (httpx)
* Fast startup
* No database dependency
* Cloud/HPC portable
* Docker-first deployment
* Minimal attack surface

---

## Current Status (v0.1.0)

✔ Service health aggregation
✔ Latency measurement
✔ Configurable via environment
✔ Docker-ready
✔ Compose-compatible

---

## Planned Enhancements

* Prometheus metrics endpoint
* Service dependency graph view
* Web dashboard UI
* Historical uptime tracking
* Alert hooks (Slack / Email)
* Authentication layer
* Multi-cluster support

---

## Role in OmniBioAI Ecosystem

The Control Center is the **operational observability layer** of OmniBioAI.

It ensures:

* Reproducibility verification
* Deployment validation
* Infrastructure transparency
* Ecosystem integrity

---

## License

MIT License (or your chosen license)


# OmniBioAI Local Development Workspace

This repository defines a **local development workspace and orchestration layer** for the **OmniBioAI ecosystem**, including workflow execution, tool services, LIMS integration, AI-driven bioinformatics applications, and developer-facing utilities.

All services are designed to run **locally**, **without mandatory cloud dependencies**, using a shared workspace layout and reproducible startup mechanisms.

> **Important**
>
> This repository does **not** vendor or embed core application source code.
> Each major component lives in its **own GitHub repository** and is referenced here explicitly.
> This repository acts as a **local control plane and workspace coordinator**.

---

## Workspace Layout

```text
Desktop/machine/
├── omnibioai/                     # OmniBioAI Workbench (Django core platform)
├── omnibioai-tool-exec/           # TES – Tool Execution Service (local/HPC/cloud)
├── omnibioai-toolserver/          # FastAPI ToolServer (Enrichr, BLAST, etc.)
├── omnibioai-lims/                # Laboratory Information Management System (LIMS)
├── omnibioai-rag/                 # RAG-based Bioinformatics Intelligence Service
├── omnibioai_sdk/                 # Python SDK for OmniBioAI APIs
├── omnibioai-workflow-bundles/    # Workflow bundles (Nextflow, WDL, Snakemake)
├── aws-tools/                     # Cloud & infrastructure helper tools (optional)
├── utils/
│   └── kill_port.sh               # Utility to free busy ports
├── smoke_test_stack.sh            # Health checks for the full local stack
├── start_stack_tmux.sh            # One-command local stack launcher (tmux)
├── db-init/                       # Database initialization dumps
│   ├── omnibioai.sql              # OmniBioAI core DB
│   └── limsdb.sql                 # LIMS database
├── docker-compose.yml             # Full OmniBioAI local stack (Docker Compose)
├── .env.example                   # Environment variable template
├── backup/                        # Archived / experimental work
└── ai-dev-docker/                 # AI & Docker experiments (optional)
```

---

## Architecture

```mermaid
flowchart LR
  %% Clients
  U[User / Browser]
  Dev[Developer CLI / SDK]

  %% Application Services
  subgraph Apps[Application Services]
    WB[OmniBioAI Workbench\nDjango + ASGI + Channels\nPort 8000]
    LS[LIMS-X\nDjango\nPort 7000]
    TS[ToolServer\nFastAPI + Uvicorn\nPort 9090]
    TES[TES\nTool Execution Service\nPort 8080]
  end

  %% Infrastructure
  subgraph Infra[Infrastructure]
    MySQL[MySQL 8\nDatabases: omnibioai, limsdb\nPort 3306]
    Redis[Redis\nCelery + Channels\nPort 6379]
  end

  %% Shared Workspace
  subgraph Storage[Shared Workspace]
    WS[Workspace Root\nDocker: /workspace\nLocal: Desktop/machine]
    Runs[Workflow Runs and Outputs]
    Registry[Registries and Provenance\nRelative paths only]
  end

  %% Client traffic
  U --> WB
  Dev --> WB
  Dev --> TS
  Dev --> TES

  %% Service interactions
  WB --> TES
  TES --> TS

  %% Data plane
  WB --> MySQL
  LS --> MySQL
  WB --> Redis
  TES --> Redis

  %% Shared filesystem
  WB --> WS
  LS --> WS
  TS --> WS
  TES --> WS
  WS --> Runs
  WS --> Registry
```

---

## Canonical Repositories

Each component must be cloned independently.

| Component                        | Repository                                                                                         |
| -------------------------------- | -------------------------------------------------------------------------------------------------- |
| **OmniBioAI Workbench**          | [https://github.com/man4ish/omnibioai](https://github.com/man4ish/omnibioai)                       |
| **Tool Execution Service (TES)** | [https://github.com/man4ish/omnibioai-tool-exec](https://github.com/man4ish/omnibioai-tool-exec)   |
| **ToolServer**                   | [https://github.com/man4ish/omnibioai-toolserver](https://github.com/man4ish/omnibioai-toolserver) |
| **LIMS-X**                       | [https://github.com/man4ish/lims-x](https://github.com/man4ish/lims-x)                             |
| **RAGBio**                       | [https://github.com/man4ish/ragbio](https://github.com/man4ish/ragbio)                             |
| **OmniBioAI SDK**                | [https://github.com/man4ish/omnibioai_sdk](https://github.com/man4ish/omnibioai_sdk)               |

This repository **only orchestrates** these projects.

---

## Developer SDK & Utilities

### OmniBioAI SDK

`omnibioai_sdk/` provides a lightweight Python SDK for interacting with OmniBioAI APIs, including:

* Object registry access
* Development APIs (`/api/dev/*`)
* Notebook-based analysis workflows

The SDK is published independently on **PyPI** and is intended for:

* Jupyter notebooks
* Python scripts
* Workflow tooling
* Programmatic access to the OmniBioAI platform

> The SDK is a **thin client** and does not embed backend logic.

### AWS Tools (Optional)

`aws-tools/` contains experimental and optional utilities for:

* Cloud execution
* Infrastructure prototyping
* Deployment experiments

These tools are **not required** for local development and may change independently.

---

## Design Principles

* **Single workspace root**
* **Relative paths only**
* **No hardcoded absolute paths**
* **Service isolation via ports**
* **Restart-safe startup**
* **Docker ↔ non-Docker parity**

This makes the workspace:

* Portable across machines
* Safe to rename or relocate
* Suitable for Docker, HPC, or VM environments
* Stable for long-running research workflows

---

## Services & Ports

| Service             | Default Port | Description                |
| ------------------- | ------------ | -------------------------- |
| OmniBioAI Workbench | 8000         | Django UI, plugins, agents |
| TES                 | 8080         | Workflow & tool execution  |
| ToolServer          | 9090         | FastAPI tool APIs          |
| LIMS-X              | 7000         | LIMS integration           |
| MySQL               | 3306         | omnibioai + limsdb         |
| Redis               | 6379         | Celery, Channels           |

All ports are configurable via `.env`.

---

## Environment Configuration

Copy the template:

```bash
cp .env.example .env
```

Edit values as needed (ports, secrets, database credentials).

---

## Docker-Based Workflow (Recommended)

### 1. Build All Images

```bash
docker compose build
```

Each service builds from its **own repo-local Dockerfile**.

> ⚠️ **Note**
> Exclude large data directories via `.dockerignore` in each repo to avoid multi-GB build contexts.

---

### 2. Export Existing Databases (One-Time)

```bash
mysqldump -u root -p omnibioai > db-init/omnibioai.sql
mysqldump -u root -p limsdb > db-init/limsdb.sql
```

These dumps are imported automatically on first startup.

---

### 3. Start the Full Stack

```bash
docker compose up
```

Or clean rebuild:

```bash
docker compose down -v
docker compose up --build
```

---

### 4. Verify Health

```bash
curl http://localhost:9090/health
curl http://localhost:8080/health
curl http://localhost:8000/
curl http://localhost:7000/
```

---

## One-Command Startup (Non-Docker)

```bash
bash start_stack_tmux.sh
tmux attach -t omnibioai
```

Ideal for fast local iteration without containers.

---

## Path Handling Policy (Critical)

All persisted paths **must be relative** to the workspace root.

✅ Correct:

```json
{ "path": "omnibioai/work/results/run_001" }
```

❌ Incorrect:

```json
{ "path": "/home/manish/Desktop/machine/omnibioai/..." }
```

This ensures Docker, HPC, and rename safety.

---

## Database Model

| Database    | Used By             |
| ----------- | ------------------- |
| `omnibioai` | OmniBioAI Workbench |
| `limsdb`    | LIMS-X              |

Single MySQL container, multiple logical databases.

---

## Quick Debug Commands

```bash
docker compose logs -f omnibioai
docker compose logs -f mysql
lsof -i :8000 :8080 :9090 :7000
```

---

## Status

✅ Clean workspace
✅ Docker + non-Docker parity
✅ Multi-database MySQL
✅ No absolute paths
✅ Production-leaning architecture

This repository acts as the **local control plane** for the OmniBioAI ecosystem.

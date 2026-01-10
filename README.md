# OmniBioAI Local Development Workspace

This repository defines a **local development workspace and orchestration layer** for the **OmniBioAI ecosystem**, including workflow execution, tool services, LIMS integration, and AI-driven bioinformatics applications.

All services are designed to run **locally**, **without mandatory cloud dependencies**, using a shared workspace layout and reproducible startup mechanisms.

> **Important**
>
> This repository does **not** vendor or embed application source code.
> Each major component lives in its **own GitHub repository** and is referenced here explicitly.

---

## Workspace Layout

```
Desktop/machine/
├── omnibioai/                 # OmniBioAI Workbench (Django)
├── omnibioai-tool-exec/       # TES – Tool Execution Service
├── omnibioai-toolserver/      # FastAPI ToolServer (Enrichr, BLAST, etc.)
├── lims-x/                    # LIMS-X (Laboratory Information Management)
├── ragbio/                    # RAG-based Bioinformatics Assistant
├── utils/
│   └── kill_port.sh           # Utility to free busy ports
├── smoke_test_stack.sh        # Health checks for the full stack
├── start_stack_tmux.sh        # One-command stack launcher (tmux)
├── db-init/                   # MySQL init dumps (omnibioai + limsdb)
│   ├── omnibioai.sql
│   └── limsdb.sql
├── docker-compose.yml         # Full local stack (Docker Compose)
├── backup/                    # Archived / experimental work
└── ai-dev-docker/             # Docker experiments (optional)
```

---

## Canonical Repositories

Each service must be cloned independently. This workspace assumes the following repositories:

| Component                        | Repository                                                                                         |
| -------------------------------- | -------------------------------------------------------------------------------------------------- |
| **OmniBioAI Workbench**          | [https://github.com/man4ish/omnibioai](https://github.com/man4ish/omnibioai)                       |
| **Tool Execution Service (TES)** | [https://github.com/man4ish/omnibioai-tool-exec](https://github.com/man4ish/omnibioai-tool-exec)   |
| **ToolServer**                   | [https://github.com/man4ish/omnibioai-toolserver](https://github.com/man4ish/omnibioai-toolserver) |
| **LIMS-X**                       | [https://github.com/man4ish/lims-x](https://github.com/man4ish/lims-x)                             |
| **RAGBio**                       | [https://github.com/man4ish/ragbio](https://github.com/man4ish/ragbio)                             |

This repository **only orchestrates** these projects; it does not replace them.

---

## Design Principles

* **Single workspace root**
* **Relative paths only** in registries and metadata
* **No hardcoded absolute paths**
* **Service isolation via ports**
* **Restart-safe startup**
* **Docker + non-Docker parity**

This makes the workspace:

* Portable across machines
* Safe to rename or relocate
* Suitable for Docker, HPC, or VM environments
* Stable across long-running research workflows

---

## Services & Ports

| Service             | Repo                   | Default Port | Description                |
| ------------------- | ---------------------- | ------------ | -------------------------- |
| OmniBioAI Workbench | `omnibioai`            | `8000`       | Django UI, plugins, agents |
| TES                 | `omnibioai-tool-exec`  | `8080`       | Workflow & tool execution  |
| ToolServer          | `omnibioai-toolserver` | `9090`       | FastAPI tool APIs          |
| LIMS-X              | `lims-x`               | `7000`       | LIMS integration           |
| MySQL               | shared                 | `3306`       | omnibioai + limsdb         |
| Redis               | shared                 | `6379`       | Celery, channels           |

All ports are configurable via environment variables.

---

## Docker-Based Workflow (Recommended)

### 1. Build All Docker Images

From the workspace root:

```bash
docker compose build
```

This builds:

* `omnibioai-workbench`
* `omnibioai-toolserver`
* `omnibioai-tes`
* `lims-x`
* MySQL + Redis (official images)

Each service maintains its **own Dockerfile in its own repo**.

---

### 2. Export Existing Databases (One-Time)

If you already have local MySQL databases, export them:

```bash
# OmniBioAI database
mysqldump -u root -p omnibioai > db-init/omnibioai.sql

# LIMS-X database
mysqldump -u root -p limsdb > db-init/limsdb.sql
```

These dumps are **automatically imported** by MySQL when Docker Compose starts.

> ⚠️ This happens **only on first startup** or when volumes are removed.

---

### 3. Start the Full Stack (Docker Compose)

```bash
docker compose up
```

Or rebuild everything cleanly:

```bash
docker compose down -v
docker compose up --build
```

This launches:

* MySQL (with `omnibioai` + `limsdb`)
* Redis
* ToolServer
* TES
* OmniBioAI Workbench
* LIMS-X

---

### 4. Verify Health

```bash
curl http://localhost:9090/health   # ToolServer
curl http://localhost:8080/health   # TES
curl http://localhost:8000/         # OmniBioAI
curl http://localhost:7000/         # LIMS-X
```

---

## One-Command Startup (Non-Docker)

For local development without containers:

```bash
bash start_stack_tmux.sh
```

This:

1. Frees required ports
2. Creates a `tmux` session
3. Starts all services directly
4. Runs smoke tests

Attach:

```bash
tmux attach -t omnibioai
```

---

## Path Handling Policy (Critical)

All persisted paths **must be relative** to the workspace root.

✅ Correct:

```json
{
  "path": "omnibioai/work/results/run_001"
}
```

❌ Incorrect:

```json
{
  "path": "/home/manish/Desktop/machine/omnibioai/..."
}
```

This guarantees:

* Docker compatibility
* HPC compatibility
* Repo rename safety
* Stable provenance tracking

---

## Database Model

A **single MySQL container** hosts **multiple logical databases**:

| Database    | Used By             |
| ----------- | ------------------- |
| `omnibioai` | OmniBioAI Workbench |
| `limsdb`    | LIMS-X              |

No cross-contamination, no duplicate containers.

---

## Repository Renaming Notes (Historical)

| Old Name                       | New Name    |
| ------------------------------ | ----------- |
| `omnibioai_workbench`          | `omnibioai` |
| `LIMS-X`                       | `lims-x`    |
| `rag-gene-discovery-assistant` | `ragbio`    |

All internal references have been updated.

---

## Quick Debug Commands

```bash
# Ports
lsof -i :8000
lsof -i :8080
lsof -i :9090
lsof -i :7000

# Docker logs
docker compose logs -f omnibioai
docker compose logs -f mysql

# Reset everything
docker compose down -v
docker compose up --build
```

---

## Status

✅ Clean workspace
✅ Docker + non-Docker parity
✅ Multi-database MySQL
✅ No absolute paths
✅ Production-leaning architecture

This repository acts as the **local control plane** for the OmniBioAI ecosystem.

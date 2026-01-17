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

![Architecture](ecosystem.png)

---

## Canonical Repositories

Each component must be cloned independently.

| Component                        | Repository                                                                                                     |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **OmniBioAI Workbench**          | [https://github.com/man4ish/omnibioai](https://github.com/man4ish/omnibioai)                                   |
| **Tool Execution Service (TES)** | [https://github.com/man4ish/omnibioai-tool-exec](https://github.com/man4ish/omnibioai-tool-exec)               |
| **ToolServer**                   | [https://github.com/man4ish/omnibioai-toolserver](https://github.com/man4ish/omnibioai-toolserver)             |
| **LIMS (OmniBioAI-LIMS)**        | [https://github.com/man4ish/omnibioai-lims](https://github.com/man4ish/omnibioai-lims)                         |
| **RAG Service (OmniBioAI-RAG)**  | [https://github.com/man4ish/omnibioai-rag](https://github.com/man4ish/omnibioai-rag)                           |
| **Workflow Bundles**             | [https://github.com/man4ish/omnibioai-workflow-bundles](https://github.com/man4ish/omnibioai-workflow-bundles) |
| **OmniBioAI SDK**                | [https://github.com/man4ish/omnibioai_sdk](https://github.com/man4ish/omnibioai_sdk)                           |

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
| OmniBioAI-LIMS      | 7000         | LIMS integration           |
| MySQL               | 3306         | omnibioai + limsdb         |
| Redis               | 6379         | Celery, Channels           |

All ports are configurable via `.env`.

---

## Status

✅ Clean workspace
✅ Docker + non-Docker parity
✅ Multi-database MySQL
✅ No absolute paths
✅ Production-leaning architecture

This repository acts as the **local control plane** for the OmniBioAI ecosystem.


# OmniBioAI Control Center

## Local Development, Orchestration & Deployment Plane

This repository defines the **OmniBioAI Control Center** — the orchestration, deployment, and operational control plane of the OmniBioAI ecosystem.

OmniBioAI is a **reproducible scientific execution and reasoning platform** designed to run consistently across:

* Local machines
* On-prem servers
* HPC environments
* Cloud infrastructure

With **no mandatory cloud dependencies**.

This repository does **not** embed bioinformatics algorithms or core application logic.
Instead, it assembles independently versioned OmniBioAI components into a **single runnable, production-grade ecosystem**.

> Think of this repository as the operational brain and runtime assembly layer of OmniBioAI.

---

# What Is the OmniBioAI Control Center?

The Control Center is responsible for:

* Service orchestration
* Environment configuration
* Runtime boundaries
* Cross-service wiring
* Health checks and dependency contracts
* Persistence management
* Deployment portability (local ↔ HPC ↔ cloud)

It defines how OmniBioAI runs — not what each component internally implements.

It is the **control plane** of the ecosystem.

---

# Architectural Positioning

OmniBioAI follows a **multi-plane architecture**:

### 1. Control Plane (This Repository)

* Django Workbench
* Model Registry
* Tool Execution Service (TES)
* ToolServer
* LIMS
* Metadata databases
* Object and artifact governance
* API boundaries
* Health contracts

These services are:

* Long-lived
* Stateful
* Restart-safe
* Governance-aware

---

### 2. Compute Plane

* Workflow runners (WDL, Nextflow, Snakemake, CWL)
* Tool runtime containers
* HPC adapters
* Slurm execution
* Kubernetes jobs
* Cloud batch adapters

These services are:

* Ephemeral
* Replaceable
* Execution-only

TES is the strict boundary between control and compute planes.

---

### 3. Data Plane

* OmniObjects
* Model artifacts
* Workflow outputs
* Versioned bundles
* Datasets

---

### 4. AI Plane

* RAG services
* LLM reasoning
* Agent orchestration
* Scientific interpretation layers

---

# Who This Repository Is For

This repository is intended for:

* Core OmniBioAI developers
* Infrastructure engineers
* HPC administrators
* Enterprise deployment teams
* Regulated or air-gapped environments
* Power users running full stacks locally

It is **not required** for:

* Plugin-only development
* SDK-only usage
* Users consuming hosted OmniBioAI

---

# Workspace Layout

```text
Desktop/machine/
├── omnibioai/                     # Workbench (Django platform)
├── omnibioai-tes/                 # Tool Execution Service
├── omnibioai-toolserver/          # FastAPI ToolServer
├── omnibioai-model-registry/      # Model registry service
├── omnibioai-lims/                # LIMS
├── omnibioai-rag/                 # RAG & LLM services
├── omnibioai_sdk/                 # Python SDK
├── omnibioai-workflow-bundles/    # Engine-agnostic workflows
│
├── deploy/
│   ├── compose/                   # Canonical Docker Compose
│   ├── scripts/                   # Bootstrap utilities
│   ├── bundle/                    # Offline bundles
│   ├── hpc/                       # Apptainer assets
│   └── k8s/                       # Kubernetes (in progress)
│
├── data/
├── work/
├── tmpdata/
├── out/
├── local_registry/
│
├── db-init/
├── utils/
├── images/
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# Canonical Runtime Services

| Service                      | Port | Role                         |
| ---------------------------- | ---- | ---------------------------- |
| OmniBioAI Workbench          | 8000 | UI, plugins, agents          |
| Tool Execution Service (TES) | 8081 | Workflow orchestration       |
| ToolServer                   | 9090 | Tool APIs                    |
| Model Registry               | 8095 | Versioned ML artifacts       |
| LIMS                         | 7000 | Sample & metadata management |
| MySQL                        | 3306 | Databases                    |
| Redis                        | 6379 | Celery & caching             |

All ports are configurable via `.env`.

---

# Key Capabilities of the Control Center

### 1. Deterministic Multi-Service Orchestration

* Ordered startup with health checks
* Restart-safe dependency management
* Strict port contracts
* Environment-based configuration

---

### 2. Model Governance Layer

* Model versioning
* Alias promotion
* Artifact verification
* Reproducibility metadata
* Strict package validation

---

### 3. HPC Compatibility

Supports execution on:

* Slurm clusters
* Apptainer / Singularity environments
* Non-root HPC nodes

Control plane can remain external while compute runs on HPC.

---

### 4. Cloud Parity

OCI-compliant images allow deployment to:

* AWS Batch
* Azure Batch
* Kubernetes
* On-prem Docker

Design goal: **parity across environments**

---

### 5. Offline / Air-Gapped Deployment

This repository supports:

* Prebuilt Docker image bundles
* Volume snapshots
* Seeded databases
* Fully offline installation

Suitable for:

* Regulated research labs
* Secure enterprise networks
* Hospital environments

---

# Local Deployment

### Prerequisites

* Docker Engine or Docker Desktop
* Docker Compose v2+

### Start Full Stack

```bash
cp deploy/compose/.env.example deploy/compose/.env
docker compose \
  --project-directory . \
  --env-file deploy/compose/.env \
  -f deploy/compose/docker-compose.yml \
  up -d
```

### Verify Services

```bash
curl http://127.0.0.1:8000
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8095/health
```

---

# Operational Modes

| Mode      | Control Plane  | Compute Plane     |
| --------- | -------------- | ----------------- |
| Local dev | Docker Compose | Local Docker      |
| On-prem   | Docker Compose | Docker / TES      |
| HPC       | External VM    | Apptainer via TES |
| Hybrid    | VM             | HPC + TES         |
| Cloud     | Kubernetes     | Kubernetes        |

---

# Design Principles

* Single workspace root
* No absolute paths
* Strict service boundaries
* Control plane ≠ compute plane
* Restart-safe orchestration
* Container-native design
* Environment-driven configuration
* No forced cloud dependencies

---

# What This Repository Does Not Do

* Does not contain bioinformatics algorithms
* Does not vendor component repositories
* Does not enforce a single workflow engine
* Does not hide execution behind opaque AI calls
* Does not require external SaaS services

---

# Strategic Role in the Ecosystem

OmniBioAI components are independently versioned repositories.

This repository:

* Assembles them
* Wires them
* Runs them
* Governs them
* Deploys them

It is the **operational control boundary** of OmniBioAI.

---

# Current Status

* Multi-service orchestration stable
* Model Registry integrated
* TES integrated
* ToolServer integrated
* LIMS integrated
* Offline-ready structure
* HPC-aware architecture
* Kubernetes preparation underway

---

# Final Positioning

This repository is:

> The OmniBioAI Control Center — the orchestration, deployment, and runtime control plane of the OmniBioAI ecosystem.

It defines how the ecosystem runs, scales, and moves across environments — while preserving strict reproducibility and architectural boundaries.

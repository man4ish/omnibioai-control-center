# OmniBioAI Deployment Guide

This document describes how to deploy the **OmniBioAI ecosystem** across different environments — **local machines, servers, HPC clusters, and cloud platforms** — using containerized, dependency-free workflows.

OmniBioAI is designed to be **portable, reproducible, and infrastructure-agnostic**, with Docker/OCI images as the primary distribution unit and optional support for Apptainer/Singularity and Kubernetes.

---

## Design Goals

* **Zero local software dependency** beyond a container runtime
* **Consistent deployment** across local, HPC, and cloud
* **Offline / air-gapped support**
* **Separation of control plane and compute plane**
* **Pluggable execution backends** (local, HPC schedulers, Kubernetes)
* **Future-proof for enterprise and multi-tenant use**

---

## Current Deployment Architecture (v1)

At present, OmniBioAI is deployed as a **Docker Compose–based ecosystem** consisting of multiple services:

### Core Services

* `omnibioai` – Main web UI & API (Django)
* `omnibioai-toolserver` – Tool registry & metadata service
* `omnibioai-tes` – Tool Execution Service (TES)
* `omnibioai-workflow-service` – Workflow registry & runner
* `omnibioai-rag` – RAG & LLM-backed knowledge services
* `omnibioai-lims` – LIMS and data management components

### Infrastructure Services

* MySQL (metadata, registries)
* Redis (async tasks, caching)
* Ollama (local LLM backend)
* Optional: Celery workers, Jupyter, auxiliary services

All services are containerized and orchestrated via Docker Compose.

---

## Supported Environments (Current)

| Environment               | Status            | Notes                          |
| ------------------------- | ----------------- | ------------------------------ |
| Local workstation         | ✅ Fully supported | Docker / Docker Compose        |
| Single server (on-prem)   | ✅ Fully supported | Same as local                  |
| Offline / air-gapped      | ✅ Supported       | Via bundled images & volumes   |
| HPC (login/compute nodes) | ⚠️ Partial        | Apptainer for compute services |
| Cloud VM                  | ✅ Supported       | Docker-based                   |
| Kubernetes                | ⚠️ Early          | Helm manifests in progress     |

---

## Local / Server Deployment (Online)

### Prerequisites

* Docker Engine or Docker Desktop
* Docker Compose v2+

### Steps

```bash
cp deploy/compose/.env.example deploy/compose/.env
cd deploy/compose
docker compose up -d
```

### Optional: Pull LLM model

```bash
docker compose exec ollama ollama pull llama3:8b
```

---

## Offline / Air-Gapped Deployment

OmniBioAI supports **fully offline deployment**, including LLM models.

### Offline Bundle Contents

* Pre-built Docker images (`*.tar`)
* Docker Compose file
* Environment template
* Pre-seeded volumes (optional):

  * Ollama model cache
  * Database snapshot
  * Object store seed

### Install on Target Machine

```bash
./install.sh
docker compose --env-file .env up -d
```

This requires **no internet access** after installation.

---

## HPC Deployment (Apptainer / Singularity)

HPC environments typically restrict Docker. OmniBioAI supports HPC by running **compute services** via Apptainer while keeping the control plane external.

### Typical HPC Pattern

* Control plane (UI, DB, registry): local server / cloud / VM
* Compute plane (tool execution, workflow runners): HPC nodes

### Supported on HPC

* `omnibioai-tes`
* Workflow executors
* Optional: LLM inference (site dependent)

### Apptainer Build

```bash
apptainer build omnibioai-tes.sif docker://man4ish/omnibioai-tes:latest
```

### Run on HPC

```bash
apptainer run omnibioai-tes.sif
```

This enables **scheduler-native execution** (Slurm / PBS / SGE) while preserving reproducibility.

---

## Kubernetes Deployment (Experimental)

Kubernetes support is under active development.

### Current Status

* OCI images are Kubernetes-compatible
* Basic Helm chart structure exists
* Stateful components require PVC configuration

### Planned Capabilities

* Helm-based installation
* Horizontal scaling of compute services
* GPU-aware LLM and workflow execution
* Multi-tenant isolation

---

## Environment Configuration

All deployments are driven by environment variables defined in `.env`.

Key categories:

* Service URLs
* Database credentials
* Storage locations
* Execution backend selection
* LLM backend configuration

This ensures **the same images run everywhere**, with only configuration changes.

---

## Execution Backends

OmniBioAI is designed with **pluggable execution targets**:

### Current

* Local Docker execution
* TES-based tool execution
* Workflow engines (WDL, Nextflow, Snakemake, CWL)

### Planned

* Native Slurm / PBS / SGE adapters
* Kubernetes Jobs
* Remote execution nodes
* Hybrid local + HPC execution

---

## Future Enhancements (Roadmap)

### Deployment & Infrastructure

* Unified installer (`omnibioai install`)
* Single-node “appliance” mode
* Signed release bundles
* Automated health checks & recovery
* Secrets management integration

### HPC & Scale

* Full scheduler integration (Slurm/PBS/SGE)
* Distributed workflow execution
* Data-local execution strategies
* Compute autoscaling (cloud + HPC)

### Kubernetes

* Production-ready Helm charts
* Operator-based lifecycle management
* Multi-tenant namespaces
* Observability (Prometheus/Grafana)

### LLM & AI Runtime

* Backend-agnostic LLMService
* Support for vLLM / TGI / llama.cpp
* GPU sharing & batching
* Model registry & versioning

---

## Deployment Philosophy

> **Build once, run anywhere.**

OmniBioAI treats container images as immutable, portable artifacts and separates **infrastructure concerns from scientific logic**.

Whether running on a laptop, an HPC cluster, or a cloud platform, the same workflows, tools, and AI services behave identically.

---

## Support & Contributions

* Issues and deployment questions: GitHub Issues
* Contributions welcome for:

  * Kubernetes support
  * HPC adapters
  * CI/CD automation
  * Packaging & installers


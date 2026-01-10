# OmniBioAI Local Development Workspace

This workspace hosts the full **OmniBioAI ecosystem**, including workflow execution, tool services, LIMS integration, and AI-driven bioinformatics applications.
All services are designed to run **locally**, **without cloud dependencies**, using a shared workspace and reproducible startup scripts.

---

## Workspace Layout

```
Desktop/machine/
├── omnibioai/                 # Main Django-based OmniBioAI Workbench
├── omnibioai-tool-exec/       # TES (Tool Execution Service)
├── omnibioai-toolserver/      # FastAPI ToolServer (Enrichr, BLAST, etc.)
├── lims-x/                    # LIMS-X (Laboratory Information Management)
├── ragbio/                    # RAG-based Gene Discovery / Knowledge Assistant
├── utils/
│   └── kill_port.sh           # Utility to free busy ports
├── smoke_test_stack.sh        # Health checks for the full stack
├── start_stack_tmux.sh        # One-command stack launcher (tmux)
├── backup/                    # Archived / experimental work
└── ai-dev-docker/             # Docker experiments (optional)
```

---

## Design Principles

* **Single workspace root**
* **Relative paths only** in registries and metadata
* **No hardcoded absolute paths**
* **Service isolation via ports**
* **tmux-managed lifecycle**
* **Restart-safe (ports auto-killed)**

This allows the workspace to be:

* Moved to another machine
* Mounted into Docker
* Deployed on HPC
* Versioned safely

---

## Services & Ports

| Service                      | Repo                   | Port   | Description                              |
| ---------------------------- | ---------------------- | ------ | ---------------------------------------- |
| OmniBioAI Workbench          | `omnibioai`            | `8000` | Django UI, plugins, registry             |
| TES (Tool Execution Service) | `omnibioai-tool-exec`  | `8080` | Workflow & tool execution                |
| ToolServer                   | `omnibioai-toolserver` | `9090` | FastAPI tool APIs (Enrichr, BLAST, etc.) |
| LIMS-X                       | `lims-x`               | `7000` | LIMS integration (placeholder for now)   |

All ports are configurable via environment variables.

---

## One-Command Startup (Recommended)

Start **everything** with:

```bash
bash start_stack_tmux.sh
```

What this does:

1. Kills any process using required ports
2. Creates a fresh tmux session
3. Starts:

   * TES
   * ToolServer (via `uvicorn`)
   * OmniBioAI Workbench
   * LIMS-X placeholder
4. Runs smoke tests automatically

Attach to the session:

```bash
tmux attach -t omnibioai
```

---

## tmux Window Layout

| Window       | Purpose                |
| ------------ | ---------------------- |
| `tes`        | Tool Execution Service |
| `toolserver` | FastAPI ToolServer     |
| `limsx`      | LIMS-X (stub / future) |
| `workbench`  | Django OmniBioAI       |
| `smoke`      | Health checks          |

Each service runs independently and can be restarted without affecting others.

---

## Startup Script (start_stack_tmux.sh)

Key behaviors:

* Uses `utils/kill_port.sh` to avoid port conflicts
* Fully restartable
* Supports environment overrides:

```bash
TES_PORT=8081 WORKBENCH_PORT=9000 bash start_stack_tmux.sh
```

---

## Health & Smoke Tests

After startup, `smoke_test_stack.sh` verifies:

* TES `/health`
* ToolServer `/health`
* OmniBioAI root page
* Core APIs reachable

You can run it manually:

```bash
bash smoke_test_stack.sh
```

---

## Path Handling Policy (Important)

All **stored paths** in OmniBioAI and LIMS-X must be:

✅ Relative to workspace root
❌ Absolute paths like `/home/manish/...`

Example (correct):

```json
{
  "path": "omnibioai/work/results/run_001"
}
```

Resolution happens at runtime via the workspace root.

This guarantees:

* Portability
* Docker compatibility
* No broken registries after renames

---

## Repo Renaming Notes (Historical)

The following renames were performed cleanly (local + remote):

| Old                            | New         |
| ------------------------------ | ----------- |
| `omnibioai_workbench`          | `omnibioai` |
| `LIMS-X`                       | `lims-x`    |
| `rag-gene-discovery-assistant` | `ragbio`    |

All references were updated to avoid legacy paths.

---

## How This Workspace Is Meant to Be Used

* **Development**: local iteration on plugins, tools, AI agents
* **Integration**: LIMS-X ↔ OmniBioAI ↔ ToolServer
* **Execution**: TES handles real workflows
* **AI augmentation**: RAGBio + Agentic workflows
* **Future**:

  * Docker Compose
  * Kubernetes
  * HPC deployment

---

## Quick Debug Commands

```bash
# Check ports
lsof -i :8000
lsof -i :8080
lsof -i :9090

# Restart everything
bash start_stack_tmux.sh

# Attach to logs
tmux attach -t omnibioai
```

---

## Status

✅ Codebase clean
✅ No hardcoded absolute paths
✅ Services isolated
✅ Fully reproducible local stack

This workspace is now **production-grade for local + research environments**.

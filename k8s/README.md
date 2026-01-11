# Migrating omnibioai Docker Compose → Kubernetes (Work in Progress)
Date started: January 11, 2026  
Machine: spark-70f0 (ARM64 / aarch64)  
Goal: Convert existing docker-compose.yml to Kubernetes manifests

## Current Status (Jan 11, 2026 evening)
- kompose successfully converted the compose file
- Generated files are in: `~/Desktop/machine/k8s/`
- Main problem identified: `mysql-cm1-configmap.yaml` is ~552 kB → contains all files from `./db-init/` as base64 → **bad practice**
- Shared `workspace` volume is currently one PVC → good start, but mounts need checking/fixing

## Files Overview

├── mysql-deployment.yaml
├── mysql-data-persistentvolumeclaim.yaml
├── mysql-cm1-configmap.yaml          ← DELETE or ignore this monster (552kB)
├── redis-deployment.yaml
├── toolserver-deployment.yaml
├── tes-deployment.yaml
├── omnibioai-deployment.yaml
├── lims-x-deployment.yaml
├── workspace-persistentvolumeclaim.yaml   ← shared /workspace PVC – important!
├── tes-service.yaml
├── omnibioai-service.yaml
└── lims-x-service.yaml

## What Still Needs Fixing (high priority)

1. **MySQL init scripts**  
   Current: Kompose turned ./db-init/ into huge ConfigMap → don't use it!  
   Recommended solutions (choose one):
   - Best: Build custom MySQL image with init scripts baked in
     ```dockerfile
     # Dockerfile.mysql
     FROM mysql:8.0
     COPY ./db-init /docker-entrypoint-initdb.d/

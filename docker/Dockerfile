FROM python:3.12-slim

WORKDIR /app

# Keep image small + deterministic
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install runtime deps (paths are relative to build context: repo root)
COPY deploy/control-center/backend/pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir .

# Copy source (paths are relative to build context: repo root)
COPY deploy/control-center/backend/src /app/src

ENV PYTHONPATH=/app/src

EXPOSE 7070

CMD ["uvicorn", "control_center.main:app", "--host", "0.0.0.0", "--port", "7070"]

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System packages: cloc for code counting
RUN apt-get update && \
    apt-get install -y --no-install-recommends cloc && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir pandas

# Copy source
COPY backend/src /app/src

ENV PYTHONPATH=/app/src

EXPOSE 7070

CMD ["uvicorn", "control_center.main:app", "--host", "0.0.0.0", "--port", "7070"]

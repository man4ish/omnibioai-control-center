FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .

COPY omnibioai_control_center /app/omnibioai_control_center

CMD ["uvicorn", "omnibioai_control_center.app.main:app", "--host", "0.0.0.0", "--port", "8100"]

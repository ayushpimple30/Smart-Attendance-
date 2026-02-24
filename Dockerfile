FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY gunicorn_conf.py ./gunicorn_conf.py
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

RUN chown -R appuser:appuser /app /opt/venv
USER appuser

EXPOSE 8000

CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-c", "gunicorn_conf.py"]

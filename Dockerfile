FROM python:3.12-slim

WORKDIR /app

# Système deps pour grpc/cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

ENV PYTHONUNBUFFERED=1

# Cloud Run lance ce processus une fois par cycle (--once)
# Cloud Scheduler déclenche HTTP → ici on lance le bot via flask micro-serveur
COPY scripts/cloud_run_entry.py ./
EXPOSE 8080
CMD ["python", "cloud_run_entry.py"]

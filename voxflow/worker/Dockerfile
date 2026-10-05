FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng ffmpeg curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY voxflow/worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch
RUN pip install --no-cache-dir -r /tmp/worker-requirements.txt

COPY scripts /app/scripts
COPY voxflow /app/voxflow

CMD ["sh","-c","uvicorn voxflow.worker.app:app --host 0.0.0.0 --port ${PORT:-8080}"]

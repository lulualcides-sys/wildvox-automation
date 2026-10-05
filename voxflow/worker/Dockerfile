FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng ffmpeg curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY voxflow/worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/worker-requirements.txt

COPY scripts /app/scripts
COPY voxflow /app/voxflow

CMD ["python","-m","voxflow.worker.worker"]

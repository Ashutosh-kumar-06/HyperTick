FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY consumer/pyproject.toml .
COPY consumer/src/ src/
COPY worker/include/ /app/worker/include/

RUN pip install --no-cache-dir .

CMD ["swarm-consumer"]

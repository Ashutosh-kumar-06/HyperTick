FROM python:3.11-slim

WORKDIR /app

COPY orchestrator/pyproject.toml .
COPY orchestrator/src/ src/

RUN pip install --no-cache-dir .

CMD ["swarm-run"]

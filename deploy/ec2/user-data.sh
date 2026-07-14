#!/usr/bin/env bash
# EC2 bootstrap for horizontal consumer scaling
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y docker.io docker-compose-plugin git

systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu || true

APP_DIR=/opt/trading-swarm
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Clone or sync project (override REPO_URL via user-data)
REPO_URL="${REPO_URL:-}"
if [[ -n "$REPO_URL" ]]; then
  git clone "$REPO_URL" .
fi

cp .env.example .env

# Build worker image once per host
docker build -f worker/Dockerfile -t trading-swarm-worker:latest .

# Scale consumers via compose overlay
CONSUMER_REPLICAS="${CONSUMER_REPLICAS:-5}"
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d \
  rabbitmq redis mongodb

docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d \
  --scale consumer="$CONSUMER_REPLICAS" consumer

echo "Trading swarm cluster ready with $CONSUMER_REPLICAS consumer replicas"

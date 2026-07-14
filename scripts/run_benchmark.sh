#!/usr/bin/env bash
# Run 2M ticks/sec benchmark against an Arrow dataset
set -euo pipefail

DATASET="${1:-data/sample_spy_ticks.arrow}"
BATCH="${2:-4096}"
MIN_TPS="${3:-2000000}"

if [[ ! -f "$DATASET" ]]; then
  echo "Dataset not found: $DATASET"
  echo "Generate with: python scripts/generate_sample_data.py -n 2000000"
  exit 1
fi

docker build -f worker/Dockerfile -t trading-swarm-worker:latest . >/dev/null

docker run --rm \
  -v "$(pwd)/data:/data:ro" \
  --entrypoint /usr/local/bin/swarm_benchmark \
  trading-swarm-worker:latest \
  "/data/$(basename "$DATASET")" "$BATCH" "$MIN_TPS"

#!/usr/bin/env bash
# REQ-3.4: Ephemeral compilation of agent-generated strategy into .so
set -euo pipefail

STRATEGY_SRC="${1:?strategy source path required}"
OUTPUT_SO="${2:?output .so path required}"
INCLUDE_DIR="${3:-/app/include}"

g++ -O3 -shared -fPIC -std=c++20 \
    -I"${INCLUDE_DIR}" \
    "${STRATEGY_SRC}" \
    -o "${OUTPUT_SO}"

echo "Compiled strategy -> ${OUTPUT_SO}"

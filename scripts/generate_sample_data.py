#!/usr/bin/env python3
"""Generate a sample Arrow tick dataset for integration testing."""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow as pa
import pyarrow.ipc as ipc
import numpy as np


def generate(output: Path, n_ticks: int = 50_000, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    price = 450.0
    timestamps = np.arange(n_ticks, dtype=np.int64) * 1_000_000_000
    bids, asks, lasts, volumes = [], [], [], []

    for _ in range(n_ticks):
        price += rng.normal(0, 0.05)
        spread = 0.01
        bids.append(price - spread / 2)
        asks.append(price + spread / 2)
        lasts.append(price)
        volumes.append(int(rng.integers(100, 10_000)))

    table = pa.table({
        "timestamp_ns": timestamps,
        "bid": pa.array(bids, type=pa.float64()),
        "ask": pa.array(asks, type=pa.float64()),
        "last": pa.array(lasts, type=pa.float64()),
        "volume": pa.array(volumes, type=pa.int64()),
    })

    output.parent.mkdir(parents=True, exist_ok=True)
    with ipc.new_file(str(output), table.schema) as writer:
        writer.write_table(table)

    print(f"Wrote {n_ticks} ticks to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", type=Path, default=Path("data/sample_spy_ticks.arrow"))
    parser.add_argument("-n", "--num-ticks", type=int, default=50_000)
    parser.add_argument("--large", action="store_true", help="Generate 2M ticks for benchmark")
    args = parser.parse_args()
    n_ticks = 2_000_000 if args.large else args.num_ticks
    generate(args.output, n_ticks)

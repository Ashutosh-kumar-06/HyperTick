#!/usr/bin/env python3
"""Ingest real tick data (CSV / Parquet) into Arrow IPC format for the C++ engine."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

CANONICAL_COLUMNS = ("timestamp_ns", "bid", "ask", "last", "volume")

# Common vendor column aliases → canonical names
COLUMN_ALIASES: dict[str, str] = {
    "timestamp": "timestamp_ns",
    "ts": "timestamp_ns",
    "time": "timestamp_ns",
    "datetime": "timestamp_ns",
    "date": "timestamp_ns",
    "bid_price": "bid",
    "ask_price": "ask",
    "price": "last",
    "close": "last",
    "last_price": "last",
    "size": "volume",
    "qty": "volume",
    "quantity": "volume",
}


def _normalize_columns(table: pa.Table) -> pa.Table:
    rename_map = {}
    for col in table.column_names:
        key = col.strip().lower()
        if key in COLUMN_ALIASES:
            rename_map[col] = COLUMN_ALIASES[key]
        elif key in CANONICAL_COLUMNS:
            rename_map[col] = key
    if rename_map:
        table = table.rename_columns([rename_map.get(c, c) for c in table.column_names])

    for required in CANONICAL_COLUMNS:
        if required not in table.column_names:
            raise ValueError(f"Missing required column '{required}'. Found: {table.column_names}")

    # Coerce timestamp to nanoseconds int64
    ts = table.column("timestamp_ns")
    if pa.types.is_timestamp(ts.type):
        ts_col = pc.cast(ts, pa.int64())
    elif pa.types.is_string(ts.type) or pa.types.is_large_string(ts.type):
        ts_col = pc.cast(pc.strptime(ts, format="%Y-%m-%d %H:%M:%S", unit="s"), pa.int64())
        ts_col = pc.multiply(ts_col, pa.scalar(1_000_000_000))
    else:
        ts_col = pc.cast(ts, pa.int64())
        sample = ts_col.slice(0, min(10, len(ts_col))).to_pylist()
        if sample and max(abs(v) for v in sample if v is not None) < 1_000_000_000_000:
            ts_col = pc.multiply(ts_col, pa.scalar(1_000_000_000))

    return pa.table({
        "timestamp_ns": ts_col,
        "bid": pc.cast(table.column("bid"), pa.float64()),
        "ask": pc.cast(table.column("ask"), pa.float64()),
        "last": pc.cast(table.column("last"), pa.float64()),
        "volume": pc.cast(table.column("volume"), pa.int64()),
    })


def load_source(path: Path) -> pa.Table:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pacsv.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pq.read_table(path)
    if suffix == ".arrow":
        with pa.memory_map(str(path), "r") as source:
            reader = ipc.open_file(source)
            return reader.read_all()
    raise ValueError(f"Unsupported format: {suffix}. Use .csv, .parquet, or .arrow")


def content_id(table: pa.Table, source: Path) -> str:
    digest = hashlib.sha256()
    digest.update(source.name.encode())
    digest.update(str(len(table)).encode())
    if len(table) > 0:
        for col in CANONICAL_COLUMNS:
            arr = table.column(col)
            digest.update(arr.to_string().encode())
    return digest.hexdigest()[:16]


def write_arrow(table: pa.Table, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ipc.new_file(str(output), table.schema) as writer:
        writer.write_table(table)


def register_index(index_path: Path, dataset_id: str, meta: dict) -> None:
    index: dict[str, dict] = {}
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    index[dataset_id] = meta
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")


def ingest(
    source: Path,
    output_dir: Path,
    dataset_id: str | None = None,
    register: bool = True,
) -> Path:
    table = load_source(source)
    table = _normalize_columns(table)
    table = table.sort_by([("timestamp_ns", "ascending")])

    ds_id = dataset_id or content_id(table, source)
    output = output_dir / f"{ds_id}.arrow"
    write_arrow(table, output)

    meta = {
        "dataset_id": ds_id,
        "source": str(source),
        "rows": len(table),
        "start_ts": int(table.column("timestamp_ns")[0].as_py()) if len(table) else 0,
        "end_ts": int(table.column("timestamp_ns")[-1].as_py()) if len(table) else 0,
        "arrow_path": str(output),
    }

    if register:
        register_index(output_dir / "index.json", ds_id, meta)

    print(json.dumps(meta, indent=2))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest real tick data into Arrow IPC format")
    parser.add_argument("source", type=Path, help="CSV, Parquet, or Arrow source file")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--dataset-id", type=str, default=None, help="Override content-hash dataset ID")
    parser.add_argument("--no-register", action="store_true")
    args = parser.parse_args()

    ingest(args.source, args.output_dir, args.dataset_id, register=not args.no_register)


if __name__ == "__main__":
    main()

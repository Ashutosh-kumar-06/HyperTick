# Autonomous Quantitative Trading Backtesting Swarm

**Version 1.0** — Ashutosh Kumar, July 2026

Stateful multi-agent AI swarm for autonomous strategy research, C++ code generation, and rigorous tick-level backtesting.

## Architecture

```
LangGraph Orchestrator (Python) ──CRDT state──► Redis
    │  publish task (JSON)
    ▼
RabbitMQ (trading_swarm_exchange)
    │  backtest_tasks queue  ◄── N consumer replicas (EC2)
    ▼
Docker Sandbox C++ Worker (Columnar Arrow + SIMD)
    │  publish metrics
    ▼
RabbitMQ → Evaluator → Reflection loop
```

## Quick Start

### 1. Infrastructure

```bash
cp .env.example .env
docker compose up -d rabbitmq redis mongodb
```

### 2. Sample / Real Data

```bash
# Synthetic data
pip install -r scripts/requirements-ingest.txt
python scripts/generate_sample_data.py -n 2000000

# Real tick data (CSV / Parquet → Arrow)
python scripts/ingest_ticks.py path/to/ticks.csv -o data
# Dataset ID is content-hashed; listed in data/index.json
```

### 3. Build C++ Worker + Benchmark

```bash
docker build -f worker/Dockerfile -t trading-swarm-worker:latest .

# 2M ticks/sec benchmark (REQ-5.1)
bash scripts/run_benchmark.sh data/sample_spy_ticks.arrow 4096 2000000
```

### 4. LLM Providers

**OpenAI (default):**
```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
```

**Gemini:**
```bash
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.0-flash
GEMINI_API_KEY=...
```

### 5. Horizontal Scaling (EC2)

```bash
# Local: scale consumers
docker compose -f docker-compose.yml -f docker-compose.cluster.yml up -d --scale consumer=10

# EC2 bootstrap
sudo bash deploy/ec2/user-data.sh
```

Each consumer is stateless with `prefetch=1` for fair work distribution across replicas.

### 6. CRDT Distributed State

Enable for multi-node orchestrator deployments:

```bash
ENABLE_CRDT_SYNC=true
CRDT_NODE_ID=orchestrator-ec2-a
```

Uses LWW-Register, OR-Set, and G-Counter CRDTs in Redis for conflict-free merge across nodes.

### 7. Run Swarm

```bash
docker compose --profile full up -d consumer
cd orchestrator && pip install -e . && swarm-run --dataset <dataset_id>
```

## Performance Optimizations

| Technique | Location | Impact |
|-----------|----------|--------|
| Zero-copy SoA Arrow columns | `ColumnarTickStore` | Eliminates tick vector copy |
| Batch prefetch (4096 ticks) | `BacktestEngine` | L1/L2 cache warmth |
| AVX2 SIMD metrics | `SimdMetrics` | Fast Sharpe/variance post-processing |
| No-op benchmark mode | `swarm_benchmark` | Isolates loop throughput |
| Latency sampling stride | `EngineConfig` | Removes chrono overhead in prod |

## Requirements Traceability

| Req ID | Component | Location |
|--------|-----------|----------|
| REQ-1.1–1.4 | LangGraph + reflection | `orchestrator/src/swarm_orchestrator/` |
| REQ-2.1 | RabbitMQ exchange/queues | `broker/rabbitmq.py` |
| REQ-2.2 | Redis + CRDT state | `broker/redis_cache.py`, `broker/crdt_state.py` |
| REQ-3.1–3.4 | C++ event engine | `worker/` |
| REQ-5.1 | 2M ticks/sec benchmark | `swarm_benchmark`, `scripts/run_benchmark.sh` |
| REQ-5.2 | Sandbox isolation | `consumer/src/swarm_consumer/sandbox.py` |
| REQ-5.4 | Horizontal scaling | `docker-compose.cluster.yml`, `deploy/ec2/` |

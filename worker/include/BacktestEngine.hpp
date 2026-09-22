#pragma once

#include "ColumnarTickStore.hpp"
#include "OrderMatchingSimulator.hpp"
#include "StrategyInterface.hpp"

#include <chrono>
#include <dlfcn.h>
#include <memory>
#include <string>

namespace swarm {

struct EngineConfig {
    std::string dataset_path;
    std::string strategy_lib_path;
    double initial_capital{100'000.0};
    double commission_bps{1.0};
    double slippage_bps{0.5};
    size_t batch_size{ColumnarTickStore::kDefaultBatchSize};
    /// Sample per-tick latency every N ticks (0 = disable sampling for max throughput).
    size_t latency_sample_stride{1000};
    bool use_builtin_noop{false};
};

struct EngineResult {
    StrategyMetrics metrics;
    bool success{false};
    std::string error;
    double elapsed_ms{0.0};
    double ticks_per_second{0.0};
};

/// REQ-3.2: Monolithic event loop — Tick → Market → Strategy → Signal → OMS → Fill
class BacktestEngine {
public:
    explicit BacktestEngine(EngineConfig config);

    EngineResult run();

private:
    EngineConfig config_;
};

std::unique_ptr<StrategyInterface> load_strategy(const std::string& lib_path, std::string& error);

/// Run benchmark with built-in NoOp strategy (target: 2M ticks/sec).
EngineResult run_benchmark(const std::string& dataset_path, size_t batch_size = ColumnarTickStore::kDefaultBatchSize);

}  // namespace swarm

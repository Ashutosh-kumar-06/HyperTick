#include "BacktestEngine.hpp"
#include "NoOpStrategy.hpp"
#include "SimdMetrics.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <vector>

namespace swarm {

std::unique_ptr<StrategyInterface> load_strategy(const std::string& lib_path, std::string& error) {
    void* handle = dlopen(lib_path.c_str(), RTLD_NOW);
    if (!handle) {
        error = dlerror();
        return nullptr;
    }

    auto* factory = reinterpret_cast<StrategyInterface* (*)()>(dlsym(handle, "create_strategy"));
    if (!factory) {
        error = dlerror();
        dlclose(handle);
        return nullptr;
    }

    return std::unique_ptr<StrategyInterface>(factory());
}

namespace {

void build_returns(const std::vector<double>& equity, std::vector<double>& returns) {
    returns.clear();
    if (equity.size() < 2) {
        return;
    }
    returns.reserve(equity.size() - 1);
    for (size_t i = 1; i < equity.size(); ++i) {
        if (equity[i - 1] > 0) {
            returns.push_back((equity[i] - equity[i - 1]) / equity[i - 1]);
        }
    }
}

EngineResult finalize_result(
    StrategyInterface& strategy,
    OrderMatchingSimulator& oms,
    const ColumnarTickStore& store,
    double initial_capital,
    double elapsed_ms,
    std::vector<double>& latencies_us) {
    EngineResult result;

    auto metrics = strategy.finalize();
    metrics.ticks_processed = store.size();

    if (!latencies_us.empty()) {
        metrics.avg_latency_us =
            std::accumulate(latencies_us.begin(), latencies_us.end(), 0.0) /
            static_cast<double>(latencies_us.size());

        std::vector<double> sorted = latencies_us;
        std::sort(sorted.begin(), sorted.end());
        const size_t p99_idx = static_cast<size_t>(sorted.size() * 0.99);
        metrics.p99_latency_us = sorted[std::min(p99_idx, sorted.size() - 1)];
    }

    const auto& equity = oms.equity_curve();
    std::vector<double> returns;
    build_returns(equity, returns);
    if (!returns.empty()) {
        metrics.sharpe_ratio = SimdMetrics::compute_sharpe(returns);
        metrics.max_drawdown_pct = SimdMetrics::compute_max_drawdown(equity);
        metrics.total_return_pct =
            ((equity.back() - initial_capital) / initial_capital) * 100.0;
    }

    result.metrics = metrics;
    result.elapsed_ms = elapsed_ms;
    if (elapsed_ms > 0) {
        result.ticks_per_second = (static_cast<double>(store.size()) / elapsed_ms) * 1000.0;
    }
    result.success = true;
    return result;
}

}  // namespace

BacktestEngine::BacktestEngine(EngineConfig config) : config_(std::move(config)) {}

EngineResult BacktestEngine::run() {
    EngineResult result;

    ColumnarTickStore store(config_.dataset_path);
    if (!store.valid()) {
        result.error = "Failed to load Arrow dataset: " + config_.dataset_path;
        return result;
    }

    std::unique_ptr<StrategyInterface> owned_strategy;
    StrategyInterface* strategy = nullptr;

    if (config_.use_builtin_noop) {
        owned_strategy = std::make_unique<NoOpStrategy>();
        strategy = owned_strategy.get();
    } else {
        std::string load_error;
        owned_strategy = load_strategy(config_.strategy_lib_path, load_error);
        if (!owned_strategy) {
            result.error = "Failed to load strategy library: " + load_error;
            return result;
        }
        strategy = owned_strategy.get();
    }

    strategy->on_init(config_.initial_capital, config_.commission_bps, config_.slippage_bps);
    OrderMatchingSimulator oms(config_.commission_bps, config_.slippage_bps);

    const size_t batch = std::max(size_t{1}, config_.batch_size);
    const size_t stride = config_.latency_sample_stride;

    std::vector<double> latencies_us;
    if (stride > 0) {
        latencies_us.reserve(store.size() / stride + 1);
    }

    const auto t0 = std::chrono::steady_clock::now();

    for (size_t batch_start = 0; batch_start < store.size(); batch_start += batch) {
        const size_t batch_end = std::min(batch_start + batch, store.size());
        store.prefetch_batch(batch_end, batch);

        for (size_t i = batch_start; i < batch_end; ++i) {
            const bool sample = stride > 0 && (i % stride == 0);
            std::chrono::steady_clock::time_point tick_start;
            if (sample) {
                tick_start = std::chrono::steady_clock::now();
            }

            const Tick tick = store.tick_at(i);
            MarketEvent market{tick, i};
            auto signals = strategy->on_market(market);
            auto fills = oms.process_signals(signals, tick, tick.timestamp_ns);

            for (const auto& fill : fills) {
                strategy->on_fill(fill);
            }

            if (sample) {
                const auto tick_end = std::chrono::steady_clock::now();
                latencies_us.push_back(
                    std::chrono::duration<double, std::micro>(tick_end - tick_start).count());
            }
        }
    }

    const auto t1 = std::chrono::steady_clock::now();
    const double elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    return finalize_result(*strategy, oms, store, config_.initial_capital, elapsed_ms, latencies_us);
}

EngineResult run_benchmark(const std::string& dataset_path, size_t batch_size) {
    EngineConfig config;
    config.dataset_path = dataset_path;
    config.use_builtin_noop = true;
    config.batch_size = batch_size;
    config.latency_sample_stride = 0;
    return BacktestEngine(std::move(config)).run();
}

}  // namespace swarm

#include "BacktestEngine.hpp"

#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: swarm_worker <dataset.arrow> <strategy.so> [commission_bps] [slippage_bps]\n";
        return 1;
    }

    swarm::EngineConfig config;
    config.dataset_path = argv[1];
    config.strategy_lib_path = argv[2];
    if (argc > 3) {
        config.commission_bps = std::stod(argv[3]);
    }
    if (argc > 4) {
        config.slippage_bps = std::stod(argv[4]);
    }

    swarm::BacktestEngine engine(std::move(config));
    auto result = engine.run();

    if (!result.success) {
        std::cerr << result.error << "\n";
        return 2;
    }

    const auto& m = result.metrics;
    std::cout << "{"
              << "\"sharpe_ratio\":" << m.sharpe_ratio << ","
              << "\"max_drawdown_pct\":" << m.max_drawdown_pct << ","
              << "\"total_return_pct\":" << m.total_return_pct << ","
              << "\"ticks_processed\":" << m.ticks_processed << ","
              << "\"avg_latency_us\":" << m.avg_latency_us << ","
              << "\"p99_latency_us\":" << m.p99_latency_us << ","
              << "\"ticks_per_second\":" << result.ticks_per_second
              << "}\n";

    return 0;
}

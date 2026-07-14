#include "BacktestEngine.hpp"

#include <cstdlib>
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: swarm_benchmark <dataset.arrow> [batch_size] [min_ticks_per_sec]\n";
        return 1;
    }

    const std::string dataset = argv[1];
    size_t batch_size = swarm::ColumnarTickStore::kDefaultBatchSize;
    if (argc > 2) {
        batch_size = static_cast<size_t>(std::stoul(argv[2]));
    }

    double min_tps = 2'000'000.0;
    if (argc > 3) {
        min_tps = std::stod(argv[3]);
    }

    auto result = swarm::run_benchmark(dataset, batch_size);
    if (!result.success) {
        std::cerr << result.error << "\n";
        return 2;
    }

    const auto& m = result.metrics;
    const bool passed = result.ticks_per_second >= min_tps;

    std::cout << "{"
              << "\"ticks_processed\":" << m.ticks_processed << ","
              << "\"elapsed_ms\":" << result.elapsed_ms << ","
              << "\"ticks_per_second\":" << result.ticks_per_second << ","
              << "\"target_ticks_per_second\":" << min_tps << ","
              << "\"benchmark_passed\":" << (passed ? "true" : "false") << ","
              << "\"batch_size\":" << batch_size
              << "}\n";

    return passed ? 0 : 3;
}

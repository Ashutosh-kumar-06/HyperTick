#pragma once

#include "StrategyInterface.hpp"

#include <vector>

namespace swarm {

/// Minimal strategy for throughput benchmarking (no virtual dispatch overhead in hot path).
class NoOpStrategy final : public StrategyInterface {
public:
    void on_init(double, double, double) override {}

    std::vector<SignalEvent> on_market(const MarketEvent&) override {
        return {};
    }

    void on_fill(const FillEvent&) override {}

    StrategyMetrics finalize() override { return {}; }
};

}  // namespace swarm

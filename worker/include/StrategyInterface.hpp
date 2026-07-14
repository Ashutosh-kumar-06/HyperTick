#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace swarm {

enum class Side : uint8_t { Buy = 0, Sell = 1 };

enum class OrderType : uint8_t { Market = 0, Limit = 1 };

struct Tick {
    int64_t timestamp_ns;
    double bid;
    double ask;
    double last;
    int64_t volume;
};

struct MarketEvent {
    Tick tick;
    size_t tick_index;
};

struct SignalEvent {
    Side side;
    double quantity;
    double limit_price;  // 0 = market
    OrderType order_type;
};

struct FillEvent {
    Side side;
    double quantity;
    double fill_price;
    double commission;
    int64_t timestamp_ns;
};

struct StrategyMetrics {
    double sharpe_ratio{0.0};
    double max_drawdown_pct{0.0};
    double total_return_pct{0.0};
    uint64_t ticks_processed{0};
    double avg_latency_us{0.0};
    double p99_latency_us{0.0};
};

/// REQ-3.2 / REQ-1.2: All agent-generated strategies must implement this interface.
class StrategyInterface {
public:
    virtual ~StrategyInterface() = default;

    /// Called once before the event loop begins. No look-ahead: only config params allowed.
    virtual void on_init(double initial_capital, double commission_bps, double slippage_bps) = 0;

    /// REQ-3.2: Process a single market tick sequentially. Must not access future ticks.
    virtual std::vector<SignalEvent> on_market(const MarketEvent& event) = 0;

    /// Called after each fill to update internal position state.
    virtual void on_fill(const FillEvent& fill) = 0;

    /// Return final performance metrics after the simulation completes.
    virtual StrategyMetrics finalize() = 0;
};

}  // namespace swarm

/// Factory symbol exported by dynamically compiled strategy .so files.
extern "C" swarm::StrategyInterface* create_strategy();

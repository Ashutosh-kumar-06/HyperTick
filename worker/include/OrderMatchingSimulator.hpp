#pragma once

#include "StrategyInterface.hpp"

#include <deque>
#include <optional>
#include <vector>

namespace swarm {

struct PendingOrder {
    Side side;
    double quantity;
    double limit_price;
    OrderType order_type;
    uint64_t queue_position;
};

/// REQ-3.3: Order Matching Simulator with slippage, commission, and queue priority.
class OrderMatchingSimulator {
public:
    OrderMatchingSimulator(double commission_bps, double slippage_bps);

    std::vector<FillEvent> process_signals(
        const std::vector<SignalEvent>& signals,
        const Tick& tick,
        int64_t timestamp_ns);

    double position() const { return position_; }
    double cash() const { return cash_; }
    double equity(double mark_price) const { return cash_ + position_ * mark_price; }

    const std::vector<double>& equity_curve() const { return equity_curve_; }

private:
    double apply_slippage(Side side, double price) const;
    double commission_for(double notional) const;

    double commission_bps_;
    double slippage_bps_;
    double position_{0.0};
    double cash_{0.0};
    std::deque<PendingOrder> book_;
    std::vector<double> equity_curve_;
    uint64_t order_seq_{0};
};

}  // namespace swarm

#include "OrderMatchingSimulator.hpp"

#include <algorithm>
#include <cmath>

namespace swarm {

OrderMatchingSimulator::OrderMatchingSimulator(double commission_bps, double slippage_bps)
    : commission_bps_(commission_bps), slippage_bps_(slippage_bps) {}

double OrderMatchingSimulator::apply_slippage(Side side, double price) const {
    const double factor = slippage_bps_ / 10'000.0;
    return side == Side::Buy ? price * (1.0 + factor) : price * (1.0 - factor);
}

double OrderMatchingSimulator::commission_for(double notional) const {
    return std::abs(notional) * (commission_bps_ / 10'000.0);
}

std::vector<FillEvent> OrderMatchingSimulator::process_signals(
    const std::vector<SignalEvent>& signals,
    const Tick& tick,
    int64_t timestamp_ns) {
    std::vector<FillEvent> fills;

    for (const auto& sig : signals) {
        PendingOrder order{
            sig.side,
            sig.quantity,
            sig.limit_price,
            sig.order_type,
            order_seq_++,
        };
        book_.push_back(order);
    }

    std::vector<PendingOrder> remaining;
    for (auto& order : book_) {
        double ref_price = order.side == Side::Buy ? tick.ask : tick.bid;
        if (ref_price <= 0.0) {
            ref_price = tick.last;
        }

        if (order.order_type == OrderType::Limit) {
            const bool marketable =
                (order.side == Side::Buy && ref_price <= order.limit_price) ||
                (order.side == Side::Sell && ref_price >= order.limit_price);
            if (!marketable) {
                remaining.push_back(order);
                continue;
            }
        }

        const double fill_price = apply_slippage(order.side, ref_price);
        const double notional = fill_price * order.quantity;
        const double commission = commission_for(notional);

        if (order.side == Side::Buy) {
            cash_ -= notional + commission;
            position_ += order.quantity;
        } else {
            cash_ += notional - commission;
            position_ -= order.quantity;
        }

        fills.push_back(FillEvent{
            order.side,
            order.quantity,
            fill_price,
            commission,
            timestamp_ns,
        });
    }

    book_ = std::deque<PendingOrder>(remaining.begin(), remaining.end());

    const double mark = tick.last > 0 ? tick.last : (tick.bid + tick.ask) / 2.0;
    equity_curve_.push_back(equity(mark));

    return fills;
}

}  // namespace swarm

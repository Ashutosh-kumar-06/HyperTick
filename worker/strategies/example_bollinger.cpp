#include "StrategyInterface.hpp"

#include <cmath>
#include <deque>
#include <vector>

namespace {

class BollingerMeanReversion : public swarm::StrategyInterface {
public:
    void on_init(double initial_capital, double commission_bps, double slippage_bps) override {
        capital_ = initial_capital;
        commission_bps_ = commission_bps;
        slippage_bps_ = slippage_bps;
    }

    std::vector<swarm::SignalEvent> on_market(const swarm::MarketEvent& event) override {
        std::vector<swarm::SignalEvent> signals;
        prices_.push_back(event.tick.last > 0 ? event.tick.last : (event.tick.bid + event.tick.ask) / 2.0);

        constexpr size_t window = 20;
        if (prices_.size() < window) {
            return signals;
        }
        if (prices_.size() > window) {
            prices_.pop_front();
        }

        double sum = 0.0;
        for (double p : prices_) {
            sum += p;
        }
        const double mean = sum / static_cast<double>(prices_.size());

        double var = 0.0;
        for (double p : prices_) {
            var += (p - mean) * (p - mean);
        }
        const double stddev = std::sqrt(var / static_cast<double>(prices_.size()));

        const double price = prices_.back();
        const double upper = mean + 2.0 * stddev;
        const double lower = mean - 2.0 * stddev;

        if (price > upper && position_ > 0) {
            signals.push_back({swarm::Side::Sell, position_, 0.0, swarm::OrderType::Market});
        } else if (price < lower && position_ <= 0) {
            const double qty = std::floor(capital_ * 0.1 / price);
            if (qty > 0) {
                signals.push_back({swarm::Side::Buy, qty, 0.0, swarm::OrderType::Market});
            }
        }

        return signals;
    }

    void on_fill(const swarm::FillEvent& fill) override {
        if (fill.side == swarm::Side::Buy) {
            position_ += fill.quantity;
            capital_ -= fill.fill_price * fill.quantity + fill.commission;
        } else {
            position_ -= fill.quantity;
            capital_ += fill.fill_price * fill.quantity - fill.commission;
        }
    }

    swarm::StrategyMetrics finalize() override {
        return {};
    }

private:
    double capital_{0.0};
    double commission_bps_{0.0};
    double slippage_bps_{0.0};
    double position_{0.0};
    std::deque<double> prices_;
};

}  // namespace

extern "C" swarm::StrategyInterface* create_strategy() {
    return new BollingerMeanReversion();
}

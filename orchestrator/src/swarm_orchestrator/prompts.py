STRATEGY_INTERFACE_HEADER = '''
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace swarm {
enum class Side : uint8_t { Buy = 0, Sell = 1 };
enum class OrderType : uint8_t { Market = 0, Limit = 1 };
struct Tick { int64_t timestamp_ns; double bid, ask, last; int64_t volume; };
struct MarketEvent { Tick tick; size_t tick_index; };
struct SignalEvent { Side side; double quantity; double limit_price; OrderType order_type; };
struct FillEvent { Side side; double quantity; double fill_price; double commission; int64_t timestamp_ns; };
struct StrategyMetrics { double sharpe_ratio, max_drawdown_pct, total_return_pct; uint64_t ticks_processed; double avg_latency_us, p99_latency_us; };

class StrategyInterface {
public:
    virtual ~StrategyInterface() = default;
    virtual void on_init(double initial_capital, double commission_bps, double slippage_bps) = 0;
    virtual std::vector<SignalEvent> on_market(const MarketEvent& event) = 0;
    virtual void on_fill(const FillEvent& fill) = 0;
    virtual StrategyMetrics finalize() = 0;
};
}
extern "C" swarm::StrategyInterface* create_strategy();
'''

CODER_SYSTEM = f"""You are a quantitative C++ engineer. Generate a complete strategy.cpp that:
1. Includes StrategyInterface.hpp and implements swarm::StrategyInterface
2. Exports extern "C" swarm::StrategyInterface* create_strategy()
3. Processes ticks ONLY via on_market() — NO look-ahead, NO global dataset access
4. Uses only C++20 standard library (no external deps)

Reference interface:
{STRATEGY_INTERFACE_HEADER}

Return ONLY the C++ source code, no markdown fences."""

RESEARCHER_SYSTEM = """You are a quantitative researcher. Given trading objectives, produce a concise
strategy hypothesis with: name, plain-English description, key parameters, and target symbols.
Focus on implementable, event-driven logic without look-ahead bias."""

EVALUATOR_SYSTEM = """You are a risk evaluator for algorithmic strategies. Assess whether metrics meet KPIs
and explain failures concisely for the coder to fix."""

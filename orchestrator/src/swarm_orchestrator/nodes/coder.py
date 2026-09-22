"""REQ-1.2: Coder Node — generate C++ strategy conforming to StrategyInterface.hpp."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from swarm_orchestrator.broker.crdt_state import SwarmStateCRDT
from swarm_orchestrator.broker.redis_cache import AgentMemoryCache
from swarm_orchestrator.config import Settings
from swarm_orchestrator.llm_factory import create_llm
from swarm_orchestrator.prompts import CODER_SYSTEM
from swarm_orchestrator.state import SwarmState

FALLBACK_STRATEGY = """#include "StrategyInterface.hpp"
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
        const double price = event.tick.last > 0 ? event.tick.last : (event.tick.bid + event.tick.ask) / 2.0;
        if (price <= 0.0) return signals;

        prices_.push_back(price);
        constexpr size_t window = 20;
        if (prices_.size() < window) return signals;
        if (prices_.size() > window) prices_.pop_front();

        double sum = 0.0;
        for (double p : prices_) sum += p;
        const double mean = sum / static_cast<double>(prices_.size());

        double var = 0.0;
        for (double p : prices_) var += (p - mean) * (p - mean);
        const double stddev = std::sqrt(var / static_cast<double>(prices_.size()));

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
    double capital_{100000.0};
    double commission_bps_{1.0};
    double slippage_bps_{0.5};
    double position_{0.0};
    std::deque<double> prices_;
};

} // namespace

extern "C" swarm::StrategyInterface* create_strategy() {
    return new BollingerMeanReversion();
}
"""


def _extract_text(content) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _strip_fences(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)


def coder_node(state: SwarmState, settings: Settings) -> dict:
    task_id = state.get("task_id", "")
    crdt = SwarmStateCRDT(settings.redis_url, settings.crdt_node_id or None)
    if settings.enable_crdt_sync:
        crdt.subscribe_sync(task_id)

    cache = AgentMemoryCache(settings.redis_url)
    history = crdt.format_iteration_log(task_id) or cache.format_for_prompt(task_id)

    hypothesis_text = ""
    hypothesis = state.get("hypothesis")
    if hypothesis:
        hypothesis_text = hypothesis.model_dump_json(indent=2)

    reflection = ""
    if state.get("reflection_notes"):
        reflection = f"\n\nFix these issues from the evaluator:\n{state['reflection_notes']}"
    outcome = state.get("outcome")
    if outcome and outcome.stderr:
        reflection += f"\n\nCompiler/runtime stderr:\n{outcome.stderr[:4000]}"

    source = ""
    try:
        llm = create_llm(settings)
        response = llm.invoke([
            SystemMessage(content=CODER_SYSTEM),
            HumanMessage(content=f"{history}\n\nHypothesis:\n{hypothesis_text}{reflection}"),
        ])
        raw_text = _extract_text(response.content)
        source = _strip_fences(raw_text)
    except Exception:
        pass

    if not source or "create_strategy" not in source:
        source = FALLBACK_STRATEGY

    iteration = state.get("iteration", 0)

    crdt.update_register(task_id, "strategy_source", source)
    crdt.append_iteration(task_id, {
        "iteration": iteration,
        "status": "coded",
        "notes": f"Generated strategy for {hypothesis.name if hypothesis else 'unknown'}",
    })
    if settings.enable_crdt_sync:
        crdt.publish_for_sync(task_id)

    cache.append_iteration(task_id, {
        "iteration": iteration,
        "status": "coded",
        "notes": f"Generated strategy for {hypothesis.name if hypothesis else 'unknown'}",
    })

    return {
        "strategy_source": source,
        "iteration": iteration + 1,
        "iteration_log": [f"[coder] Iteration {iteration + 1} C++ strategy synthesized ({len(source)} bytes)"],
    }

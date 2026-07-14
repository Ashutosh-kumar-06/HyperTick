"""CLI entry point for the trading swarm orchestrator."""

from __future__ import annotations

import argparse
import json

from swarm_orchestrator.config import Settings
from swarm_orchestrator.graph import build_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Quantitative Trading Backtesting Swarm")
    parser.add_argument("--prompt", default="Bollinger Band mean reversion with 2-standard-deviation threshold on SPY")
    parser.add_argument("--dataset", default="sample_spy_ticks", help="Dataset ID (see data/index.json)")
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--provider", choices=["openai", "gemini", "groq"], default=None, help="Override LLM_PROVIDER")
    args = parser.parse_args()

    settings = Settings()
    if args.max_iterations is not None:
        settings.max_iterations = args.max_iterations
    if args.provider:
        settings.llm_provider = args.provider

    print(f"LLM provider: {settings.llm_provider} model: {settings.llm_model}")

    graph = build_graph(settings)
    result = graph.invoke({
        "user_prompt": args.prompt,
        "dataset_id": args.dataset,
        "max_iterations": settings.max_iterations,
    })

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

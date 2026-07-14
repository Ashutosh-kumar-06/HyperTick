from pydantic import BaseModel, Field
from typing import Annotated, Literal, Optional, TypedDict
import operator


class StrategyHypothesis(BaseModel):
    name: str
    description: str
    parameters: dict[str, str | float | int] = Field(default_factory=dict)
    symbols: list[str] = Field(default_factory=lambda: ["SPY"])


class BacktestMetrics(BaseModel):
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    total_return_pct: float = 0.0
    ticks_processed: int = 0
    avg_latency_us: float = 0.0
    p99_latency_us: float = 0.0
    elapsed_ms: float = 0.0


class BacktestOutcome(BaseModel):
    task_id: str
    status: Literal["success", "compile_error", "runtime_error", "timeout", "segfault", "pending"]
    metrics: Optional[BacktestMetrics] = None
    stderr: str = ""
    stdout: str = ""


class SwarmState(TypedDict, total=False):
    """Immutable state schema for the LangGraph control loop (REQ-1.1–1.4)."""

    task_id: str
    iteration: int
    max_iterations: int
    user_prompt: str
    dataset_id: str
    hypothesis: StrategyHypothesis
    strategy_source: str
    outcome: BacktestOutcome
    reflection_notes: str
    iteration_log: Annotated[list[str], operator.add]
    approved: bool

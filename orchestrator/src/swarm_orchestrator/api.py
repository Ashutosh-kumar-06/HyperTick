from contextlib import asynccontextmanager
from typing import Optional, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from swarm_orchestrator.config import Settings
from swarm_orchestrator.graph import build_graph

# Global settings and graph
settings = Settings()
graph = build_graph(settings)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Swarm Orchestrator API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RunRequest(BaseModel):
    prompt: str
    dataset_id: str = "sample_spy_ticks.arrow"
    max_iterations: Optional[int] = None

class RunResponse(BaseModel):
    task_id: str = ""
    iteration: int = 0
    max_iterations: int = 5
    user_prompt: str = ""
    dataset_id: str = ""
    hypothesis: str = ""
    strategy_source: str = ""
    outcome: str = ""
    reflection_notes: str = ""
    iteration_log: list[str] = Field(default_factory=list)
    approved: bool = False

@app.post("/api/run", response_model=RunResponse)
async def run_backtest(req: RunRequest):
    try:
        max_iters = req.max_iterations if req.max_iterations is not None else settings.max_iterations
        result = graph.invoke({
            "user_prompt": req.prompt,
            "dataset_id": req.dataset_id,
            "max_iterations": max_iters,
        })

        hyp = result.get("hypothesis")
        hyp_str = hyp.name if hasattr(hyp, "name") else str(hyp or "")

        outcome_val = result.get("outcome")
        if hasattr(outcome_val, "status"):
            outcome_str = f"Status: {outcome_val.status}"
            if outcome_val.metrics:
                m = outcome_val.metrics
                outcome_str += f" (Sharpe: {m.sharpe_ratio:.2f}, Drawdown: {m.max_drawdown_pct:.1f}%, Return: {m.total_return_pct:.1f}%)"
        else:
            outcome_str = str(outcome_val or "")

        return RunResponse(
            task_id=result.get("task_id", ""),
            iteration=result.get("iteration", 0),
            max_iterations=max_iters,
            user_prompt=req.prompt,
            dataset_id=req.dataset_id,
            hypothesis=hyp_str,
            strategy_source=result.get("strategy_source", ""),
            outcome=outcome_str,
            reflection_notes=result.get("reflection_notes", ""),
            iteration_log=result.get("iteration_log", []),
            approved=bool(result.get("approved", False)),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "llm_provider": settings.llm_provider}

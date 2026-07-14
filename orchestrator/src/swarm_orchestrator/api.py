from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from swarm_orchestrator.config import Settings
from swarm_orchestrator.graph import build_graph

# Global settings and graph
settings = Settings()
graph = build_graph(settings)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: setup resources if needed
    yield
    # Shutdown: cleanup resources if needed

app = FastAPI(title="Swarm Orchestrator API", lifespan=lifespan)

# Allow CORS for local UI development
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
    task_id: str
    iteration: int
    max_iterations: int
    user_prompt: str
    dataset_id: str
    hypothesis: str
    strategy_source: str
    outcome: str
    reflection_notes: str
    iteration_log: list[str]
    approved: bool

@app.post("/api/run", response_model=RunResponse)
async def run_backtest(req: RunRequest):
    try:
        max_iters = req.max_iterations if req.max_iterations is not None else settings.max_iterations
        result = graph.invoke({
            "user_prompt": req.prompt,
            "dataset_id": req.dataset_id,
            "max_iterations": max_iters,
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "llm_provider": settings.llm_provider}

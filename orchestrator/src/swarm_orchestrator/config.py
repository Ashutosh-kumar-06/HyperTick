from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    rabbitmq_url: str = "amqp://swarm:swarm_secret@localhost:5672/"
    redis_url: str = "redis://localhost:6379/0"
    mongodb_url: str = "mongodb://localhost:27017/trading_swarm"

    llm_provider: str = "openai"  # openai | gemini | groq
    openai_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.0

    crdt_node_id: str = ""
    enable_crdt_sync: bool = False

    max_drawdown_pct: float = 15.0
    max_latency_us: float = 50.0
    min_sharpe_ratio: float = 1.0
    max_iterations: int = 5

    backtest_timeout_sec: float = 30.0

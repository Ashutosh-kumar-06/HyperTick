from pydantic_settings import BaseSettings, SettingsConfigDict


class ConsumerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    rabbitmq_url: str = "amqp://swarm:swarm_secret@localhost:5672/"
    docker_host: str = "unix:///var/run/docker.sock"
    worker_image: str = "trading-swarm-worker:latest"
    worker_timeout_sec: int = 5
    worker_cpu: float = 0.5
    worker_memory: str = "512m"
    consumer_instance_id: str = ""
    rabbitmq_prefetch: int = 1
    data_dir: str = "/data"

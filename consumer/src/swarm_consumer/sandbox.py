"""Docker sandbox worker execution (REQ-5.2, REQ-5.3)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import docker

from swarm_consumer.config import ConsumerSettings


class SandboxRunner:
    def __init__(self, settings: ConsumerSettings):
        self.settings = settings
        self.client = docker.DockerClient(base_url=settings.docker_host)

    def run_backtest(
        self,
        strategy_source: str,
        dataset_id: str,
        commission_bps: float = 1.0,
        slippage_bps: float = 0.5,
    ) -> dict:
        work_dir = Path(tempfile.mkdtemp(prefix="swarm_"))
        try:
            strategy_path = work_dir / "strategy.cpp"
            strategy_path.write_text(strategy_source, encoding="utf-8")
            so_path = work_dir / "strategy.so"

            compile_cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--entrypoint", "/bin/bash",
                "-v", f"{work_dir}:/work",
                "-v", f"{Path(__file__).resolve().parents[3] / 'worker' / 'include'}:/app/include:ro",
                self.settings.worker_image,
                "-c",
                "/app/scripts/compile_strategy.sh /work/strategy.cpp /work/strategy.so /app/include",
            ]

            compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=30)
            if compile_proc.returncode != 0:
                return {
                    "status": "compile_error",
                    "stderr": compile_proc.stderr or compile_proc.stdout,
                    "stdout": "",
                    "exit_code": compile_proc.returncode,
                    "metrics": None,
                }

            dataset_path = Path(self.settings.data_dir) / f"{dataset_id}.arrow"
            if not dataset_path.exists():
                return {
                    "status": "runtime_error",
                    "stderr": f"Dataset not found: {dataset_path}",
                    "stdout": "",
                    "exit_code": 1,
                    "metrics": None,
                }

            container_name = f"swarm_worker_{uuid.uuid4().hex[:12]}"
            nano_cpus = int(self.settings.worker_cpu * 1e9)

            container = self.client.containers.run(
                self.settings.worker_image,
                command=[
                    str(dataset_path),
                    "/work/strategy.so",
                    str(commission_bps),
                    str(slippage_bps),
                ],
                entrypoint="/usr/local/bin/swarm_worker",
                name=container_name,
                detach=True,
                network_mode="none",
                user="sandbox",
                mem_limit=self.settings.worker_memory,
                nano_cpus=nano_cpus,
                volumes={
                    str(dataset_path): {"bind": str(dataset_path), "mode": "ro"},
                    str(so_path): {"bind": "/work/strategy.so", "mode": "ro"},
                },
                remove=False,
            )

            try:
                result = container.wait(timeout=self.settings.worker_timeout_sec)
            except Exception:
                container.kill()
                container.remove(force=True)
                return {
                    "status": "timeout",
                    "stderr": f"Worker exceeded {self.settings.worker_timeout_sec}s timeout",
                    "stdout": "",
                    "exit_code": -1,
                    "metrics": None,
                }

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            exit_code = result.get("StatusCode", -1)
            container.remove(force=True)

            status = "success" if exit_code == 0 else "runtime_error"
            if exit_code == 139:
                status = "segfault"

            metrics = None
            if exit_code == 0 and stdout.strip():
                try:
                    line = stdout.strip().splitlines()[-1]
                    if line.startswith("{"):
                        metrics = json.loads(line)
                except json.JSONDecodeError:
                    pass

            return {
                "status": status,
                "stderr": stderr,
                "stdout": stdout,
                "exit_code": exit_code,
                "metrics": metrics,
            }
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

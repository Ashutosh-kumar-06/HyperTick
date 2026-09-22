"""Docker sandbox worker execution (REQ-5.2, REQ-5.3)."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import docker

from swarm_consumer.config import ConsumerSettings


def _get_host_data_source(client: docker.DockerClient, fallback: str) -> str:
    container_id = os.environ.get("HOSTNAME")
    if container_id:
        try:
            c = client.containers.get(container_id)
            for m in c.attrs.get("Mounts", []):
                if m.get("Destination") == "/data":
                    return m.get("Source", fallback)
        except Exception:
            pass
    return fallback


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
        base_scratch = Path("/tmp/swarm_workers")
        use_scratch_volume = base_scratch.exists()
        work_dir = Path(tempfile.mkdtemp(prefix="swarm_", dir=base_scratch if use_scratch_volume else None))
        try:
            strategy_path = work_dir / "strategy.cpp"
            strategy_path.write_text(strategy_source, encoding="utf-8")
            so_path = work_dir / "strategy.so"

            # Normalize dataset id (handle both "foo" and "foo.arrow")
            clean_ds_id = dataset_id[:-6] if dataset_id.endswith(".arrow") else dataset_id
            local_dataset = Path(self.settings.data_dir) / f"{clean_ds_id}.arrow"
            if not local_dataset.exists():
                return {
                    "status": "runtime_error",
                    "stderr": f"Dataset not found: {local_dataset}",
                    "stdout": "",
                    "exit_code": 1,
                    "metrics": None,
                }

            # Prepare mounts
            host_data = _get_host_data_source(self.client, str(local_dataset.parent))
            host_dataset_file = f"{host_data}/{clean_ds_id}.arrow" if not host_data.endswith(".arrow") else host_data

            if use_scratch_volume:
                volume_map = {
                    "quantai_worker_scratch": {"bind": "/tmp/swarm_workers", "mode": "rw"},
                }
                container_so_path = str(so_path)
                container_cpp_path = str(strategy_path)
            else:
                volume_map = {
                    str(work_dir.resolve()): {"bind": "/work", "mode": "rw"},
                }
                container_so_path = "/work/strategy.so"
                container_cpp_path = "/work/strategy.cpp"

            # Compile strategy directly via Docker SDK (no subprocess 'docker' CLI dependency)
            try:
                compile_cmd = [
                    "-c",
                    f"g++ -O3 -shared -fPIC -std=c++20 -I/app/include {container_cpp_path} -o {container_so_path}",
                ]
                self.client.containers.run(
                    self.settings.worker_image,
                    entrypoint="/bin/bash",
                    command=compile_cmd,
                    volumes=volume_map,
                    user="root",
                    remove=True,
                    network_mode="none",
                )
            except docker.errors.ContainerError as exc:
                return {
                    "status": "compile_error",
                    "stderr": exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc),
                    "stdout": "",
                    "exit_code": exc.exit_status,
                    "metrics": None,
                }
            except Exception as exc:
                return {
                    "status": "compile_error",
                    "stderr": str(exc),
                    "stdout": "",
                    "exit_code": 1,
                    "metrics": None,
                }

            container_name = f"swarm_worker_{uuid.uuid4().hex[:12]}"
            nano_cpus = int(self.settings.worker_cpu * 1e9)

            worker_volumes = dict(volume_map)
            worker_volumes[host_dataset_file] = {"bind": "/data/dataset.arrow", "mode": "ro"}

            container = self.client.containers.run(
                self.settings.worker_image,
                command=[
                    "/data/dataset.arrow",
                    container_so_path,
                    str(commission_bps),
                    str(slippage_bps),
                ],
                entrypoint="/usr/local/bin/swarm_worker",
                name=container_name,
                detach=True,
                network_mode="none",
                user="root",
                mem_limit=self.settings.worker_memory,
                nano_cpus=nano_cpus,
                volumes=worker_volumes,
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

"""Persistência real: o serviço é iniciado como processo (uvicorn), encerrado e reiniciado."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_service(data_dir: Path, legacy_dir: Path, port: int) -> subprocess.Popen:
    env = {**os.environ, "BIM_SCHEDULE_DATA_DIR": str(data_dir), "BIM_SCHEDULE_LEGACY_DIR": str(legacy_dir),
           "BIM_SCHEDULE_LOG_LEVEL": "WARNING", "PYTHONPATH": str(BACKEND_DIR)}
    process = subprocess.Popen([sys.executable, "-m", "app", "--port", str(port)], cwd=BACKEND_DIR, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"Serviço terminou ao iniciar:\n{process.stdout.read()}")
        try:
            if httpx.get(f"http://127.0.0.1:{port}/api/v1/system/health", timeout=1, trust_env=False).status_code == 200:
                return process
        except httpx.HTTPError:
            time.sleep(0.2)
    process.kill()
    raise AssertionError("Serviço não respondeu a tempo.")


def stop_service(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def test_project_survives_service_restart(tmp_path):
    data_dir, legacy_dir = tmp_path / "data", tmp_path / "legacy"
    port = free_port()
    base = f"http://127.0.0.1:{port}/api/v1"

    process = start_service(data_dir, legacy_dir, port)
    try:
        first_line = process.stdout.readline()
        assert first_line.startswith("BIM_SCHEDULE_READY ")
        assert json.loads(first_line.split(" ", 1)[1])["api_base_url"] == base
        created = httpx.post(f"{base}/projects/", json={"name": "Persistente", "code": "PERS-01",
                                                         "start_date": "2026-01-05", "end_date": "2026-03-01"},
                             trust_env=False)
        assert created.status_code == 201, created.text
        project_id = created.json()["id"]
        act = httpx.post(f"{base}/activities/", json={"project_id": project_id, "name": "Fundação", "code": "F1",
                                                       "duration": 10}, trust_env=False)
        assert act.status_code == 201
    finally:
        stop_service(process)

    assert (data_dir / "bim_schedule.db").is_file()

    process = start_service(data_dir, legacy_dir, port)
    try:
        project = httpx.get(f"{base}/projects/{project_id}", trust_env=False).json()
        assert project["code"] == "PERS-01" and project["start_date"] == "2026-01-05"
        activities = httpx.get(f"{base}/activities/project/{project_id}", trust_env=False).json()
        assert [a["code"] for a in activities] == ["F1"]
    finally:
        stop_service(process)


def test_service_refuses_non_local_host(tmp_path):
    env = {**os.environ, "BIM_SCHEDULE_DATA_DIR": str(tmp_path / "d"), "BIM_SCHEDULE_LEGACY_DIR": str(tmp_path / "l"),
           "PYTHONPATH": str(BACKEND_DIR)}
    result = subprocess.run([sys.executable, "-m", "app", "--host", "0.0.0.0"], cwd=BACKEND_DIR, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 2
    assert "127.0.0.1" in result.stderr

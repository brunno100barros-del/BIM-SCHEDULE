"""Importa arquivos IFC pelo serviço local e mede tempo e memória do processamento.

Uso (na raiz do repositório):

    .venv\\Scripts\\python.exe desktop\\scripts\\ifc_benchmark.py --plan plano.json --out resultado.json
        [--service desktop\\service\\dist\\bim-schedule-service\\bim-schedule-service.exe] [--port 8799]

plano.json: [{"project": "Nome do projeto", "code": "COD", "files": ["C:/.../a.ifc", ...]}, ...]

O serviço usa a pasta de dados padrão (%LOCALAPPDATA%\\BIM-SCHEDULE), a menos que
BIM_SCHEDULE_DATA_DIR esteja definido. Os IFCs NUNCA são copiados para o repositório.
Requer psutil (somente para medição; não é dependência do produto).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import psutil


def tree_rss(proc: psutil.Process) -> tuple[int, int]:
    """RSS do serviço e RSS somado dos processos filhos (tarefas)."""
    try:
        main = proc.memory_info().rss
    except psutil.Error:
        return 0, 0
    children = 0
    for child in proc.children(recursive=True):
        try:
            children += child.memory_info().rss
        except psutil.Error:
            pass
    return main, children


class Sampler(threading.Thread):
    def __init__(self, proc: psutil.Process):
        super().__init__(daemon=True)
        self.proc = proc
        self.stop_flag = threading.Event()
        self.peak_main = 0
        self.peak_children = 0
        self.peak_total = 0

    def run(self):
        while not self.stop_flag.is_set():
            main, children = tree_rss(self.proc)
            self.peak_main = max(self.peak_main, main)
            self.peak_children = max(self.peak_children, children)
            self.peak_total = max(self.peak_total, main + children)
            time.sleep(0.25)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--service", default=str(Path(__file__).resolve().parents[1] / "service" / "dist" / "bim-schedule-service" / "bim-schedule-service.exe"))
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--timeout-min", type=float, default=60)
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    base = f"http://127.0.0.1:{args.port}/api/v1"
    log = open(Path(args.out).with_suffix(".service.log"), "w", encoding="utf-8")
    svc = subprocess.Popen([args.service, "--port", str(args.port)], stdout=log, stderr=subprocess.STDOUT,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    proc = psutil.Process(svc.pid)
    results = []
    try:
        client = httpx.Client(timeout=httpx.Timeout(600.0))
        for _ in range(240):
            try:
                if client.get(f"{base}/system/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        status = client.get(f"{base}/system/status").json()
        idle_main, _ = tree_rss(proc)
        print("Serviço pronto; dados em", status["storage"]["data_dir"], flush=True)

        for entry in plan:
            existing = [p for p in client.get(f"{base}/projects/").json() if p["code"] == entry["code"]]
            if existing:
                project = existing[0]
            else:
                r = client.post(f"{base}/projects/", json={"name": entry["project"], "code": entry["code"],
                                                          "description": "Projeto de TESTE criado pelo benchmark de IFC."})
                r.raise_for_status()
                project = r.json()
            for f in entry["files"]:
                path = Path(f)
                rec = {"project_id": project["id"], "project": entry["project"], "file": str(path), "filename": path.name,
                       "size_bytes": path.stat().st_size}
                print(f"-> {path.name} ({rec['size_bytes'] / 1e6:.1f} MB)", flush=True)
                sampler = Sampler(proc)
                sampler.start()
                t0 = time.perf_counter()
                with open(path, "rb") as fh:
                    r = client.post(f"{base}/ifc/project/{project['id']}/upload", files={"file": (path.name, fh, "application/octet-stream")})
                rec["upload_seconds"] = round(time.perf_counter() - t0, 2)
                if r.status_code != 202:
                    rec.update(status="upload_failed", http_status=r.status_code, error=r.text[:500])
                    sampler.stop_flag.set(); results.append(rec); print("   falha no envio:", r.text[:200], flush=True)
                    continue
                up = r.json()
                rec.update(model_id=up["id"], job_id=up["job_id"], warnings=up.get("warnings", []))
                t1 = time.perf_counter()
                job = {}
                last_msg = None
                while time.perf_counter() - t1 < args.timeout_min * 60:
                    job = client.get(f"{base}/jobs/{up['job_id']}").json()
                    msg = job.get("message")
                    if msg != last_msg:
                        last_msg = msg
                    if job.get("status") in ("completed", "failed", "cancelled", "interrupted"):
                        break
                    time.sleep(0.5)
                rec["processing_seconds"] = round(time.perf_counter() - t1, 2)
                rec["total_seconds"] = round(time.perf_counter() - t0, 2)
                sampler.stop_flag.set(); sampler.join()
                rec["peak_service_rss_mb"] = round(sampler.peak_main / 2**20, 1)
                rec["peak_job_process_rss_mb"] = round(sampler.peak_children / 2**20, 1)
                rec["peak_total_rss_mb"] = round(sampler.peak_total / 2**20, 1)
                rec["job_status"] = job.get("status")
                rec["job_error"] = job.get("error") or job.get("error_message")
                model = client.get(f"{base}/ifc/model/{up['id']}").json()
                rec["model_status"] = model.get("status")
                rec["schema"] = model.get("schema_name")
                rec["element_count"] = model.get("element_count")
                rec["model_error"] = model.get("error_message")
                print(f"   {rec['job_status']} em {rec['processing_seconds']} s; {rec['element_count']} elementos; "
                      f"pico tarefa {rec['peak_job_process_rss_mb']} MB", flush=True)
                results.append(rec)
                Path(args.out).write_text(json.dumps({"idle_service_rss_mb": round(idle_main / 2**20, 1), "results": results},
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        subprocess.run(["taskkill", "/PID", str(svc.pid), "/T", "/F"], capture_output=True)
        log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

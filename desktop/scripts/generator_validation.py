"""Valida quantitativos + gerador de cronograma nos projetos cujo código começa com um prefixo.

    .venv\\Scripts\\python.exe desktop\\scripts\\generator_validation.py --out resultado.json [--prefix TST-] [--apply]

Usa o serviço empacotado e a pasta de dados padrão. Com ``--apply``, aceita a proposta
(substituindo a geração anterior) e calcula o CPM. Requer psutil (medição de memória).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="TST-")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--port", type=int, default=8798)
    ap.add_argument("--service", default=str(ROOT / "desktop" / "service" / "dist" / "bim-schedule-service" / "bim-schedule-service.exe"))
    args = ap.parse_args()
    base = f"http://127.0.0.1:{args.port}/api/v1"
    log = open(Path(args.out).with_suffix(".service.log"), "w", encoding="utf-8")
    svc = subprocess.Popen([args.service, "--port", str(args.port)], stdout=log, stderr=subprocess.STDOUT,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    proc = psutil.Process(svc.pid)
    out = []
    try:
        c = httpx.Client(timeout=httpx.Timeout(900.0))
        for _ in range(240):
            try:
                if c.get(f"{base}/system/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        print("revisão do banco:", c.get(f"{base}/system/status").json()["database"], flush=True)
        projects = [p for p in c.get(f"{base}/projects/").json() if p["code"].startswith(args.prefix)]
        for p in sorted(projects, key=lambda p: p["id"]):
            models = c.get(f"{base}/takeoff/project/{p['id']}/models").json()
            rec = {"project": p["name"], "code": p["code"], "models": []}
            for m in models:
                t0 = time.perf_counter()
                job_id = c.post(f"{base}/takeoff/model/{m['model_id']}").json()["job_id"]
                peak = 0
                while True:
                    job = c.get(f"{base}/jobs/{job_id}").json()
                    try:
                        peak = max(peak, sum(ch.memory_info().rss for ch in proc.children(recursive=True)))
                    except psutil.Error:
                        pass
                    if job["is_terminal"]:
                        break
                    time.sleep(0.25)
                info = c.get(f"{base}/takeoff/model/{m['model_id']}").json()
                s = info.get("summary") or {}
                rec["models"].append({"filename": m["filename"], "status": job["status"], "error": job.get("error"),
                                      "seconds": round(time.perf_counter() - t0, 1), "peak_job_rss_mb": round(peak / 2**20),
                                      "included": s.get("included"), "excluded": s.get("excluded"),
                                      "with_geometry": s.get("with_geometry"), "geometry_attempted": s.get("geometry_attempted"),
                                      "sources": s.get("sources_by_measure"),
                                      "totals": (info.get("totals") or {}).get("by_type")})
                print(f"{p['code']} {m['filename']}: {job['status']} em {rec['models'][-1]['seconds']} s, "
                      f"geometria {s.get('with_geometry')}/{s.get('geometry_attempted')}", flush=True)
            ids = [m["model_id"] for m in models if m["is_current"]]
            t0 = time.perf_counter()
            prop = c.post(f"{base}/schedule-generator/project/{p['id']}/preview", json={"model_ids": ids})
            if prop.status_code != 200:
                rec["preview_error"] = prop.text[:500]
                out.append(rec)
                continue
            prop = prop.json()
            rec["preview_seconds"] = round(time.perf_counter() - t0, 2)
            rec["level_mode"] = prop["level_mode"]
            rec["levels"] = [(lv["name"], lv["element_count"]) for lv in prop["levels"]]
            rec["stats"] = prop["stats"]
            rec["unmapped"] = prop["unmapped"]
            rec["warnings"] = prop["warnings"]
            rec["activities"] = [{k: a[k] for k in ("code", "name", "quantity", "unit", "coverage", "duration", "provisional",
                                                    "provisional_reason", "element_count", "include")} for a in prop["activities"]]
            print(f"   prévia: {prop['stats']} níveis={len(prop['levels'])} ({prop['level_mode']})", flush=True)
            if args.apply:
                t0 = time.perf_counter()
                res = c.post(f"{base}/schedule-generator/project/{p['id']}/apply", json={"model_ids": ids, "replace_previous": True})
                rec["apply_seconds"] = round(time.perf_counter() - t0, 2)
                rec["apply"] = res.json() if res.status_code == 201 else {"error": res.text[:500]}
                print(f"   aplicado: {rec['apply']}", flush=True)
            out.append(rec)
            Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        subprocess.run(["taskkill", "/PID", str(svc.pid), "/T", "/F"], capture_output=True)
        log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

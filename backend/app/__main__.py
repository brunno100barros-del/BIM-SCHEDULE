"""Ponto de entrada do serviço local: ``python -m app``.

É o comando que o aplicativo Windows (Electron) executará para iniciar o
backend, sem que o usuário abra um terminal. Também oferece subcomandos de
manutenção::

    python -m app                       inicia o serviço (127.0.0.1:8000)
    python -m app --port 0              escolhe uma porta livre e a informa no stdout
    python -m app prepare               resolve a pasta de dados e aplica migrações
    python -m app storage-info          mostra onde os dados estão e se há dados legados

Ao iniciar, o serviço imprime uma linha ``BIM_SCHEDULE_READY {json}`` com a URL
efetiva, que o processo pai pode ler para configurar o frontend.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import socket
import sys


def _free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bim-schedule-service")
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "prepare", "storage-info"])
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args(argv)

    if args.data_dir:
        os.environ["BIM_SCHEDULE_DATA_DIR"] = args.data_dir

    from app.core.config import get_settings, reset_settings

    reset_settings()
    settings = get_settings()

    if args.command == "storage-info":
        from app.core.storage import resolve_storage
        layout = resolve_storage(settings, migrate=False)
        print(json.dumps(layout.public_summary(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "prepare":
        from app.core.bootstrap import prepare_storage
        storage, schema = prepare_storage(settings)
        print(json.dumps({"storage": storage.public_summary(), "schema": schema}, ensure_ascii=False, indent=2))
        return 0

    import uvicorn

    from app.main import create_app

    host = args.host or settings.HOST
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"Recusado: o serviço local só pode escutar em 127.0.0.1 (recebido {host}).", file=sys.stderr)
        return 2
    port = args.port if args.port is not None else settings.PORT
    if port == 0:
        port = _free_port(host)
    print("BIM_SCHEDULE_READY " + json.dumps({"api_base_url": f"http://{host}:{port}{settings.API_V1_STR}"}), flush=True)
    uvicorn.run(create_app(settings), host=host, port=port, log_level=settings.LOG_LEVEL.lower())
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()  # necessário para processos filhos no executável empacotado (Windows)
    sys.exit(main())

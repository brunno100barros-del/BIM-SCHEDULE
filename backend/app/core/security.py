"""Proteções do serviço local.

- O serviço escuta apenas em 127.0.0.1 (definido em ``__main__`` e nos scripts).
- ``TrustedHostMiddleware`` rejeita cabeçalhos Host inesperados (proteção contra
  DNS rebinding a partir de páginas abertas no navegador).
- CORS restrito às origens configuradas.
- Token local opcional: quando ``LOCAL_API_TOKEN`` está definido (o app desktop
  gera um por sessão), toda rota ``/api`` exige o cabeçalho ``X-BIM-Schedule-Token``,
  exceto a verificação de saúde.
"""
from __future__ import annotations

import hmac
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import Settings
from app.core.errors import error_payload
from app.core.logging import get_logger

TOKEN_HEADER = "X-BIM-Schedule-Token"
REQUEST_ID_HEADER = "X-Request-ID"
logger = get_logger("http")


def install_middlewares(app: FastAPI, settings: Settings) -> None:
    public_paths = {f"{settings.API_V1_STR}/system/health"}

    @app.middleware("http")
    async def _request_context(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        if (
            settings.LOCAL_API_TOKEN
            and request.url.path.startswith("/api")
            and request.url.path not in public_paths
            and request.method != "OPTIONS"
        ):
            supplied = request.headers.get(TOKEN_HEADER, "")
            if not hmac.compare_digest(supplied, settings.LOCAL_API_TOKEN):
                return JSONResponse(
                    status_code=401,
                    content=error_payload(401, "Token local ausente ou inválido.", request_id=request_id),
                    headers={REQUEST_ID_HEADER: request_id},
                )
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.debug("%s %s -> %s (%.1f ms) id=%s", request.method, request.url.path, response.status_code, elapsed_ms, request_id)
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", TOKEN_HEADER, REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

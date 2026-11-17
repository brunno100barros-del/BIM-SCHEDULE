"""Formato padronizado de erros da API.

Toda resposta de erro tem o formato::

    {
      "error": {"code": "not_found", "message": "Projeto não encontrado.", "details": null,
                "request_id": "..."},
      "detail": "Projeto não encontrado."
    }

``detail`` é mantido por compatibilidade com o formato padrão do FastAPI usado
pelos clientes anteriores.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("api")

STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "too_many_requests",
    500: "internal_error",
    503: "service_unavailable",
}


class AppError(Exception):
    """Erro de domínio com código estável para o frontend."""

    def __init__(self, status_code: int, message: str, *, code: Optional[str] = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code or STATUS_CODES.get(status_code, "error")
        self.details = details


def error_payload(status_code: int, message: str, *, code: Optional[str] = None, details: Any = None,
                  request_id: Optional[str] = None) -> dict:
    return {
        "error": {
            "code": code or STATUS_CODES.get(status_code, "error"),
            "message": message,
            "details": jsonable_encoder(details) if details is not None else None,
            "request_id": request_id,
        },
        "detail": message,
    }


def _request_id(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.status_code, exc.message, code=exc.code, details=exc.details,
                                  request_id=_request_id(request)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "Erro na requisição."
        details = None if isinstance(exc.detail, str) else exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.status_code, message, details=details, request_id=_request_id(request)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        errors = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_payload(422, "Dados inválidos na requisição.", details=errors, request_id=_request_id(request)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("Erro não tratado em %s %s (request_id=%s)", request.method, request.url.path, _request_id(request))
        return JSONResponse(
            status_code=500,
            content=error_payload(500, "Erro interno no serviço BIM SCHEDULE. Consulte o log para detalhes.",
                                  request_id=_request_id(request)),
        )


__all__ = ["AppError", "HTTPException", "error_payload", "register_exception_handlers"]

import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


def register_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def response(request: Request, status: int, code: str, message: str) -> JSONResponse:
        identifier = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": identifier,
                }
            },
            headers={
                "X-Request-ID": identifier,
                **({"WWW-Authenticate": "Bearer"} if status == 401 else {}),
            },
        )

    @app.exception_handler(APIError)
    async def domain_error(request: Request, exc: APIError) -> JSONResponse:
        return response(request, exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo rejected values: they can contain patient information.
        return response(request, 422, "validation_error", "Request validation failed")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return response(request, exc.status_code, "http_error", "Request could not be processed")

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        return response(
            request, 409, "conflict", "Record conflicts with existing data or relationships"
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error(
            "Database failure request_id=%s type=%s", request.state.request_id, type(exc).__name__
        )
        return response(request, 503, "database_unavailable", "Database temporarily unavailable")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled failure request_id=%s type=%s", request.state.request_id, type(exc).__name__
        )
        return response(request, 500, "internal_error", "An unexpected error occurred")

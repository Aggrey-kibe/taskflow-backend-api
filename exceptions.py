"""
core/exceptions.py
------------------
Centralised exception handlers registered on the FastAPI application.
Catches unhandled exceptions and converts them to consistent JSON responses.
This prevents leaking stack traces to clients in production.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("taskflow.exceptions")


def register_exception_handlers(app: FastAPI) -> None:
    """
    Call this once during app startup to attach all global handlers.
    Order matters: more specific handlers should be registered first.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """
        Handles all HTTPExceptions raised by FastAPI routes or dependencies.
        Wraps them in a consistent { "detail": "..." } envelope.
        """
        req_id = getattr(request.state, "request_id", "n/a")
        logger.warning(
            "HTTPException %d: %s  [req_id=%s]  path=%s",
            exc.status_code,
            exc.detail,
            req_id,
            request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Pydantic validation errors — returns structured field-level messages
        so clients know exactly which fields failed and why.
        """
        req_id = getattr(request.state, "request_id", "n/a")
        errors = exc.errors()
        logger.info(
            "Validation error  [req_id=%s]  path=%s  errors=%s",
            req_id,
            request.url.path,
            errors,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation failed",
                "errors": [
                    {
                        "field": " → ".join(str(loc) for loc in err["loc"]),
                        "message": err["msg"],
                        "type": err["type"],
                    }
                    for err in errors
                ],
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Catch-all for any exception that slipped through.
        Logs the full traceback but returns a generic 500 to the client —
        never expose internal details (stack traces, DB errors) to clients.
        """
        req_id = getattr(request.state, "request_id", "n/a")
        logger.exception(
            "Unhandled exception  [req_id=%s]  path=%s",
            req_id,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred. Please try again later.",
                "request_id": req_id,
            },
        )

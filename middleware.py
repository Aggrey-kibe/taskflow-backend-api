"""
core/middleware.py
------------------
ASGI middleware for request/response logging and timing.
Wraps every request so we can log method, path, status code, and duration.
This runs outside FastAPI's routing layer — it sees every request.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("taskflow.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs each incoming request with:
      - A unique request ID (injected into response headers too)
      - HTTP method and path
      - Response status code
      - Total wall-clock duration in milliseconds

    The request ID is invaluable for correlating logs when debugging
    production issues — paste the ID from a client error into your log
    aggregator to see the full request trace.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Attach request ID so downstream code (e.g. services) can read it
        request.state.request_id = request_id

        logger.info(
            "→ %s %s  [req_id=%s]",
            request.method,
            request.url.path,
            request_id,
        )

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "✗ %s %s  [req_id=%s]  duration=%.1fms  unhandled_error=%r",
                request.method,
                request.url.path,
                request_id,
                duration_ms,
                exc,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "← %s %s  [req_id=%s]  status=%d  duration=%.1fms",
            request.method,
            request.url.path,
            request_id,
            response.status_code,
            duration_ms,
        )

        # Propagate the request ID to the client for correlation
        response.headers["X-Request-ID"] = request_id
        return response

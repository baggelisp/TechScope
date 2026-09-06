"""Building the application: wire the service once, register the routes, own the error shape.

The service is built here and kept for the life of the process, rather than per request: it owns
an HTTP connection pool and a compiled fingerprint index, and rebuilding either per request would
turn a scan into a cold start. A caller may inject one instead, which is how the tests drive this
without a network.
"""

import logging
import math
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from techscope.bootstrap import (
    DEFAULT_CONCURRENCY,
    DEFAULT_FINGERPRINTS_PATH,
    DEFAULT_TIMEOUT_SECONDS,
    ScanService,
    ScanSettings,
    build_scan_service,
)
from techscope.presentation.api.body_limit import BodySizeLimitMiddleware
from techscope.presentation.api.errors import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    STATUS_INTERNAL_ERROR,
    STATUS_INVALID_REQUEST,
    UNEXPECTED_FAILURE_MESSAGE,
    ApiError,
    build_error_body,
    decide_error_code,
)
from techscope.presentation.api.routes import SERVICE_STATE_ATTRIBUTE, router
from techscope.presentation.api.schemas import MAXIMUM_SUBMITTED_DOMAINS

logger = logging.getLogger(__name__)

API_TITLE = "TechScope"
API_DESCRIPTION = "Detect the technologies a domain uses from public HTTP and DNS signals."

# Room for the last wave to finish rather than be cut short at the line.
DEADLINE_MARGIN_SECONDS = 5.0
# Not the CLI's 55 s: that number exists to fit the assignment's 60 s budget for twenty domains,
# and this driver accepts more than twenty. A full-cap scan is five waves of ten, each bounded by
# the per-domain timeout, so a shorter deadline would report the last wave as having timed out
# without ever having tried it. Derived, so raising the cap raises this with it.
API_DEADLINE_SECONDS = (
    math.ceil(MAXIMUM_SUBMITTED_DOMAINS / DEFAULT_CONCURRENCY) * DEFAULT_TIMEOUT_SECONDS
    + DEADLINE_MARGIN_SECONDS
)

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(service: ScanService | None = None) -> FastAPI:
    """The application. Pass a service to drive it without building one from the environment."""
    application = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        lifespan=_build_lifespan(service),
    )
    application.add_middleware(BodySizeLimitMiddleware)
    application.include_router(router)
    _register_error_handlers(application)

    return application


def build_default_settings() -> ScanSettings:
    """What a server scans with when nobody said otherwise."""
    return ScanSettings(
        fingerprints_path=DEFAULT_FINGERPRINTS_PATH,
        nameservers=(),
        concurrency=DEFAULT_CONCURRENCY,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        deadline_seconds=API_DEADLINE_SECONDS,
    )


def _build_lifespan(service: ScanService | None) -> Lifespan:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if service is not None:
            setattr(application.state, SERVICE_STATE_ATTRIBUTE, service)

            yield

            return

        async with build_scan_service(build_default_settings()) as built:
            setattr(application.state, SERVICE_STATE_ATTRIBUTE, built)

            yield

    return lifespan


def _register_error_handlers(application: FastAPI) -> None:
    application.add_exception_handler(ApiError, _handle_api_error)
    application.add_exception_handler(RequestValidationError, _handle_validation_error)
    application.add_exception_handler(StarletteHTTPException, _handle_http_error)
    application.add_exception_handler(Exception, _handle_unexpected_error)


async def _handle_api_error(_request: Request, error: Exception) -> JSONResponse:
    api_error = _decide_api_error(error)

    return JSONResponse(
        status_code=api_error.status_code,
        content=build_error_body(api_error.code, api_error.message),
    )


async def _handle_validation_error(_request: Request, error: Exception) -> JSONResponse:
    """FastAPI's own body is a list of locations; a caller of ours gets a sentence instead.

    What is logged is how the body was wrong, never what was in it: the framework's message
    embeds the offending input verbatim, so logging it hands a caller an unbounded write of
    text of its choosing — newlines included — into the log this container ships.
    """
    logger.info("refusing a malformed request: %s", _describe_validation_error(error))

    return JSONResponse(
        status_code=STATUS_INVALID_REQUEST,
        content=build_error_body(INVALID_REQUEST, "the request body is not a valid scan request"),
    )


async def _handle_http_error(_request: Request, error: Exception) -> JSONResponse:
    status_code = _decide_status_code(error)

    return JSONResponse(
        status_code=status_code,
        content=build_error_body(decide_error_code(status_code), _decide_message(error)),
    )


async def _handle_unexpected_error(_request: Request, error: Exception) -> JSONResponse:
    """The last resort. What went wrong is logged here and never described to the caller."""
    logger.exception("unexpected failure serving a request", exc_info=error)

    return JSONResponse(
        status_code=STATUS_INTERNAL_ERROR,
        content=build_error_body(INTERNAL_ERROR, UNEXPECTED_FAILURE_MESSAGE),
    )


def _describe_validation_error(error: Exception) -> str:
    if not isinstance(error, RequestValidationError):
        return "the body could not be validated"

    problems = error.errors()
    kinds = sorted({str(problem.get("type", "unknown")) for problem in problems})

    return f"{len(problems)} problem(s): {', '.join(kinds)}"


def _decide_api_error(error: Exception) -> ApiError:
    if isinstance(error, ApiError):
        return error

    return ApiError(
        status_code=STATUS_INTERNAL_ERROR,
        code=INTERNAL_ERROR,
        message=UNEXPECTED_FAILURE_MESSAGE,
    )


def _decide_status_code(error: Exception) -> int:
    if isinstance(error, StarletteHTTPException):
        return error.status_code

    return STATUS_INTERNAL_ERROR


def _decide_message(error: Exception) -> str:
    if isinstance(error, StarletteHTTPException):
        return str(error.detail)

    return UNEXPECTED_FAILURE_MESSAGE

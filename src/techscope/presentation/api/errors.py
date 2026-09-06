"""One shape for everything that goes wrong, so a caller never has to parse a traceback.

A driver that leaks its framework's error format leaks its framework. The web app branches on
``code``; ``message`` is for a person reading it.
"""

from dataclasses import dataclass

INVALID_REQUEST = "invalid_request"
NOT_FOUND = "not_found"
METHOD_NOT_ALLOWED = "method_not_allowed"
INTERNAL_ERROR = "internal_error"
SERVICE_UNAVAILABLE = "service_unavailable"
UNEXPECTED = "error"

STATUS_INVALID_REQUEST = 422
STATUS_INTERNAL_ERROR = 500
STATUS_SERVICE_UNAVAILABLE = 503

# The framework raises its own errors for routing; each still leaves as one of ours.
ERROR_CODE_BY_STATUS = {
    400: INVALID_REQUEST,
    404: NOT_FOUND,
    405: METHOD_NOT_ALLOWED,
    422: INVALID_REQUEST,
    500: INTERNAL_ERROR,
    503: SERVICE_UNAVAILABLE,
}

UNEXPECTED_FAILURE_MESSAGE = "the request could not be completed"


@dataclass(frozen=True, slots=True)
class ApiError(Exception):
    """A refusal this driver decided on, already carrying how it should be answered."""

    status_code: int
    code: str
    message: str

    @classmethod
    def invalid_request(cls, message: str) -> "ApiError":
        return cls(status_code=STATUS_INVALID_REQUEST, code=INVALID_REQUEST, message=message)

    @classmethod
    def unavailable(cls, message: str) -> "ApiError":
        return cls(
            status_code=STATUS_SERVICE_UNAVAILABLE, code=SERVICE_UNAVAILABLE, message=message
        )


def build_error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def decide_error_code(status_code: int) -> str:
    return ERROR_CODE_BY_STATUS.get(status_code, UNEXPECTED)

"""Opaque request and long-task correlation identifiers."""
from __future__ import annotations

from uuid import UUID, uuid4

from starlette.requests import Request


REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"


def normalize_diagnostic_id(value: object) -> str | None:
    """Return a lowercase UUID hex value or reject unsafe caller input."""
    if not isinstance(value, str) or len(value) not in {32, 36}:
        return None
    try:
        return UUID(value).hex
    except (ValueError, AttributeError):
        return None


def new_diagnostic_id() -> str:
    return uuid4().hex


def get_request_id(request: Request) -> str:
    existing = normalize_diagnostic_id(getattr(request.state, "request_id", None))
    if existing is not None:
        return existing
    request_id = normalize_diagnostic_id(request.headers.get(REQUEST_ID_HEADER))
    request_id = request_id or new_diagnostic_id()
    request.state.request_id = request_id
    return request_id


def get_correlation_id(request: Request) -> str:
    existing = normalize_diagnostic_id(getattr(request.state, "correlation_id", None))
    if existing is not None:
        return existing
    correlation_id = normalize_diagnostic_id(
        request.headers.get(CORRELATION_ID_HEADER)
    )
    correlation_id = correlation_id or new_diagnostic_id()
    request.state.correlation_id = correlation_id
    return correlation_id

"""Exception hierarchy for the Lime Go Agentic SDK.

Every error raised by the SDK derives from :class:`LimeGoError`. Non-2xx API responses
raise an :class:`APIStatusError` subclass carrying the parsed JSON:API ``errors`` array,
whose ``code`` values are documented by Lime as stable (e.g. ``relationship_too_large``,
``unavailable``), so callers can branch on ``exc.code`` rather than on message text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class LimeGoError(Exception):
    """Base class for every error raised by this SDK."""


class ConfigurationError(LimeGoError):
    """Raised when the client is misconfigured (missing credentials, unknown environment)."""


class AuthenticationError(LimeGoError):
    """Raised when an access token could not be obtained from ``/oauth/token``."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class MissingETagError(LimeGoError):
    """Raised when an ``If-Match`` value is required but none is available.

    PATCH, DELETE and relationship writes require the resource's current ETag. Resources
    returned by ``get``/``create``/``update``/``upsert`` carry the response ETag; other
    resources derive it from ``meta.revision``. Only resources without a revision (and
    no response ETag) raise this.
    """


class APIError(LimeGoError):
    """Base class for errors returned by an API call."""


class APIConnectionError(APIError):
    """Raised when the request could not be sent or no response was received."""


class APITimeoutError(APIConnectionError):
    """Raised when a request exceeds the configured timeout."""


@dataclass(frozen=True)
class ErrorObject:
    """One entry of a JSON:API ``errors`` array."""

    status: str | None = None
    code: str | None = None
    title: str | None = None
    detail: str | None = None
    source: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ErrorObject":
        source = raw.get("source")
        meta = raw.get("meta")
        return cls(
            status=_opt_str(raw.get("status")),
            code=_opt_str(raw.get("code")),
            title=_opt_str(raw.get("title")),
            detail=_opt_str(raw.get("detail")),
            source=source if isinstance(source, dict) else None,
            meta=meta if isinstance(meta, dict) else {},
        )


class APIStatusError(APIError):
    """Raised when the API returns a non-2xx HTTP status.

    Attributes
    ----------
    status_code:
        The HTTP status code.
    errors:
        The parsed JSON:API ``errors`` array (empty if the body was not JSON:API).
    code:
        The ``code`` of the first error, or ``None``. Lime documents codes as stable.
    body:
        The raw parsed body (JSON or text).
    request_id:
        The ``x-request-id`` header, useful when raising a support case with Lime.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        errors: list[ErrorObject] | None = None,
        body: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors or []
        self.body = body
        self.request_id = request_id

    @property
    def code(self) -> str | None:
        return self.errors[0].code if self.errors else None

    def __str__(self) -> str:
        base = super().__str__()
        parts = [f"status={self.status_code}"]
        if self.code:
            parts.append(f"code={self.code}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return f"{base} ({', '.join(parts)})"


class BadRequestError(APIStatusError):
    """HTTP 400 - malformed request (bad query parameter, invalid JSON:API document)."""


class UnauthorizedError(APIStatusError):
    """HTTP 401 - token missing, expired or invalid."""


class ForbiddenError(APIStatusError):
    """HTTP 403 - authenticated but missing the required OAuth scope."""


class NotFoundError(APIStatusError):
    """HTTP 404."""


class NotAcceptableError(APIStatusError):
    """HTTP 406 - the ``Accept`` header was not ``application/vnd.api+json``."""


class ConflictError(APIStatusError):
    """HTTP 409 - e.g. ``relationship_too_large`` or an idempotency-key conflict."""


class GoneError(APIStatusError):
    """HTTP 410 - the resource (or a sync cursor) no longer exists."""


class PreconditionFailedError(APIStatusError):
    """HTTP 412 - the ``If-Match`` ETag is stale; re-read the resource and retry."""


class PayloadTooLargeError(APIStatusError):
    """HTTP 413."""


class UnsupportedMediaTypeError(APIStatusError):
    """HTTP 415 - the request ``Content-Type`` was not ``application/vnd.api+json``."""


class UnprocessableEntityError(APIStatusError):
    """HTTP 422 - validation failed."""


class PreconditionRequiredError(APIStatusError):
    """HTTP 428 - the request needs an ``If-Match`` header."""


class RateLimitError(APIStatusError):
    """HTTP 429 - per-instance limit reached."""


class ServerError(APIStatusError):
    """HTTP 5xx."""


class ServiceUnavailableError(ServerError):
    """HTTP 503 - the API is temporarily unavailable (code ``unavailable``)."""


_STATUS_TO_EXC: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    406: NotAcceptableError,
    409: ConflictError,
    410: GoneError,
    412: PreconditionFailedError,
    413: PayloadTooLargeError,
    415: UnsupportedMediaTypeError,
    422: UnprocessableEntityError,
    428: PreconditionRequiredError,
    429: RateLimitError,
    503: ServiceUnavailableError,
}


def status_error_from_response(
    status_code: int,
    *,
    body: Any = None,
    request_id: str | None = None,
) -> APIStatusError:
    """Build the most specific :class:`APIStatusError` for ``status_code``."""
    exc_type = _STATUS_TO_EXC.get(status_code)
    if exc_type is None:
        exc_type = ServerError if status_code >= 500 else APIStatusError
    errors = _parse_errors(body)
    message = _message(errors) or f"Lime Go API returned HTTP {status_code}"
    return exc_type(message, status_code=status_code, errors=errors, body=body, request_id=request_id)


def _parse_errors(body: Any) -> list[ErrorObject]:
    if not isinstance(body, dict):
        return []
    raw = body.get("errors")
    if not isinstance(raw, list):
        return []
    return [ErrorObject.from_dict(e) for e in raw if isinstance(e, dict)]


def _message(errors: list[ErrorObject]) -> str | None:
    texts = [e.detail or e.title for e in errors if e.detail or e.title]
    return "; ".join(t for t in texts if t) or None


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)

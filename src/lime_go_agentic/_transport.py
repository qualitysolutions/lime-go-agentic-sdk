"""Low-level HTTP transport shared by the sync and async clients.

Responsibilities:
  * acquire and cache the OAuth2 bearer token (refreshing when stale, and once on 401),
  * speak JSON:API (``application/vnd.api+json`` for ``Accept`` and request bodies),
  * give every write an ``Idempotency-Key`` (required by the API) that stays the SAME
    across retries, which is what makes retrying a POST/PATCH/PUT/DELETE safe,
  * retry on transient network errors, 429 and 5xx, honouring ``Retry-After`` up to
    ``Config.max_retry_after``,
  * map non-2xx responses to the SDK exception hierarchy.

The sync and async send loops are intentionally duplicated because httpx's sync and
async APIs are not interchangeable; everything else is shared free functions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from ._auth import AccessToken, OAuth2ClientCredentials
from .config import Config
from .errors import APIConnectionError, APITimeoutError, status_error_from_response

logger = logging.getLogger("lime_go_agentic")

JSONAPI_MEDIA_TYPE = "application/vnd.api+json"
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class Response:
    """A successful (2xx) response: parsed body plus the headers the SDK needs."""

    status_code: int
    body: Any
    etag: str | None
    request_id: str | None


def _parse_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


def _request_id(response: httpx.Response) -> str | None:
    value: str | None = response.headers.get("x-request-id")
    return value


def _handle_response(response: httpx.Response) -> Response:
    rid = _request_id(response)
    if 200 <= response.status_code < 300:
        return Response(
            status_code=response.status_code,
            body=_parse_body(response),
            etag=response.headers.get("etag"),
            request_id=rid,
        )
    raise status_error_from_response(response.status_code, body=_parse_body(response), request_id=rid)


def _retry_delay(attempt: int, response: httpx.Response | None) -> float:
    """Exponential backoff, or the server's ``Retry-After`` when present."""
    if response is not None:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass
    return float(min(2.0**attempt * 0.5, 8.0))


def _should_retry_status(config: Config, attempt: int, response: httpx.Response) -> float | None:
    """Return the delay before retrying ``response``, or None to stop and raise."""
    if response.status_code not in _RETRY_STATUSES or attempt >= config.max_retries:
        return None
    delay = _retry_delay(attempt, response)
    if delay > config.max_retry_after:
        logger.warning(
            "server asked to retry after %.0fs (> max_retry_after=%.0fs); not retrying",
            delay, config.max_retry_after,
        )
        return None
    return delay


def _log_response(method: str, url: str, response: httpx.Response, started: float) -> None:
    """Log the outcome at DEBUG (no bodies/headers -> no secrets/PII)."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    elapsed_ms = (time.perf_counter() - started) * 1000
    rid = _request_id(response)
    logger.debug(
        "%s %s -> %d (%.0f ms)%s",
        method, url, response.status_code, elapsed_ms, f" request_id={rid}" if rid else "",
    )


def _build_url(config: Config, path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    return f"{config.base_url}/{path.lstrip('/')}"


def _prepare(
    config: Config,
    method: str,
    json_body: Any,
    headers: Mapping[str, str] | None,
) -> tuple[bytes | None, dict[str, str]]:
    """Encode the body and build the per-call headers (minus Authorization)."""
    out: dict[str, str] = {"Accept": JSONAPI_MEDIA_TYPE}
    out.update(config.default_headers)
    if headers:
        out.update(headers)
    content: bytes | None = None
    if json_body is not None:
        content = json.dumps(json_body, separators=(",", ":")).encode()
        out["Content-Type"] = JSONAPI_MEDIA_TYPE
    if method in _WRITE_METHODS and not any(k.lower() == "idempotency-key" for k in out):
        out["Idempotency-Key"] = str(uuid.uuid4())
    return content, out


class SyncTransport:
    """Synchronous transport backed by :class:`httpx.Client`."""

    def __init__(self, config: Config, *, client: httpx.Client | None = None) -> None:
        self._config = config
        self._auth = OAuth2ClientCredentials(config)
        self._token: AccessToken | None = None
        self._lock = threading.Lock()
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=config.timeout, verify=config.verify_tls)

    def _get_token(self, *, force_refresh: bool = False) -> str:
        with self._lock:
            if force_refresh or self._token is None or not self._token.is_valid():
                self._token = self._auth.fetch_sync(self._client)
            return self._token.value

    @property
    def granted_scopes(self) -> tuple[str, ...]:
        """Scopes of the current token (fetching one if needed)."""
        self._get_token()
        assert self._token is not None
        return self._token.scopes

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        method = method.upper()
        url = _build_url(self._config, path)
        content, base_headers = _prepare(self._config, method, json, headers)
        attempt = 0
        token_retried = False
        while True:
            request_headers = {**base_headers, "Authorization": f"Bearer {self._get_token()}"}
            logger.debug("%s %s (attempt %d)", method, url, attempt + 1)
            started = time.perf_counter()
            try:
                response = self._client.request(
                    method, url, content=content, params=params, headers=request_headers
                )
            except httpx.TimeoutException as exc:
                if attempt < self._config.max_retries:
                    logger.warning("timeout on %s %s; retrying (%d/%d)", method, url,
                                   attempt + 1, self._config.max_retries)
                    time.sleep(_retry_delay(attempt, None))
                    attempt += 1
                    continue
                raise APITimeoutError(f"Request to {url} timed out: {exc}") from exc
            except httpx.HTTPError as exc:
                if attempt < self._config.max_retries:
                    logger.warning("network error on %s %s: %s; retrying (%d/%d)", method, url,
                                   exc, attempt + 1, self._config.max_retries)
                    time.sleep(_retry_delay(attempt, None))
                    attempt += 1
                    continue
                raise APIConnectionError(f"Request to {url} failed: {exc}") from exc

            _log_response(method, url, response, started)
            if response.status_code == 401 and not token_retried:
                logger.debug("401 on %s %s; refreshing token and retrying once", method, url)
                token_retried = True
                self._get_token(force_refresh=True)
                continue
            delay = _should_retry_status(self._config, attempt, response)
            if delay is not None:
                logger.warning("%s %s returned %d; retrying in %.1fs (%d/%d)", method, url,
                               response.status_code, delay, attempt + 1, self._config.max_retries)
                time.sleep(delay)
                attempt += 1
                continue
            return _handle_response(response)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class AsyncTransport:
    """Asynchronous transport backed by :class:`httpx.AsyncClient`."""

    def __init__(self, config: Config, *, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._auth = OAuth2ClientCredentials(config)
        self._token: AccessToken | None = None
        self._lock = asyncio.Lock()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=config.timeout, verify=config.verify_tls)

    async def _get_token(self, *, force_refresh: bool = False) -> str:
        async with self._lock:
            if force_refresh or self._token is None or not self._token.is_valid():
                self._token = await self._auth.fetch_async(self._client)
            return self._token.value

    async def granted_scopes(self) -> tuple[str, ...]:
        """Scopes of the current token (fetching one if needed)."""
        await self._get_token()
        assert self._token is not None
        return self._token.scopes

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        method = method.upper()
        url = _build_url(self._config, path)
        content, base_headers = _prepare(self._config, method, json, headers)
        attempt = 0
        token_retried = False
        while True:
            request_headers = {**base_headers, "Authorization": f"Bearer {await self._get_token()}"}
            logger.debug("%s %s (attempt %d)", method, url, attempt + 1)
            started = time.perf_counter()
            try:
                response = await self._client.request(
                    method, url, content=content, params=params, headers=request_headers
                )
            except httpx.TimeoutException as exc:
                if attempt < self._config.max_retries:
                    logger.warning("timeout on %s %s; retrying (%d/%d)", method, url,
                                   attempt + 1, self._config.max_retries)
                    await asyncio.sleep(_retry_delay(attempt, None))
                    attempt += 1
                    continue
                raise APITimeoutError(f"Request to {url} timed out: {exc}") from exc
            except httpx.HTTPError as exc:
                if attempt < self._config.max_retries:
                    logger.warning("network error on %s %s: %s; retrying (%d/%d)", method, url,
                                   exc, attempt + 1, self._config.max_retries)
                    await asyncio.sleep(_retry_delay(attempt, None))
                    attempt += 1
                    continue
                raise APIConnectionError(f"Request to {url} failed: {exc}") from exc

            _log_response(method, url, response, started)
            if response.status_code == 401 and not token_retried:
                logger.debug("401 on %s %s; refreshing token and retrying once", method, url)
                token_retried = True
                await self._get_token(force_refresh=True)
                continue
            delay = _should_retry_status(self._config, attempt, response)
            if delay is not None:
                logger.warning("%s %s returned %d; retrying in %.1fs (%d/%d)", method, url,
                               response.status_code, delay, attempt + 1, self._config.max_retries)
                await asyncio.sleep(delay)
                attempt += 1
                continue
            return _handle_response(response)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

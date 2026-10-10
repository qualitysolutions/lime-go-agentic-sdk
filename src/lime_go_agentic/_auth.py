"""OAuth 2.0 client-credentials token handling.

The API issues **opaque** bearer tokens from ``POST {base_url}/oauth/token``
(``application/x-www-form-urlencoded``: ``grant_type=client_credentials``,
``client_id``, ``client_secret``, optional ``scope``). Tokens live 1800 s and there is no
refresh token, so the transports simply fetch a new one when the cached one is stale.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Config
from .errors import AuthenticationError

logger = logging.getLogger("lime_go_agentic")


@dataclass(frozen=True)
class AccessToken:
    """A cached bearer token, the scopes it was granted and when it becomes stale."""

    value: str
    #: Epoch seconds after which the token should be refreshed (leeway applied).
    expires_at: float
    scopes: tuple[str, ...] = ()

    def is_valid(self, *, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) < self.expires_at


class OAuth2ClientCredentials:
    """Fetches and parses tokens. Stateless; the transports own the cache."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def _form_body(self) -> dict[str, str]:
        body = {
            "grant_type": "client_credentials",
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
        }
        if self._config.scopes:
            body["scope"] = " ".join(self._config.scopes)
        return body

    def fetch_sync(self, client: httpx.Client) -> AccessToken:
        try:
            response = client.post(
                self._config.token_url,
                data=self._form_body(),
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"Failed to reach the token endpoint: {exc}") from exc
        return self._parse(response)

    async def fetch_async(self, client: httpx.AsyncClient) -> AccessToken:
        try:
            response = await client.post(
                self._config.token_url,
                data=self._form_body(),
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise AuthenticationError(f"Failed to reach the token endpoint: {exc}") from exc
        return self._parse(response)

    def _parse(self, response: httpx.Response) -> AccessToken:
        if response.status_code != 200:
            raise AuthenticationError(
                "The token endpoint rejected the client-credentials request",
                status_code=response.status_code,
                body=_safe_json(response),
            )
        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise AuthenticationError("Token response was not JSON", body=response.text) from exc
        token = data.get("access_token")
        if not token:
            # Do not echo the body: it is a credential response.
            raise AuthenticationError("Token response did not contain an access_token")
        try:
            lifetime = float(data.get("expires_in", 1800))
        except (TypeError, ValueError):
            lifetime = 300.0
        scope = data.get("scope")
        scopes = tuple(scope.split()) if isinstance(scope, str) else ()
        # Never log the token value; only its lifetime and scopes.
        logger.debug("obtained access token (valid %ds, scopes=%s)", int(lifetime), " ".join(scopes))
        return AccessToken(
            value=token,
            expires_at=time.time() + lifetime - self._config.token_expiry_leeway,
            scopes=scopes,
        )


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text

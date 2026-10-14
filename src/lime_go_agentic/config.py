"""Configuration for the Lime Go Agentic SDK client."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .errors import ConfigurationError

#: Known environments and their base URLs. Only staging is published so far (the
#: OpenAPI spec has no ``servers`` entry); for any other instance pass ``base_url``.
ENVIRONMENT_URLS = {
    "staging": "https://agentic.staging.lime-go.com",
}

#: Every OAuth scope declared by the API. Request only the ones an integration needs.
ALL_SCOPES = (
    "activities:read", "activities:write", "activities:delete",
    "changes:read",
    "companies:read", "companies:write", "companies:delete",
    "contacts:read", "contacts:write", "contacts:delete",
    "deals:read", "deals:write", "deals:delete",
    "reference:read",
    "tasks:read", "tasks:write", "tasks:delete",
)


@dataclass
class Config:
    """Configuration for a Lime Go Agentic client.

    ``client_id``/``client_secret`` are the confidential OAuth client credentials issued
    for your integration. The base URL is either given explicitly (``base_url``) or
    derived from ``environment`` (see :data:`ENVIRONMENT_URLS`). There is deliberately
    **no default environment**, so a misconfigured deploy cannot silently write to the
    wrong instance.

    ``scopes`` limits the token to the listed scopes (sent as the space-separated
    ``scope`` form field). A single space-separated string is accepted too. ``None`` sends no ``scope`` and lets the server grant the
    client's configured default.

    :meth:`from_env` reads ``LIME_GO_*`` variables (see its docstring).
    """

    client_id: str
    client_secret: str
    environment: str | None = None
    base_url: str | None = None
    scopes: tuple[str, ...] | str | None = None

    # Networking.
    timeout: float = 30.0
    max_retries: int = 2
    #: Longest ``Retry-After`` (seconds) the SDK will sleep for on 429/503. A longer
    #: server-requested wait raises the error instead of blocking the caller.
    max_retry_after: float = 30.0
    verify_tls: bool = True
    #: Seconds subtracted from a token's lifetime (1800 s) before refreshing it.
    token_expiry_leeway: float = 60.0
    #: Optional extra headers applied to every API request.
    default_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.client_id:
            raise ConfigurationError("client_id is required")
        if not self.client_secret:
            raise ConfigurationError("client_secret is required")
        if self.environment:
            self.environment = self.environment.lower()
        if not self.base_url:
            if not self.environment:
                raise ConfigurationError(
                    "Set base_url, or environment to one of "
                    f"{sorted(ENVIRONMENT_URLS)} (LIME_GO_ENV / LIME_GO_BASE_URL)"
                )
            if self.environment not in ENVIRONMENT_URLS:
                raise ConfigurationError(
                    f"Unknown environment {self.environment!r}; set base_url explicitly "
                    f"or use one of {sorted(ENVIRONMENT_URLS)}"
                )
            self.base_url = ENVIRONMENT_URLS[self.environment]
        self.base_url = self.base_url.rstrip("/")
        if isinstance(self.scopes, str):
            # tuple("a b") would send one scope per character.
            self.scopes = tuple(self.scopes.split())
        elif self.scopes is not None:
            self.scopes = tuple(self.scopes)

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/oauth/token"

    @classmethod
    def from_env(cls, **overrides: object) -> "Config":
        """Build a :class:`Config` from ``LIME_GO_*`` environment variables.

        ``LIME_GO_ENV`` selects the environment. Each value is looked up
        environment-first, so one ``.env`` can hold several instances::

            LIME_GO_ENV=staging
            LIME_GO_STAGING_CLIENT_ID=...      LIME_GO_PROD_CLIENT_ID=...
            LIME_GO_STAGING_CLIENT_SECRET=...  LIME_GO_PROD_CLIENT_SECRET=...
            LIME_GO_PROD_BASE_URL=https://...

        Variables: ``CLIENT_ID``, ``CLIENT_SECRET``, ``BASE_URL`` (optional when the
        environment is known) and ``SCOPES`` (optional, space-separated). Keyword
        overrides win over everything.
        """
        env = (os.getenv("LIME_GO_ENV") or "").lower() or None
        prefix = f"LIME_GO_{env.upper()}_" if env else None

        def pick(name: str) -> str | None:
            if prefix and os.getenv(prefix + name):
                return os.getenv(prefix + name)
            return os.getenv("LIME_GO_" + name) or None

        scopes_raw = pick("SCOPES")
        values: dict[str, object] = {
            "client_id": pick("CLIENT_ID") or "",
            "client_secret": pick("CLIENT_SECRET") or "",
            "environment": env,
            "base_url": pick("BASE_URL"),
            "scopes": tuple(scopes_raw.split()) if scopes_raw else None,
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]

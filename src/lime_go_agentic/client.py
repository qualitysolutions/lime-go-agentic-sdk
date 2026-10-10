"""Public sync and async clients for the Lime Go Agentic API."""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from ._transport import AsyncTransport, Response, SyncTransport
from .config import Config
from .resources import (
    Activities,
    ActivityTypes,
    AsyncActivities,
    AsyncActivityTypes,
    AsyncChanges,
    AsyncCompanies,
    AsyncContacts,
    AsyncCustomFieldDefinitions,
    AsyncDeals,
    AsyncOwners,
    AsyncStages,
    AsyncTags,
    AsyncTasks,
    Changes,
    Companies,
    Contacts,
    CustomFieldDefinitions,
    Deals,
    Owners,
    Stages,
    Tags,
    Tasks,
)


def _coerce_config(config: Config | None, kwargs: dict[str, Any]) -> Config:
    if config is not None:
        if kwargs:
            raise TypeError("Pass either a Config or credential keyword arguments, not both")
        return config
    return Config.from_env(**kwargs)


class LimeGoClient:
    """Synchronous client for the Lime Go Agentic API.

    Construct with a :class:`Config`, with keyword arguments, or with nothing (reads
    ``LIME_GO_*`` environment variables)::

        with LimeGoClient(client_id="...", client_secret="...", environment="staging") as lime:
            for company in lime.companies.iter({"status": "customer"}):
                print(company.id, company.attributes.name)
    """

    def __init__(
        self,
        config: Config | None = None,
        *,
        http_client: httpx.Client | None = None,
        **credentials: Any,
    ) -> None:
        self._config = _coerce_config(config, credentials)
        self._transport = SyncTransport(self._config, client=http_client)
        t = self._transport

        self.companies = Companies(t)
        self.contacts = Contacts(t)
        self.deals = Deals(t)
        self.activities = Activities(t)
        self.tasks = Tasks(t)
        self.owners = Owners(t)
        self.stages = Stages(t)
        self.tags = Tags(t)
        self.activity_types = ActivityTypes(t)
        self.custom_field_definitions = CustomFieldDefinitions(t)
        self.changes = Changes(t)

    @property
    def config(self) -> Config:
        return self._config

    @property
    def granted_scopes(self) -> tuple[str, ...]:
        """The OAuth scopes the server granted this client's token."""
        return self._transport.granted_scopes

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        """Escape hatch: an authenticated JSON:API call to any path (relative to
        ``base_url``) or absolute URL. Writes get an ``Idempotency-Key`` automatically."""
        return self._transport.request(method, path, json=json, params=params, headers=headers)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "LimeGoClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class AsyncLimeGoClient:
    """Asynchronous client; mirrors :class:`LimeGoClient` with coroutine methods::

        async with AsyncLimeGoClient() as lime:
            async for deal in lime.deals.iter():
                ...
    """

    def __init__(
        self,
        config: Config | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        **credentials: Any,
    ) -> None:
        self._config = _coerce_config(config, credentials)
        self._transport = AsyncTransport(self._config, client=http_client)
        t = self._transport

        self.companies = AsyncCompanies(t)
        self.contacts = AsyncContacts(t)
        self.deals = AsyncDeals(t)
        self.activities = AsyncActivities(t)
        self.tasks = AsyncTasks(t)
        self.owners = AsyncOwners(t)
        self.stages = AsyncStages(t)
        self.tags = AsyncTags(t)
        self.activity_types = AsyncActivityTypes(t)
        self.custom_field_definitions = AsyncCustomFieldDefinitions(t)
        self.changes = AsyncChanges(t)

    @property
    def config(self) -> Config:
        return self._config

    async def granted_scopes(self) -> tuple[str, ...]:
        return await self._transport.granted_scopes()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        return await self._transport.request(method, path, json=json, params=params, headers=headers)

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> "AsyncLimeGoClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

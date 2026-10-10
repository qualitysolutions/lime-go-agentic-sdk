"""Concrete resource namespaces exposed on the clients."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from .._transport import AsyncTransport, Response, SyncTransport
from ..errors import LimeGoError
from ..models import (
    Activity,
    ActivityCreate,
    ActivityFilter,
    ActivityType,
    ActivityUpdate,
    Change,
    ChangePage,
    Company,
    CompanyCreate,
    CompanyFilter,
    CompanyUpdate,
    Contact,
    ContactCreate,
    ContactFilter,
    ContactUpdate,
    CustomFieldDefinition,
    Deal,
    DealCreate,
    DealFilter,
    DealUpdate,
    NameFilter,
    NoFilter,
    Owner,
    Stage,
    Tag,
    Task,
    TaskCreate,
    TaskFilter,
    TaskUpdate,
    UpdatedSinceFilter,
)
from ._base import (
    AsyncCrudResource,
    AsyncReadResource,
    AsyncRelationship,
    SyncCrudResource,
    SyncReadResource,
    SyncRelationship,
)

API = "/api/v1"


# -- sync ------------------------------------------------------------------------------
class Companies(SyncCrudResource[Company, CompanyFilter, CompanyCreate, CompanyUpdate]):
    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/companies", "companies", Company)
        self.tags = SyncRelationship(transport, self._path, "tags", "tags")


class Contacts(SyncCrudResource[Contact, ContactFilter, ContactCreate, ContactUpdate]):
    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/contacts", "contacts", Contact)
        self.tags = SyncRelationship(transport, self._path, "tags", "tags")


class Deals(SyncCrudResource[Deal, DealFilter, DealCreate, DealUpdate]):
    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/deals", "deals", Deal)
        self.contacts = SyncRelationship(transport, self._path, "contacts", "contacts")
        self.owners = SyncRelationship(transport, self._path, "owners", "owners")
        self.tags = SyncRelationship(transport, self._path, "tags", "tags")


class Activities(SyncCrudResource[Activity, ActivityFilter, ActivityCreate, ActivityUpdate]):
    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/activities", "activities", Activity)


class Tasks(SyncCrudResource[Task, TaskFilter, TaskCreate, TaskUpdate]):
    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/tasks", "tasks", Task)
        self.companies = SyncRelationship(transport, self._path, "companies", "companies")
        self.contacts = SyncRelationship(transport, self._path, "contacts", "contacts")
        self.deals = SyncRelationship(transport, self._path, "deals", "deals")


class Owners(SyncReadResource[Owner, NoFilter]):
    """Active organisation members. Supports paging only (no filter/sort/fields)."""

    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/owners", "owners", Owner)


class Stages(SyncReadResource[Stage, NameFilter]):
    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/stages", "stages", Stage)


class Tags(SyncReadResource[Tag, NameFilter]):
    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/tags", "tags", Tag)


class ActivityTypes(SyncReadResource[ActivityType, NameFilter]):
    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/activity-types", "activity-types", ActivityType)


class CustomFieldDefinitions(SyncReadResource[CustomFieldDefinition, UpdatedSinceFilter]):
    def __init__(self, transport: SyncTransport) -> None:
        super().__init__(transport, f"{API}/custom-field-definitions", "custom-field-definitions",
                         CustomFieldDefinition)


#: Query parameter carrying the resume cursor on ``GET /changes``. UNVERIFIED: the spec
#: returns ``meta.cursor`` but documents no request parameter; confirm with Lime.
CHANGES_CURSOR_PARAM = "cursor"


def _parse_changes(response: Response) -> ChangePage:
    body: Any = response.body
    if not isinstance(body, dict) or "meta" not in body:
        raise LimeGoError(f"Unexpected /changes body: request_id={response.request_id}")
    meta = body["meta"]
    return ChangePage(
        data=[Change.model_validate(item) for item in body.get("data") or []],
        cursor=meta["cursor"],
        has_more=bool(meta.get("has_more", False)),
        checkpoint=bool(meta.get("checkpoint", False)),
    )


class Changes:
    """The change feed for incremental sync (scope ``changes:read``).

    Typical loop: call ``read()`` once without a cursor to get a checkpoint, persist
    ``page.cursor``, then periodically ``iter_pages(cursor)`` and persist the last cursor.
    """

    def __init__(self, transport: SyncTransport) -> None:
        self._t = transport

    def read(self, cursor: str | None = None) -> ChangePage:
        params = {CHANGES_CURSOR_PARAM: cursor} if cursor else None
        return _parse_changes(self._t.request("GET", f"{API}/changes", params=params))

    def iter_pages(self, cursor: str | None = None) -> Iterator[ChangePage]:
        """Read pages until caught up (``has_more`` false). Persist each page's cursor."""
        while True:
            page = self.read(cursor)
            yield page
            if not page.has_more:
                return
            cursor = page.cursor


# -- async -----------------------------------------------------------------------------
class AsyncCompanies(AsyncCrudResource[Company, CompanyFilter, CompanyCreate, CompanyUpdate]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/companies", "companies", Company)
        self.tags = AsyncRelationship(transport, self._path, "tags", "tags")


class AsyncContacts(AsyncCrudResource[Contact, ContactFilter, ContactCreate, ContactUpdate]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/contacts", "contacts", Contact)
        self.tags = AsyncRelationship(transport, self._path, "tags", "tags")


class AsyncDeals(AsyncCrudResource[Deal, DealFilter, DealCreate, DealUpdate]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/deals", "deals", Deal)
        self.contacts = AsyncRelationship(transport, self._path, "contacts", "contacts")
        self.owners = AsyncRelationship(transport, self._path, "owners", "owners")
        self.tags = AsyncRelationship(transport, self._path, "tags", "tags")


class AsyncActivities(AsyncCrudResource[Activity, ActivityFilter, ActivityCreate, ActivityUpdate]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/activities", "activities", Activity)


class AsyncTasks(AsyncCrudResource[Task, TaskFilter, TaskCreate, TaskUpdate]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/tasks", "tasks", Task)
        self.companies = AsyncRelationship(transport, self._path, "companies", "companies")
        self.contacts = AsyncRelationship(transport, self._path, "contacts", "contacts")
        self.deals = AsyncRelationship(transport, self._path, "deals", "deals")


class AsyncOwners(AsyncReadResource[Owner, NoFilter]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/owners", "owners", Owner)


class AsyncStages(AsyncReadResource[Stage, NameFilter]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/stages", "stages", Stage)


class AsyncTags(AsyncReadResource[Tag, NameFilter]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/tags", "tags", Tag)


class AsyncActivityTypes(AsyncReadResource[ActivityType, NameFilter]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/activity-types", "activity-types", ActivityType)


class AsyncCustomFieldDefinitions(AsyncReadResource[CustomFieldDefinition, UpdatedSinceFilter]):
    def __init__(self, transport: AsyncTransport) -> None:
        super().__init__(transport, f"{API}/custom-field-definitions", "custom-field-definitions",
                         CustomFieldDefinition)


class AsyncChanges:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    async def read(self, cursor: str | None = None) -> ChangePage:
        params = {CHANGES_CURSOR_PARAM: cursor} if cursor else None
        return _parse_changes(await self._t.request("GET", f"{API}/changes", params=params))

    async def iter_pages(self, cursor: str | None = None) -> AsyncIterator[ChangePage]:
        while True:
            page = await self.read(cursor)
            yield page
            if not page.has_more:
                return
            cursor = page.cursor


__all__ = [
    "Activities", "ActivityTypes", "Changes", "Companies", "Contacts", "CustomFieldDefinitions",
    "Deals", "Owners", "Stages", "Tags", "Tasks",
    "AsyncActivities", "AsyncActivityTypes", "AsyncChanges", "AsyncCompanies", "AsyncContacts",
    "AsyncCustomFieldDefinitions", "AsyncDeals", "AsyncOwners", "AsyncStages", "AsyncTags",
    "AsyncTasks", "CHANGES_CURSOR_PARAM",
]

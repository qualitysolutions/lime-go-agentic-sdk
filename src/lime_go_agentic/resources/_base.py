"""Generic resource namespaces shared by every endpoint family.

The API is uniform JSON:API, so one generic implementation covers all resources:

* :class:`SyncReadResource` - ``list`` / ``iter`` / ``get`` (reference data),
* :class:`SyncCrudResource` - adds ``create`` / ``upsert`` / ``update`` / ``delete``,
* :class:`SyncRelationship` - ``/{id}/relationships/{name}`` list/add/remove/replace,

plus their ``Async*`` twins. Request building and response parsing are shared free
functions so the sync and async classes only differ in ``await``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from datetime import date, datetime
from typing import Any, Generic, TypeVar
from urllib.parse import quote

from .._transport import AsyncTransport, Response, SyncTransport
from ..errors import LimeGoError, MissingETagError
from ..models import RESOURCE_MODELS
from ..models.common import Page, R, RelationshipPage, Resource, ResourceIdentifier, UpsertResult, WriteModel

F = TypeVar("F", bound=Mapping[str, Any])
C = TypeVar("C", bound=WriteModel)
U = TypeVar("U", bound=WriteModel)

#: Max items per page and per relationship write, as declared by the API.
MAX_PAGE_SIZE = 100


# -- shared helpers -------------------------------------------------------------------
def _param_value(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _list_params(
    resource_type: str,
    *,
    filter: Mapping[str, Any] | None,
    page_size: int | None,
    sort: str | None,
    fields: Sequence[str] | None,
    include: Sequence[str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {}
    for key, value in (filter or {}).items():
        if value is not None:
            params[f"filter[{key}]"] = _param_value(value)
    if page_size is not None:
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        params["page[size]"] = str(page_size)
    if sort is not None:
        params["sort"] = sort
    if fields:
        params[f"fields[{resource_type}]"] = ",".join(fields)
    if include:
        params["include"] = ",".join(include)
    return params


def _item_path(base: str, resource_id: str) -> str:
    return f"{base}/{quote(resource_id, safe='')}"


def _data(response: Response) -> Any:
    if not isinstance(response.body, dict) or "data" not in response.body:
        raise LimeGoError(f"Unexpected response body (no 'data'): request_id={response.request_id}")
    return response.body["data"]


def _parse_single(model: type[R], response: Response) -> R:
    obj = model.model_validate(_data(response))
    obj._etag = response.etag
    return obj


def _parse_included(raw: Any) -> list[Resource]:
    out: list[Resource] = []
    for item in raw or []:
        model = RESOURCE_MODELS.get(item.get("type", "")) if isinstance(item, dict) else None
        out.append((model or Resource).model_validate(item))
    return out


def _parse_page(model: type[R], response: Response) -> Page[R]:
    body = response.body if isinstance(response.body, dict) else {}
    links = body.get("links") or {}
    return Page(
        data=[model.model_validate(item) for item in _data(response)],
        next_url=links.get("next") or None,
        included=_parse_included(body.get("included")),
        links=links,
        etag=response.etag,
    )


def _parse_relationship_page(response: Response) -> RelationshipPage:
    body = response.body if isinstance(response.body, dict) else {}
    links = body.get("links") or {}
    meta = body.get("meta") or {}
    return RelationshipPage(
        data=[ResourceIdentifier.model_validate(item) for item in _data(response)],
        next_url=links.get("next") or None,
        truncated=bool(meta.get("truncated", False)),
        etag=response.etag,
    )


def _if_match(value: str | Resource) -> str:
    if isinstance(value, Resource):
        if value.etag is None:
            raise MissingETagError(
                f"{value.type}/{value.id} has no ETag (no response ETag and no meta.revision). "
                "Fetch it with get() first, or pass if_match= the ETag string."
            )
        return value.etag
    if not value:
        raise MissingETagError("if_match must be a non-empty ETag")
    return value


def _write_headers(*, if_match: str | Resource | None, idempotency_key: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if if_match is not None:
        headers["If-Match"] = _if_match(if_match)
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _linkage(target_type: str, ids: Sequence[str]) -> dict[str, Any]:
    if len(ids) > MAX_PAGE_SIZE:
        raise ValueError(f"At most {MAX_PAGE_SIZE} relationship ids per call")
    return {"data": [{"type": target_type, "id": i} for i in ids]}


# -- sync ------------------------------------------------------------------------------
class SyncReadResource(Generic[R, F]):
    """``list`` / ``iter`` / ``get`` for one resource type."""

    def __init__(self, transport: SyncTransport, path: str, resource_type: str, model: type[R]) -> None:
        self._t = transport
        self._path = path
        self._type = resource_type
        self._model = model

    def list(
        self,
        filter: F | None = None,
        *,
        page_size: int | None = None,
        sort: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> Page[R]:
        """Fetch one page. ``sort`` is ``"id"`` or ``"-id"``; ``fields`` limits attributes."""
        params = _list_params(self._type, filter=filter, page_size=page_size, sort=sort,
                              fields=fields, include=None)
        return _parse_page(self._model, self._t.request("GET", self._path, params=params))

    def next_page(self, page: Page[R]) -> Page[R] | None:
        """Fetch the page after ``page``, or ``None`` if it was the last."""
        if page.next_url is None:
            return None
        return _parse_page(self._model, self._t.request("GET", page.next_url))

    def iter(
        self,
        filter: F | None = None,
        *,
        page_size: int = MAX_PAGE_SIZE,
        sort: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> Iterator[R]:
        """Iterate over every record, following ``links.next`` page by page."""
        page: Page[R] | None = self.list(filter, page_size=page_size, sort=sort, fields=fields)
        while page is not None:
            yield from page.data
            page = self.next_page(page)

    def get(self, resource_id: str) -> R:
        """Fetch one record. The result carries its ``etag`` for later writes."""
        return _parse_single(self._model, self._t.request("GET", _item_path(self._path, resource_id)))


class SyncCrudResource(SyncReadResource[R, F], Generic[R, F, C, U]):
    """Full CRUD + external-id upsert for one resource type."""

    def list(
        self,
        filter: F | None = None,
        *,
        page_size: int | None = None,
        sort: str | None = None,
        fields: Sequence[str] | None = None,
        include: Sequence[str] | None = None,
    ) -> Page[R]:
        """Fetch one page. ``include`` names up to two to-one relationships (e.g.
        ``["company"]``); the related records are returned in ``page.included``."""
        params = _list_params(self._type, filter=filter, page_size=page_size, sort=sort,
                              fields=fields, include=include)
        return _parse_page(self._model, self._t.request("GET", self._path, params=params))

    def iter(
        self,
        filter: F | None = None,
        *,
        page_size: int = MAX_PAGE_SIZE,
        sort: str | None = None,
        fields: Sequence[str] | None = None,
        include: Sequence[str] | None = None,
    ) -> Iterator[R]:
        page: Page[R] | None = self.list(filter, page_size=page_size, sort=sort, fields=fields,
                                         include=include)
        while page is not None:
            yield from page.data
            page = self.next_page(page)

    def create(self, data: C, *, idempotency_key: str | None = None) -> R:
        """Create a record. Pass a stable ``idempotency_key`` to make re-runs safe."""
        response = self._t.request(
            "POST", self._path, json=data.to_document(self._type),
            headers=_write_headers(if_match=None, idempotency_key=idempotency_key),
        )
        return _parse_single(self._model, response)

    def upsert(
        self,
        external_id: str,
        data: C,
        *,
        if_match: str | Resource | None = None,
        idempotency_key: str | None = None,
    ) -> UpsertResult[R]:
        """Create or update the record owned by this integration under ``external_id``
        (max 128 chars), e.g. a contract number. ``result.created`` tells which.

        Observed live (2026-10-14): when the record already exists the API requires
        ``if_match`` (428 without it) and answered 409 even with the current ETag, so
        change existing records with :meth:`update` (PATCH) until Lime clarifies."""
        if not 1 <= len(external_id) <= 128:
            raise ValueError("external_id must be 1-128 characters")
        response = self._t.request(
            "PUT", f"{self._path}/external/{quote(external_id, safe='')}",
            json=data.to_document(self._type),
            headers=_write_headers(if_match=if_match, idempotency_key=idempotency_key),
        )
        return UpsertResult(resource=_parse_single(self._model, response),
                            created=response.status_code == 201)

    def update(
        self,
        resource_id: str,
        data: U,
        *,
        if_match: str | Resource,
        idempotency_key: str | None = None,
    ) -> R:
        """Patch a record. ``if_match`` is the current ETag (or a resource from
        ``get``/``create``/``update``); a stale one raises ``PreconditionFailedError``."""
        response = self._t.request(
            "PATCH", _item_path(self._path, resource_id),
            json=data.to_document(self._type, resource_id=resource_id),
            headers=_write_headers(if_match=if_match, idempotency_key=idempotency_key),
        )
        return _parse_single(self._model, response)

    def delete(
        self,
        resource_id: str,
        *,
        if_match: str | Resource,
        idempotency_key: str | None = None,
    ) -> None:
        self._t.request(
            "DELETE", _item_path(self._path, resource_id),
            headers=_write_headers(if_match=if_match, idempotency_key=idempotency_key),
        )


class SyncRelationship:
    """A to-many relationship endpoint, e.g. ``client.deals.contacts``.

    Every write needs the PARENT record's ETag; each call returns a page whose ``etag``
    is the parent's new ETag, ready for the next write.
    """

    def __init__(self, transport: SyncTransport, parent_path: str, name: str, target_type: str) -> None:
        self._t = transport
        self._parent_path = parent_path
        self._name = name
        self._target = target_type

    def _path(self, parent_id: str) -> str:
        return f"{_item_path(self._parent_path, parent_id)}/relationships/{self._name}"

    def list(self, parent_id: str, *, page_size: int | None = None) -> RelationshipPage:
        params = {"page[size]": str(page_size)} if page_size is not None else None
        return _parse_relationship_page(self._t.request("GET", self._path(parent_id), params=params))

    def iter(self, parent_id: str) -> Iterator[str]:
        """Iterate over every linked id."""
        page: RelationshipPage | None = self.list(parent_id, page_size=MAX_PAGE_SIZE)
        while page is not None:
            yield from page.ids
            page = (_parse_relationship_page(self._t.request("GET", page.next_url))
                    if page.next_url else None)

    def _write(self, method: str, parent_id: str, ids: Sequence[str], if_match: str | Resource,
               idempotency_key: str | None) -> RelationshipPage:
        response = self._t.request(
            method, self._path(parent_id), json=_linkage(self._target, ids),
            headers=_write_headers(if_match=if_match, idempotency_key=idempotency_key),
        )
        return _parse_relationship_page(response)

    def add(self, parent_id: str, ids: Sequence[str], *, if_match: str | Resource,
            idempotency_key: str | None = None) -> RelationshipPage:
        """Link up to 100 records (existing links are kept)."""
        return self._write("POST", parent_id, ids, if_match, idempotency_key)

    def remove(self, parent_id: str, ids: Sequence[str], *, if_match: str | Resource,
               idempotency_key: str | None = None) -> RelationshipPage:
        """Unlink up to 100 records (the records themselves are kept)."""
        return self._write("DELETE", parent_id, ids, if_match, idempotency_key)

    def replace(self, parent_id: str, ids: Sequence[str], *, if_match: str | Resource,
                idempotency_key: str | None = None) -> RelationshipPage:
        """Replace the whole linkage. Raises ``ConflictError`` (``relationship_too_large``)
        if the existing collection exceeds 100."""
        return self._write("PATCH", parent_id, ids, if_match, idempotency_key)


# -- async -----------------------------------------------------------------------------
class AsyncReadResource(Generic[R, F]):
    """Async twin of :class:`SyncReadResource`."""

    def __init__(self, transport: AsyncTransport, path: str, resource_type: str, model: type[R]) -> None:
        self._t = transport
        self._path = path
        self._type = resource_type
        self._model = model

    async def list(
        self,
        filter: F | None = None,
        *,
        page_size: int | None = None,
        sort: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> Page[R]:
        params = _list_params(self._type, filter=filter, page_size=page_size, sort=sort,
                              fields=fields, include=None)
        return _parse_page(self._model, await self._t.request("GET", self._path, params=params))

    async def next_page(self, page: Page[R]) -> Page[R] | None:
        if page.next_url is None:
            return None
        return _parse_page(self._model, await self._t.request("GET", page.next_url))

    async def iter(
        self,
        filter: F | None = None,
        *,
        page_size: int = MAX_PAGE_SIZE,
        sort: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> AsyncIterator[R]:
        page: Page[R] | None = await self.list(filter, page_size=page_size, sort=sort, fields=fields)
        while page is not None:
            for item in page.data:
                yield item
            page = await self.next_page(page)

    async def get(self, resource_id: str) -> R:
        response = await self._t.request("GET", _item_path(self._path, resource_id))
        return _parse_single(self._model, response)


class AsyncCrudResource(AsyncReadResource[R, F], Generic[R, F, C, U]):
    """Async twin of :class:`SyncCrudResource`."""

    async def list(
        self,
        filter: F | None = None,
        *,
        page_size: int | None = None,
        sort: str | None = None,
        fields: Sequence[str] | None = None,
        include: Sequence[str] | None = None,
    ) -> Page[R]:
        params = _list_params(self._type, filter=filter, page_size=page_size, sort=sort,
                              fields=fields, include=include)
        return _parse_page(self._model, await self._t.request("GET", self._path, params=params))

    async def iter(
        self,
        filter: F | None = None,
        *,
        page_size: int = MAX_PAGE_SIZE,
        sort: str | None = None,
        fields: Sequence[str] | None = None,
        include: Sequence[str] | None = None,
    ) -> AsyncIterator[R]:
        page: Page[R] | None = await self.list(filter, page_size=page_size, sort=sort,
                                               fields=fields, include=include)
        while page is not None:
            for item in page.data:
                yield item
            page = await self.next_page(page)

    async def create(self, data: C, *, idempotency_key: str | None = None) -> R:
        response = await self._t.request(
            "POST", self._path, json=data.to_document(self._type),
            headers=_write_headers(if_match=None, idempotency_key=idempotency_key),
        )
        return _parse_single(self._model, response)

    async def upsert(
        self,
        external_id: str,
        data: C,
        *,
        if_match: str | Resource | None = None,
        idempotency_key: str | None = None,
    ) -> UpsertResult[R]:
        if not 1 <= len(external_id) <= 128:
            raise ValueError("external_id must be 1-128 characters")
        response = await self._t.request(
            "PUT", f"{self._path}/external/{quote(external_id, safe='')}",
            json=data.to_document(self._type),
            headers=_write_headers(if_match=if_match, idempotency_key=idempotency_key),
        )
        return UpsertResult(resource=_parse_single(self._model, response),
                            created=response.status_code == 201)

    async def update(
        self,
        resource_id: str,
        data: U,
        *,
        if_match: str | Resource,
        idempotency_key: str | None = None,
    ) -> R:
        response = await self._t.request(
            "PATCH", _item_path(self._path, resource_id),
            json=data.to_document(self._type, resource_id=resource_id),
            headers=_write_headers(if_match=if_match, idempotency_key=idempotency_key),
        )
        return _parse_single(self._model, response)

    async def delete(
        self,
        resource_id: str,
        *,
        if_match: str | Resource,
        idempotency_key: str | None = None,
    ) -> None:
        await self._t.request(
            "DELETE", _item_path(self._path, resource_id),
            headers=_write_headers(if_match=if_match, idempotency_key=idempotency_key),
        )


class AsyncRelationship:
    """Async twin of :class:`SyncRelationship`."""

    def __init__(self, transport: AsyncTransport, parent_path: str, name: str, target_type: str) -> None:
        self._t = transport
        self._parent_path = parent_path
        self._name = name
        self._target = target_type

    def _path(self, parent_id: str) -> str:
        return f"{_item_path(self._parent_path, parent_id)}/relationships/{self._name}"

    async def list(self, parent_id: str, *, page_size: int | None = None) -> RelationshipPage:
        params = {"page[size]": str(page_size)} if page_size is not None else None
        response = await self._t.request("GET", self._path(parent_id), params=params)
        return _parse_relationship_page(response)

    async def iter(self, parent_id: str) -> AsyncIterator[str]:
        page: RelationshipPage | None = await self.list(parent_id, page_size=MAX_PAGE_SIZE)
        while page is not None:
            for rid in page.ids:
                yield rid
            page = (_parse_relationship_page(await self._t.request("GET", page.next_url))
                    if page.next_url else None)

    async def _write(self, method: str, parent_id: str, ids: Sequence[str], if_match: str | Resource,
                     idempotency_key: str | None) -> RelationshipPage:
        response = await self._t.request(
            method, self._path(parent_id), json=_linkage(self._target, ids),
            headers=_write_headers(if_match=if_match, idempotency_key=idempotency_key),
        )
        return _parse_relationship_page(response)

    async def add(self, parent_id: str, ids: Sequence[str], *, if_match: str | Resource,
                  idempotency_key: str | None = None) -> RelationshipPage:
        return await self._write("POST", parent_id, ids, if_match, idempotency_key)

    async def remove(self, parent_id: str, ids: Sequence[str], *, if_match: str | Resource,
                     idempotency_key: str | None = None) -> RelationshipPage:
        return await self._write("DELETE", parent_id, ids, if_match, idempotency_key)

    async def replace(self, parent_id: str, ids: Sequence[str], *, if_match: str | Resource,
                      idempotency_key: str | None = None) -> RelationshipPage:
        return await self._write("PATCH", parent_id, ids, if_match, idempotency_key)

"""Shared JSON:API building blocks: resource objects, relationships, write models, pages.

Read models (what the API returns) use ``extra="allow"`` and default every attribute to
``None``: sparse fieldsets (``fields[...]``) legitimately omit attributes, and a field Lime
adds later is kept instead of breaking parsing. Write models (what you send) use
``extra="forbid"`` and the spec's constraints, mirroring the API's
``additionalProperties: false`` so mistakes fail locally before a request is made.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Generic, Iterator, Literal, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, PrivateAttr, model_validator

#: Strings in write bodies are capped at 10 000 characters by the API.
Text = Annotated[str, Field(max_length=10000)]


def _check_custom_fields(value: dict[str, Any]) -> dict[str, Any]:
    if len(value) > 100:
        raise ValueError("custom_fields accepts at most 100 keys")
    return value


#: ``custom_fields`` object (max 100 keys). Keys are custom-field-definition ``key`` values.
CustomFields = Annotated[dict[str, Any], AfterValidator(_check_custom_fields)]

_DECIMAL_PATTERN = re.compile(r"^-?[0-9]{1,15}(\.[0-9]{1,4})?$")


def _check_decimal(value: Decimal) -> Decimal:
    if not _DECIMAL_PATTERN.fullmatch(format(value, "f")):
        raise ValueError("must have at most 15 integer digits and 4 decimals")
    return value


#: A money amount sent as the API's decimal string (``^-?[0-9]{1,15}(\.[0-9]{1,4})?$``).
DecimalString = Annotated[
    Decimal,
    AfterValidator(_check_decimal),
    PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json"),
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ResourceIdentifier(_Model):
    """A JSON:API resource identifier: ``{"type": ..., "id": ...}``."""

    type: str
    id: str


class ToOne(_Model):
    """A to-one relationship. ``data`` is ``None`` when unset."""

    data: ResourceIdentifier | None = None

    @property
    def id(self) -> str | None:
        return self.data.id if self.data else None


class ToMany(_Model):
    """A to-many relationship."""

    data: list[ResourceIdentifier] = Field(default_factory=list)

    @property
    def ids(self) -> list[str]:
        return [ref.id for ref in self.data]


class ResourceMeta(_Model):
    #: Monotonic revision of the record (a numeric string).
    revision: str | None = None


class Resource(_Model):
    """Base for every resource object returned by the API.

    ``etag`` is the response ``ETag`` when the resource came from a single-resource
    response (get/create/update/upsert). Pass the resource itself as ``if_match=`` to
    update/delete it. Resources from a list page have ``etag = None``.
    """

    id: str
    type: str
    meta: ResourceMeta = Field(default_factory=ResourceMeta)

    _etag: str | None = PrivateAttr(default=None)

    @property
    def etag(self) -> str | None:
        return self._etag

    @property
    def revision(self) -> str | None:
        return self.meta.revision


R = TypeVar("R", bound=Resource)

RelationshipKind = Literal["one", "many"]


class WriteModel(BaseModel):
    """Base for create/update payloads.

    Only fields you actually set are sent (``exclude_unset``), so on an update an omitted
    field is left unchanged while an explicit ``None`` clears a nullable field. Setting a
    non-nullable field to ``None`` is rejected locally.
    """

    model_config = ConfigDict(extra="forbid")

    #: Relationship fields: name -> (kind, target resource type).
    relationship_fields: ClassVar[dict[str, tuple[RelationshipKind, str]]] = {}
    #: Fields the API declares ``nullable: false``.
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_explicit_null(self) -> "WriteModel":
        for name in self.non_nullable_fields & self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

    def to_document(self, resource_type: str, *, resource_id: str | None = None) -> dict[str, Any]:
        """Render the JSON:API request document."""
        dumped = self.model_dump(mode="json", exclude_unset=True, by_alias=True)
        client_id = dumped.pop("id", None)
        attributes: dict[str, Any] = {}
        relationships: dict[str, Any] = {}
        for name, value in dumped.items():
            rel = self.relationship_fields.get(name)
            if rel is None:
                attributes[name] = value
                continue
            kind, target = rel
            if kind == "one":
                relationships[name] = {"data": None if value is None else {"type": target, "id": value}}
            else:
                relationships[name] = {"data": [{"type": target, "id": v} for v in value]}
        data: dict[str, Any] = {"type": resource_type}
        if resource_id is not None:
            data["id"] = resource_id
        elif client_id is not None:
            data["id"] = client_id
        data["attributes"] = attributes
        if relationships:
            data["relationships"] = relationships
        return {"data": data}


@dataclass
class Page(Generic[R]):
    """One page of a list response."""

    data: list[R]
    #: URL of the next page, or ``None`` on the last page.
    next_url: str | None = None
    #: Compound-document resources requested with ``include=`` (typed where known).
    included: list[Resource] = field(default_factory=list)
    links: dict[str, Any] = field(default_factory=dict)
    etag: str | None = None

    def __iter__(self) -> Iterator[R]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    @property
    def has_more(self) -> bool:
        return self.next_url is not None


@dataclass
class RelationshipPage:
    """A page of relationship linkage (``/{id}/relationships/{name}``)."""

    data: list[ResourceIdentifier]
    next_url: str | None = None
    #: True when the server cut the linkage short (see the API's 100-item limit).
    truncated: bool = False
    #: ETag of the PARENT resource after the call; use it for the next write.
    etag: str | None = None

    @property
    def ids(self) -> list[str]:
        return [ref.id for ref in self.data]


@dataclass
class UpsertResult(Generic[R]):
    """Result of ``PUT .../external/{external_id}``."""

    resource: R
    #: True when the record was created (HTTP 201), False when updated (HTTP 200).
    created: bool

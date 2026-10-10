"""Activities (notes, calls, meetings)."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal, TypedDict

from pydantic import ConfigDict, Field

from .common import RelationshipKind, Resource, Text, ToOne, WriteModel, _Model

#: Activity type accepted on write. On read ``type`` is a free string.
ActivityWriteType = Literal["note", "call", "meeting"]


class ActivityAttributes(_Model):
    #: Activity type (``note``, ``call``, ``meeting``, ...). Named ``activity_type`` in
    #: Python to avoid clashing with the JSON:API resource ``type``; the wire name is
    #: ``type``.
    activity_type: str | None = Field(default=None, alias="type")
    content: str | None = None
    occurred_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ActivityRelationships(_Model):
    company: ToOne = Field(default_factory=ToOne)
    contact: ToOne = Field(default_factory=ToOne)
    deal: ToOne = Field(default_factory=ToOne)


class Activity(Resource):
    type: Literal["activities"] = "activities"
    attributes: ActivityAttributes = Field(default_factory=ActivityAttributes)
    relationships: ActivityRelationships = Field(default_factory=ActivityRelationships)


class ActivityCreate(WriteModel):
    """Body for ``create`` and ``upsert``. Relationships can only be set here."""

    relationship_fields: ClassVar[dict[str, tuple[RelationshipKind, str]]] = {
        "company": ("one", "companies"),
        "contact": ("one", "contacts"),
        "deal": ("one", "deals"),
    }
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"activity_type"})
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    activity_type: ActivityWriteType = Field(alias="type")
    content: Text | None = None
    occurred_at: datetime | None = None
    company: str | None = None
    contact: str | None = None
    deal: str | None = None
    id: str | None = None


class ActivityUpdate(WriteModel):
    """Body for ``update`` (PATCH). The API only allows ``content`` and ``type`` here."""

    non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"activity_type"})
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    activity_type: ActivityWriteType | None = Field(default=None, alias="type")
    content: Text | None = None


class ActivityFilter(TypedDict, total=False):
    updated_since: datetime

"""Tasks (to-dos)."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal, TypedDict

from pydantic import Field

from .common import RelationshipKind, Resource, Text, ToMany, ToOne, WriteModel, _Model

TaskStatus = Literal["pending", "in_progress", "completed", "cancelled", "proposed", "unknown"]
TaskWriteStatus = Literal["pending", "in_progress", "completed", "cancelled", "proposed"]
TaskPriority = Literal["low", "medium", "high", "urgent", "unknown"]
TaskWritePriority = Literal["low", "medium", "high", "urgent"]
#: How ``description`` is interpreted. Responses may also say ``unknown`` (reserved).
DescriptionFormat = Literal["plain_text", "markdown", "unknown"]
DescriptionWriteFormat = Literal["plain_text", "markdown"]


class TaskAttributes(_Model):
    title: str | None = None
    description: str | None = None
    #: Omitted in default responses for plain-text tasks (means ``plain_text``); request
    #: ``fields[tasks]=description,description_format`` for an explicit value.
    description_format: DescriptionFormat | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskRelationships(_Model):
    owner: ToOne = Field(default_factory=ToOne)
    companies: ToMany = Field(default_factory=ToMany)
    contacts: ToMany = Field(default_factory=ToMany)
    deals: ToMany = Field(default_factory=ToMany)


class Task(Resource):
    type: Literal["tasks"] = "tasks"
    attributes: TaskAttributes = Field(default_factory=TaskAttributes)
    relationships: TaskRelationships = Field(default_factory=TaskRelationships)


class _TaskWrite(WriteModel):
    relationship_fields: ClassVar[dict[str, tuple[RelationshipKind, str]]] = {
        "owner": ("one", "owners"),
        "companies": ("many", "companies"),
        "contacts": ("many", "contacts"),
        "deals": ("many", "deals"),
    }
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"title", "status", "priority", "description_format"})

    description: Text | None = None
    #: ``markdown`` renders headings, bold, lists and clickable links in Lime. Create
    #: omission = plain_text; update omission keeps the stored format; changing the
    #: format requires ``description`` in the same request (else 422).
    description_format: DescriptionWriteFormat | None = None
    status: TaskWriteStatus | None = None
    priority: TaskWritePriority | None = None
    due_date: datetime | None = None
    companies: list[str] | None = Field(default=None, max_length=100)
    contacts: list[str] | None = Field(default=None, max_length=100)
    deals: list[str] | None = Field(default=None, max_length=100)


class TaskCreate(_TaskWrite):
    """Body for ``create`` and ``upsert``. ``owner`` is required (may be ``None``)."""

    title: Text
    owner: str | None
    id: str | None = None


class TaskUpdate(_TaskWrite):
    title: Text | None = None
    owner: str | None = None


class TaskFilter(TypedDict, total=False):
    status: str
    updated_since: datetime

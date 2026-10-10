"""Contacts (people)."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal, TypedDict

from pydantic import Field

from .common import CustomFields, RelationshipKind, Resource, Text, ToMany, ToOne, WriteModel, _Model

ContactStatus = Literal["active", "inactive", "lead", "unknown"]
ContactWriteStatus = Literal["active", "inactive", "lead"]


class ContactAttributes(_Model):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile_phone: str | None = None
    job_title: str | None = None
    department: str | None = None
    notes: str | None = None
    status: ContactStatus | None = None
    custom_fields: dict[str, object] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContactRelationships(_Model):
    company: ToOne = Field(default_factory=ToOne)
    tags: ToMany = Field(default_factory=ToMany)


class Contact(Resource):
    type: Literal["contacts"] = "contacts"
    attributes: ContactAttributes = Field(default_factory=ContactAttributes)
    relationships: ContactRelationships = Field(default_factory=ContactRelationships)


class _ContactWrite(WriteModel):
    relationship_fields: ClassVar[dict[str, tuple[RelationshipKind, str]]] = {
        "company": ("one", "companies"),
        "tags": ("many", "tags"),
    }
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"first_name", "last_name", "status", "custom_fields"}
    )

    email: Text | None = None
    phone: Text | None = None
    mobile_phone: Text | None = None
    job_title: Text | None = None
    department: Text | None = None
    notes: Text | None = None
    status: ContactWriteStatus | None = None
    custom_fields: CustomFields | None = None
    #: Company id; ``None`` detaches the contact.
    company: str | None = None
    tags: list[str] | None = Field(default=None, max_length=100)


class ContactCreate(_ContactWrite):
    first_name: Text
    last_name: Text
    id: str | None = None


class ContactUpdate(_ContactWrite):
    first_name: Text | None = None
    last_name: Text | None = None


class ContactFilter(TypedDict, total=False):
    status: str
    updated_since: datetime

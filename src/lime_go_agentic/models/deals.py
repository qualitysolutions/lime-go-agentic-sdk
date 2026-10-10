"""Deals (opportunities)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import ClassVar, Literal, TypedDict

from pydantic import Field

from .common import (
    CustomFields,
    DecimalString,
    RelationshipKind,
    Resource,
    Text,
    ToMany,
    ToOne,
    WriteModel,
    _Model,
)


class DealAttributes(_Model):
    name: str | None = None
    description: str | None = None
    #: Sent by the API as a decimal string; parsed to Decimal (no float rounding).
    value: Decimal | None = None
    currency: str | None = None
    probability: int | None = None
    expected_close_date: date | None = None
    custom_fields: dict[str, object] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DealRelationships(_Model):
    company: ToOne = Field(default_factory=ToOne)
    stage: ToOne = Field(default_factory=ToOne)
    contacts: ToMany = Field(default_factory=ToMany)
    owners: ToMany = Field(default_factory=ToMany)
    tags: ToMany = Field(default_factory=ToMany)


class Deal(Resource):
    type: Literal["deals"] = "deals"
    attributes: DealAttributes = Field(default_factory=DealAttributes)
    relationships: DealRelationships = Field(default_factory=DealRelationships)


class _DealWrite(WriteModel):
    relationship_fields: ClassVar[dict[str, tuple[RelationshipKind, str]]] = {
        "company": ("one", "companies"),
        "stage": ("one", "stages"),
        "contacts": ("many", "contacts"),
        "owners": ("many", "owners"),
        "tags": ("many", "tags"),
    }
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"name", "custom_fields"})

    description: Text | None = None
    #: Max 15 integer digits and 4 decimals.
    value: DecimalString | None = None
    currency: Text | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    custom_fields: CustomFields | None = None
    company: str | None = None
    stage: str | None = None
    contacts: list[str] | None = Field(default=None, max_length=100)
    owners: list[str] | None = Field(default=None, max_length=100)
    tags: list[str] | None = Field(default=None, max_length=100)


class DealCreate(_DealWrite):
    name: Text
    id: str | None = None


class DealUpdate(_DealWrite):
    name: Text | None = None


class DealFilter(TypedDict, total=False):
    name: str
    updated_since: datetime

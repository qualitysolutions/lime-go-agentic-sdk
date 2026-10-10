"""Companies (organisations / accounts)."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal, TypedDict

from pydantic import Field

from .common import CustomFields, RelationshipKind, Resource, Text, ToMany, ToOne, WriteModel, _Model

#: Status as returned by the API (``unknown`` = a value the API cannot map).
CompanyStatus = Literal["lead", "prospect", "customer", "churned", "inactive", "unknown"]
#: Status values accepted on write.
CompanyWriteStatus = Literal["lead", "prospect", "customer", "churned", "inactive"]


class CompanyAttributes(_Model):
    name: str | None = None
    business_id: str | None = None
    status: CompanyStatus | None = None
    description: str | None = None
    domain: str | None = None
    email: str | None = None
    phone: str | None = None
    industry: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    custom_fields: dict[str, object] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CompanyRelationships(_Model):
    owner: ToOne = Field(default_factory=ToOne)
    tags: ToMany = Field(default_factory=ToMany)


class Company(Resource):
    type: Literal["companies"] = "companies"
    attributes: CompanyAttributes = Field(default_factory=CompanyAttributes)
    relationships: CompanyRelationships = Field(default_factory=CompanyRelationships)


class _CompanyWrite(WriteModel):
    relationship_fields: ClassVar[dict[str, tuple[RelationshipKind, str]]] = {
        "owner": ("one", "owners"),
        "tags": ("many", "tags"),
    }
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"name", "status", "custom_fields"})

    business_id: Text | None = None
    status: CompanyWriteStatus | None = None
    description: Text | None = None
    domain: Text | None = None
    email: Text | None = None
    phone: Text | None = None
    industry: Text | None = None
    street: Text | None = None
    postal_code: Text | None = None
    city: Text | None = None
    state: Text | None = None
    country: Text | None = None
    custom_fields: CustomFields | None = None
    #: Owner id (``owners``); ``None`` clears it.
    owner: str | None = None
    #: Tag ids (``tags``), max 100.
    tags: list[str] | None = Field(default=None, max_length=100)


class CompanyCreate(_CompanyWrite):
    """Body for ``create`` and ``upsert``."""

    name: Text
    #: Optional client-generated UUID for the new record.
    id: str | None = None


class CompanyUpdate(_CompanyWrite):
    """Body for ``update`` (PATCH). Only the fields you set are sent."""

    name: Text | None = None


class CompanyFilter(TypedDict, total=False):
    status: str
    name: str
    updated_since: datetime

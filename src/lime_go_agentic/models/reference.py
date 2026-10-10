"""Read-only reference data: owners, stages, tags, activity types, custom-field definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, TypedDict

from pydantic import Field

from .common import Resource, _Model


class OwnerAttributes(_Model):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


class Owner(Resource):
    """An active direct organisation member (assignable as owner)."""

    type: Literal["owners"] = "owners"
    attributes: OwnerAttributes = Field(default_factory=OwnerAttributes)


class StageAttributes(_Model):
    name: str | None = None
    category: str | None = None
    position: int | None = None
    probability: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Stage(Resource):
    """A deal pipeline stage."""

    type: Literal["stages"] = "stages"
    attributes: StageAttributes = Field(default_factory=StageAttributes)


class TagAttributes(_Model):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    #: Which resource type the tag applies to.
    taggable_type: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Tag(Resource):
    type: Literal["tags"] = "tags"
    attributes: TagAttributes = Field(default_factory=TagAttributes)


class ActivityTypeAttributes(_Model):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    position: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ActivityType(Resource):
    type: Literal["activity-types"] = "activity-types"
    attributes: ActivityTypeAttributes = Field(default_factory=ActivityTypeAttributes)


class CustomFieldDefinitionAttributes(_Model):
    #: The key used in a record's ``custom_fields`` object.
    key: str | None = None
    label: str | None = None
    #: Resource type the field belongs to (e.g. companies, deals).
    entity_type: str | None = None
    field_type: str | None = None
    options: list[str] | None = None
    required: bool | None = None
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CustomFieldDefinition(Resource):
    type: Literal["custom-field-definitions"] = "custom-field-definitions"
    attributes: CustomFieldDefinitionAttributes = Field(default_factory=CustomFieldDefinitionAttributes)


class NameFilter(TypedDict, total=False):
    name: str
    updated_since: datetime


class UpdatedSinceFilter(TypedDict, total=False):
    updated_since: datetime


class NoFilter(TypedDict, total=False):
    """Owners accept no filters."""

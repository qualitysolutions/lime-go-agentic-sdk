"""Typed models for the Lime Go Agentic API."""

from __future__ import annotations

from .activities import (
    Activity,
    ActivityAttributes,
    ActivityCreate,
    ActivityFilter,
    ActivityRelationships,
    ActivityUpdate,
    ActivityWriteType,
)
from .changes import Change, ChangeAttributes, ChangePage
from .common import (
    Page,
    RelationshipPage,
    Resource,
    ResourceIdentifier,
    ResourceMeta,
    ToMany,
    ToOne,
    UpsertResult,
    WriteModel,
)
from .companies import (
    Company,
    CompanyAttributes,
    CompanyCreate,
    CompanyFilter,
    CompanyRelationships,
    CompanyStatus,
    CompanyUpdate,
    CompanyWriteStatus,
)
from .contacts import (
    Contact,
    ContactAttributes,
    ContactCreate,
    ContactFilter,
    ContactRelationships,
    ContactStatus,
    ContactUpdate,
    ContactWriteStatus,
)
from .deals import Deal, DealAttributes, DealCreate, DealFilter, DealRelationships, DealUpdate
from .reference import (
    ActivityType,
    ActivityTypeAttributes,
    CustomFieldDefinition,
    CustomFieldDefinitionAttributes,
    NameFilter,
    NoFilter,
    Owner,
    OwnerAttributes,
    Stage,
    StageAttributes,
    Tag,
    TagAttributes,
    UpdatedSinceFilter,
)
from .tasks import (
    Task,
    TaskAttributes,
    TaskCreate,
    TaskFilter,
    TaskPriority,
    TaskRelationships,
    TaskStatus,
    TaskUpdate,
    TaskWritePriority,
    TaskWriteStatus,
)

#: JSON:API ``type`` -> model, used to type ``included`` resources.
RESOURCE_MODELS: dict[str, type[Resource]] = {
    "activities": Activity,
    "activity-types": ActivityType,
    "companies": Company,
    "contacts": Contact,
    "custom-field-definitions": CustomFieldDefinition,
    "deals": Deal,
    "owners": Owner,
    "stages": Stage,
    "tags": Tag,
    "tasks": Task,
}

__all__ = [
    "RESOURCE_MODELS",
    "Activity", "ActivityAttributes", "ActivityCreate", "ActivityFilter",
    "ActivityRelationships", "ActivityUpdate", "ActivityWriteType",
    "ActivityType", "ActivityTypeAttributes",
    "Change", "ChangeAttributes", "ChangePage",
    "Company", "CompanyAttributes", "CompanyCreate", "CompanyFilter",
    "CompanyRelationships", "CompanyStatus", "CompanyUpdate", "CompanyWriteStatus",
    "Contact", "ContactAttributes", "ContactCreate", "ContactFilter",
    "ContactRelationships", "ContactStatus", "ContactUpdate", "ContactWriteStatus",
    "CustomFieldDefinition", "CustomFieldDefinitionAttributes",
    "Deal", "DealAttributes", "DealCreate", "DealFilter", "DealRelationships", "DealUpdate",
    "NameFilter", "NoFilter", "UpdatedSinceFilter",
    "Owner", "OwnerAttributes",
    "Page", "RelationshipPage", "Resource", "ResourceIdentifier", "ResourceMeta",
    "Stage", "StageAttributes",
    "Tag", "TagAttributes",
    "Task", "TaskAttributes", "TaskCreate", "TaskFilter", "TaskPriority",
    "TaskRelationships", "TaskStatus", "TaskUpdate", "TaskWritePriority", "TaskWriteStatus",
    "ToMany", "ToOne", "UpsertResult", "WriteModel",
]

"""Python SDK for the Lime Go Agentic public CRM API.

Quick start::

    from decimal import Decimal
    from lime_go_agentic import LimeGoClient, DealCreate

    with LimeGoClient(client_id="...", client_secret="...", environment="staging") as lime:
        result = lime.deals.upsert("AVT-2026-0042", DealCreate(name="NaaS Kontor", value=Decimal("125000")))
        print(result.created, result.resource.id)

See ``README.md`` for authentication, concurrency (ETag / If-Match) and the change feed.
"""

from __future__ import annotations

import logging

from ._transport import Response
from .client import AsyncLimeGoClient, LimeGoClient
from .config import ALL_SCOPES, ENVIRONMENT_URLS, Config
from .errors import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConfigurationError,
    ConflictError,
    ErrorObject,
    ForbiddenError,
    GoneError,
    LimeGoError,
    MissingETagError,
    NotAcceptableError,
    NotFoundError,
    PayloadTooLargeError,
    PreconditionFailedError,
    PreconditionRequiredError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    UnauthorizedError,
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
)
from .models import (
    Activity,
    ActivityCreate,
    ActivityType,
    ActivityUpdate,
    Change,
    ChangePage,
    Company,
    CompanyCreate,
    CompanyUpdate,
    Contact,
    ContactCreate,
    ContactUpdate,
    CustomFieldDefinition,
    Deal,
    DealCreate,
    DealUpdate,
    Owner,
    Page,
    RelationshipPage,
    Resource,
    Stage,
    Tag,
    Task,
    TaskCreate,
    TaskUpdate,
    UpsertResult,
)

__version__ = "26.10.14"

# Silent unless the host app configures a handler. The SDK logs to "lime_go_agentic" at
# DEBUG (method, path, status, timing, request_id) and WARNING (retries), and never logs
# credentials, tokens, headers or request/response bodies.
logging.getLogger("lime_go_agentic").addHandler(logging.NullHandler())

__all__ = [
    "__version__",
    "LimeGoClient", "AsyncLimeGoClient", "Config", "Response", "ALL_SCOPES", "ENVIRONMENT_URLS",
    # models
    "Activity", "ActivityCreate", "ActivityUpdate", "ActivityType",
    "Change", "ChangePage",
    "Company", "CompanyCreate", "CompanyUpdate",
    "Contact", "ContactCreate", "ContactUpdate",
    "CustomFieldDefinition",
    "Deal", "DealCreate", "DealUpdate",
    "Owner", "Page", "RelationshipPage", "Resource", "Stage", "Tag",
    "Task", "TaskCreate", "TaskUpdate", "UpsertResult",
    # errors
    "LimeGoError", "ConfigurationError", "AuthenticationError", "MissingETagError",
    "APIError", "APIConnectionError", "APITimeoutError", "APIStatusError", "ErrorObject",
    "BadRequestError", "UnauthorizedError", "ForbiddenError", "NotFoundError",
    "NotAcceptableError", "ConflictError", "GoneError", "PreconditionFailedError",
    "PayloadTooLargeError", "UnsupportedMediaTypeError", "UnprocessableEntityError",
    "PreconditionRequiredError", "RateLimitError", "ServerError", "ServiceUnavailableError",
]

"""The change feed (``GET /api/v1/changes``) used for incremental synchronisation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .common import _Model


class ChangeAttributes(_Model):
    #: Resource type that changed (e.g. ``companies``).
    resource_type: str
    resource_id: str
    #: Revision of the resource after the change.
    revision: str
    #: True when the change is a deletion.
    deleted: bool
    #: The integration (OAuth client) that made the change, or ``None`` for a user/agent.
    #: Compare with your own integration id to skip echoes of your own writes.
    origin_integration_id: str | None = None


class Change(_Model):
    id: str
    type: Literal["changes"] = "changes"
    attributes: ChangeAttributes


@dataclass
class ChangePage:
    """One page of the change feed."""

    data: list[Change]
    #: Durable cursor: persist it and pass it to the next read to resume.
    cursor: str
    #: More changes are available right now.
    has_more: bool = False
    #: True when this response is a synchronisation checkpoint (no backlog replayed).
    checkpoint: bool = False


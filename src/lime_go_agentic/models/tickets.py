"""Support tickets: hand a chatbot conversation to the Lime support inbox (create only)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import Resource, WriteModel, _Model

TicketMessageRole = Literal["customer", "assistant", "agent"]
TicketStatus = Literal["open"]


class TicketAttributes(_Model):
    #: Ticket number shown in the support inbox.
    number: int | None = None
    status: TicketStatus | None = None
    source: str | None = None


class Ticket(Resource):
    """The creation receipt. Repeating a create returns the same receipt."""

    type: Literal["tickets"] = "tickets"
    attributes: TicketAttributes = Field(default_factory=TicketAttributes)


class TicketMessage(BaseModel):
    """One transcript message, plain text."""

    model_config = ConfigDict(extra="forbid")

    role: TicketMessageRole
    body: str = Field(min_length=1, max_length=8000)
    sent_at: datetime


class TicketCreate(WriteModel):
    """Body for ``tickets.create``.

    ``external_conversation_id`` is owned by the integration and immutable: a repeat with
    the same content returns the original receipt, changed content raises ``ConflictError``.
    ``messages`` are chronological; the whole transcript is limited to 48 KiB of encoded
    JSON. ``company_id`` links an existing company (also needs ``companies:read``); omit it
    to let Lime link the sender by a unique exact ``customer_email`` match.
    """

    subject: str = Field(min_length=1, max_length=998)
    customer_email: str = Field(min_length=1, max_length=320)
    source: str = Field(min_length=1, max_length=40)
    external_conversation_id: str = Field(min_length=1, max_length=128)
    messages: list[TicketMessage] = Field(min_length=1, max_length=100)
    customer_name: str | None = Field(default=None, min_length=1, max_length=500)
    company_id: str | None = None

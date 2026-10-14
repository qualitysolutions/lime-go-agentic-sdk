"""The SDK against real API responses, recorded and sanitized by scripts/record_fixtures.py.

Unlike the spec-derived payloads in conftest.py these are what the live API returned
(2026-10-14), with values replaced but shapes, nulls, enums and ETags kept.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lime_go_agentic import LimeGoClient

from .conftest import BASE, jsonapi

LIVE = Path(__file__).parent / "fixtures" / "live"
#: API path segment -> client attribute.
RESOURCES = {
    "companies": "companies", "contacts": "contacts", "deals": "deals", "tasks": "tasks",
    "activities": "activities", "owners": "owners", "stages": "stages", "tags": "tags",
    "activity-types": "activity_types", "custom-field-definitions": "custom_field_definitions",
}


def load(name: str) -> dict:
    return json.loads((LIVE / f"{name}.json").read_text())


@pytest.mark.parametrize("path", sorted(RESOURCES))
def test_list_page_parses(client: LimeGoClient, respx_mock, path: str) -> None:
    body = load(f"{path}_list")["body"]
    respx_mock.get(f"{BASE}/api/v1/{path}").mock(return_value=jsonapi(200, body))
    page = getattr(client, RESOURCES[path]).list()
    assert [r.id for r in page.data] == [r["id"] for r in body["data"]]
    assert page.next_url == body["links"].get("next")


@pytest.mark.parametrize("path", sorted(p for p in RESOURCES if (LIVE / f"{p}_get.json").exists()))
def test_get_parses_and_derived_etag_matches_response(client: LimeGoClient, respx_mock, path: str) -> None:
    fx = load(f"{path}_get")
    rid = fx["body"]["data"]["id"]
    respx_mock.get(f"{BASE}/api/v1/{path}/{rid}").mock(return_value=jsonapi(200, fx["body"], etag=fx.get("etag")))
    resource = getattr(client, RESOURCES[path]).get(rid)
    assert resource.id == rid and resource.etag == fx.get("etag")
    # The same record as a list item (no response ETag) must derive the same value.
    as_list_item = type(resource).model_validate(fx["body"]["data"])
    assert as_list_item.etag == fx.get("etag")  # None for owners (no revision)


def test_changes_checkpoint_then_page(client: LimeGoClient, respx_mock) -> None:
    respx_mock.get(f"{BASE}/api/v1/changes").mock(side_effect=[
        jsonapi(200, load("changes_checkpoint")["body"]), jsonapi(200, load("changes_page")["body"])])
    first = client.changes.read()
    assert first.checkpoint is True and first.cursor
    nxt = client.changes.read(first.cursor)
    assert nxt.has_more is False and nxt.data == []
    assert respx_mock.calls.last.request.url.params["cursor"] == first.cursor

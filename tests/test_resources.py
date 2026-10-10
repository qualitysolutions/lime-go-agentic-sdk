"""Resource behaviour: documents, ETags, pagination, upsert, relationships, changes."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from lime_go_agentic import LimeGoClient, MissingETagError
from lime_go_agentic.models import (
    ActivityCreate,
    ActivityUpdate,
    Company,
    CompanyUpdate,
    DealCreate,
    Owner,
    TaskCreate,
)

from .conftest import API, company, jsonapi

CID = "11111111-1111-1111-1111-111111111111"


def test_read_model_parses_attributes_and_relationships(client: LimeGoClient, respx_mock) -> None:
    respx_mock.get(f"{API}/companies/{CID}").mock(return_value=jsonapi(200, {"data": company()}, etag='W/"3"'))
    c = client.companies.get(CID)
    assert isinstance(c, Company)
    assert c.attributes.status == "customer"
    assert c.attributes.custom_fields == {"avtalsnummer": "AVT-1"}
    assert c.attributes.updated_at == datetime(2026, 10, 2, 9, 30, tzinfo=timezone.utc)
    assert c.relationships.owner.id == "22222222-2222-2222-2222-222222222222"
    assert c.relationships.tags.ids == ["33333333-3333-3333-3333-333333333333"]
    assert c.revision == "3" and c.etag == 'W/"3"'


def test_unknown_attributes_are_kept(client: LimeGoClient, respx_mock) -> None:
    raw = company()
    raw["attributes"]["brand_new_field"] = 7
    respx_mock.get(f"{API}/companies/{CID}").mock(return_value=jsonapi(200, {"data": raw}))
    assert client.companies.get(CID).attributes.model_extra == {"brand_new_field": 7}


def test_update_sends_only_set_fields_and_if_match(client: LimeGoClient, respx_mock) -> None:
    respx_mock.get(f"{API}/companies/{CID}").mock(return_value=jsonapi(200, {"data": company()}, etag='"3"'))
    route = respx_mock.patch(f"{API}/companies/{CID}").mock(
        return_value=jsonapi(200, {"data": company(rev="4")}, etag='"4"'))
    current = client.companies.get(CID)
    updated = client.companies.update(CID, CompanyUpdate(city=None, owner=None, tags=[]), if_match=current)
    req = route.calls.last.request
    assert req.headers["if-match"] == '"3"'
    assert json.loads(req.content) == {"data": {
        "type": "companies", "id": CID,
        "attributes": {"city": None},
        "relationships": {"owner": {"data": None}, "tags": {"data": []}},
    }}
    assert updated.etag == '"4"'


def test_list_item_has_no_etag(client: LimeGoClient, respx_mock) -> None:
    respx_mock.get(f"{API}/companies").mock(return_value=jsonapi(200, {"data": [company()], "links": {}}, etag='"p"'))
    item = client.companies.list().data[0]
    with pytest.raises(MissingETagError):
        client.companies.delete(item.id, if_match=item)


def test_delete_with_explicit_etag(client: LimeGoClient, respx_mock) -> None:
    route = respx_mock.delete(f"{API}/companies/{CID}").mock(return_value=jsonapi(204, None))
    client.companies.delete(CID, if_match='"3"')
    assert route.calls.last.request.headers["if-match"] == '"3"'


def test_non_nullable_field_cannot_be_null() -> None:
    with pytest.raises(ValidationError, match="name cannot be null"):
        CompanyUpdate(name=None)
    with pytest.raises(ValidationError, match="status cannot be null"):
        CompanyUpdate(status=None)


def test_write_models_forbid_unknown_fields_and_bad_enums() -> None:
    with pytest.raises(ValidationError):
        CompanyUpdate(nmae="typo")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        CompanyUpdate(status="unknown")  # type: ignore[arg-type]  # read-only value


def test_deal_value_decimal_string() -> None:
    doc = DealCreate(name="NaaS", value=Decimal("125000.5"), probability=60,
                     expected_close_date=date(2026, 12, 1), owners=["o1"]).to_document("deals")
    assert doc["data"]["attributes"] == {
        "name": "NaaS", "value": "125000.5", "probability": 60, "expected_close_date": "2026-12-01"}
    assert doc["data"]["relationships"] == {"owners": {"data": [{"type": "owners", "id": "o1"}]}}
    assert DealCreate(name="x", value=Decimal("1E+3")).to_document("deals")["data"]["attributes"]["value"] == "1000"
    with pytest.raises(ValidationError):
        DealCreate(name="x", value=Decimal("1.23456"))
    with pytest.raises(ValidationError):
        DealCreate(name="x", probability=101)


def test_activity_type_alias_round_trips() -> None:
    doc = ActivityCreate(activity_type="call", content="Ringde", deal="d1").to_document("activities")
    assert doc == {"data": {"type": "activities",
                            "attributes": {"type": "call", "content": "Ringde"},
                            "relationships": {"deal": {"data": {"type": "deals", "id": "d1"}}}}}
    assert ActivityUpdate(content="x").to_document("activities", resource_id="a1")["data"] == {
        "type": "activities", "id": "a1", "attributes": {"content": "x"}}


def test_task_create_requires_owner_key_even_if_null() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="Ring kunden")  # type: ignore[call-arg]
    doc = TaskCreate(title="Ring kunden", owner=None).to_document("tasks")
    assert doc["data"]["relationships"] == {"owner": {"data": None}}


def test_client_generated_id_on_create() -> None:
    from lime_go_agentic.models import CompanyCreate

    doc = CompanyCreate(name="A", id="99999999-9999-9999-9999-999999999999").to_document("companies")
    assert doc["data"]["id"] == "99999999-9999-9999-9999-999999999999"
    assert "id" not in doc["data"]["attributes"]


def test_list_params_and_iter_follows_next(client: LimeGoClient, respx_mock) -> None:
    route = respx_mock.get(f"{API}/companies").mock(side_effect=[
        jsonapi(200, {"data": [company("a")],
                      "links": {"next": f"{API}/companies?page[after]=CUR&page[size]=100"}}),
        jsonapi(200, {"data": [company("b")], "links": {"next": None}}),
    ])
    since = datetime(2026, 10, 1, tzinfo=timezone.utc)
    ids = [c.id for c in client.companies.iter({"status": "customer", "updated_since": since},
                                               fields=["name", "status"], include=["owner"])]
    assert ids == ["a", "b"]
    first, second = (dict(c.request.url.params) for c in route.calls)
    assert first == {"filter[status]": "customer", "filter[updated_since]": "2026-10-01T00:00:00+00:00",
                     "page[size]": "100", "fields[companies]": "name,status", "include": "owner"}
    assert second == {"page[after]": "CUR", "page[size]": "100"}  # links.next followed verbatim


def test_included_resources_are_typed(client: LimeGoClient, respx_mock) -> None:
    owner = {"type": "owners", "id": "o1", "attributes": {"first_name": "Ada", "last_name": "L", "email": None}}
    respx_mock.get(f"{API}/companies").mock(return_value=jsonapi(200, {
        "data": [company()], "included": [owner], "links": {}}))
    page = client.companies.list(include=["owner"])
    assert isinstance(page.included[0], Owner)
    assert page.included[0].attributes.first_name == "Ada"
    assert not page.has_more


def test_page_size_validated(client: LimeGoClient) -> None:
    with pytest.raises(ValueError):
        client.companies.list(page_size=101)


def test_upsert_by_external_id(client: LimeGoClient, respx_mock) -> None:
    from lime_go_agentic.models import CompanyCreate

    route = respx_mock.put(f"{API}/companies/external/AVT%2F2026%2F42").mock(
        side_effect=[jsonapi(201, {"data": company()}, etag='"1"'), jsonapi(200, {"data": company()}, etag='"2"')])
    first = client.companies.upsert("AVT/2026/42", CompanyCreate(name="Acme AB"))
    second = client.companies.upsert("AVT/2026/42", CompanyCreate(name="Acme AB"), if_match=first.resource)
    assert first.created is True and second.created is False
    assert "if-match" not in route.calls[0].request.headers
    assert route.calls[1].request.headers["if-match"] == '"1"'
    with pytest.raises(ValueError):
        client.companies.upsert("x" * 129, CompanyCreate(name="A"))


def test_relationship_add_returns_parent_etag(client: LimeGoClient, respx_mock) -> None:
    route = respx_mock.post(f"{API}/deals/d1/relationships/contacts").mock(return_value=jsonapi(200, {
        "data": [{"type": "contacts", "id": "c1"}, {"type": "contacts", "id": "c2"}],
        "links": {"self": "x", "next": None}, "meta": {"truncated": False}}, etag='"9"'))
    page = client.deals.contacts.add("d1", ["c2"], if_match='"8"')
    assert json.loads(route.calls.last.request.content) == {"data": [{"type": "contacts", "id": "c2"}]}
    assert route.calls.last.request.headers["if-match"] == '"8"'
    assert page.ids == ["c1", "c2"] and page.etag == '"9"' and page.truncated is False
    with pytest.raises(ValueError):
        client.deals.contacts.replace("d1", [str(i) for i in range(101)], if_match='"9"')


def test_changes_checkpoint_then_resume(client: LimeGoClient, respx_mock) -> None:
    change = {"type": "changes", "id": "ch1", "attributes": {
        "resource_type": "deals", "resource_id": "d1", "revision": "5", "deleted": False,
        "origin_integration_id": None}}
    route = respx_mock.get(f"{API}/changes").mock(side_effect=[
        jsonapi(200, {"data": [], "meta": {"cursor": "C0", "checkpoint": True, "has_more": False}}),
        jsonapi(200, {"data": [change], "meta": {"cursor": "C1", "has_more": True}}),
        jsonapi(200, {"data": [], "meta": {"cursor": "C2", "has_more": False}}),
    ])
    checkpoint = client.changes.read()
    assert checkpoint.checkpoint and checkpoint.cursor == "C0"
    pages = list(client.changes.iter_pages(checkpoint.cursor))
    assert [p.cursor for p in pages] == ["C1", "C2"]
    assert pages[0].data[0].attributes.resource_id == "d1"
    assert [dict(c.request.url.params) for c in route.calls] == [{}, {"cursor": "C0"}, {"cursor": "C1"}]


async def test_async_iter_and_relationships(async_client, respx_mock) -> None:
    respx_mock.get(f"{API}/deals").mock(return_value=jsonapi(200, {"data": [
        {"type": "deals", "id": "d1", "attributes": {"name": "N", "value": "10.50"}, "relationships": {},
         "meta": {"revision": "1"}}], "links": {"next": None}}))
    deals = [d async for d in async_client.deals.iter()]
    assert deals[0].attributes.value == Decimal("10.50")
    respx_mock.get(f"{API}/tasks/t1/relationships/deals").mock(return_value=jsonapi(200, {
        "data": [{"type": "deals", "id": "d1"}], "links": {"next": None}, "meta": {}}))
    assert [i async for i in async_client.tasks.deals.iter("t1")] == ["d1"]

"""Auth, headers, idempotency, retries and error mapping."""

from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs

import httpx
import pytest

from lime_go_agentic import (
    AuthenticationError,
    Config,
    ConflictError,
    LimeGoClient,
    PreconditionFailedError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from lime_go_agentic.models import CompanyCreate

from .conftest import API, BASE, JSONAPI, TOKEN_URL, company, jsonapi, mock_token


def test_token_request_is_form_encoded_client_credentials(respx_mock) -> None:
    token = mock_token(respx_mock)
    respx_mock.get(f"{API}/companies/abc").mock(return_value=jsonapi(200, {"data": company()}))
    cfg = Config(client_id="cid", client_secret="s3cr3t", base_url=BASE,
                 scopes=("companies:read", "companies:write"))
    with LimeGoClient(cfg) as lime:
        lime.companies.get("abc")
    form = parse_qs(token.calls.last.request.content.decode())
    assert form == {
        "grant_type": ["client_credentials"],
        "client_id": ["cid"],
        "client_secret": ["s3cr3t"],
        "scope": ["companies:read companies:write"],
    }


def test_token_is_cached_and_scope_exposed(client: LimeGoClient, respx_mock) -> None:
    route = respx_mock.get(f"{API}/companies/abc").mock(return_value=jsonapi(200, {"data": company()}))
    client.companies.get("abc")
    client.companies.get("abc")
    assert respx_mock.routes[0].call_count == 1  # token fetched once
    assert route.calls.last.request.headers["authorization"] == "Bearer TESTTOKEN"
    assert client.granted_scopes == ("companies:read", "deals:read")


def test_401_refreshes_token_once(config: Config, respx_mock) -> None:
    token = respx_mock.post(TOKEN_URL).mock(side_effect=[
        httpx.Response(200, json={"access_token": "OLD", "token_type": "Bearer", "expires_in": 1800, "scope": ""}),
        httpx.Response(200, json={"access_token": "NEW", "token_type": "Bearer", "expires_in": 1800, "scope": ""}),
    ])
    route = respx_mock.get(f"{API}/companies/abc").mock(side_effect=[
        jsonapi(401, {"errors": [{"status": "401", "code": "invalid_token", "title": "Invalid token"}]}),
        jsonapi(200, {"data": company()}),
    ])
    with LimeGoClient(config) as lime:
        lime.companies.get("abc")
    assert token.call_count == 2
    assert route.calls.last.request.headers["authorization"] == "Bearer NEW"


def test_persistent_401_raises(client: LimeGoClient, respx_mock) -> None:
    respx_mock.get(f"{API}/companies/abc").mock(
        return_value=jsonapi(401, {"errors": [{"status": "401", "code": "invalid_token", "title": "Invalid token"}]}))
    with pytest.raises(UnauthorizedError) as exc:
        client.companies.get("abc")
    assert exc.value.code == "invalid_token"


def test_token_rejection_raises_authentication_error(config: Config, respx_mock) -> None:
    respx_mock.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))
    with LimeGoClient(config) as lime, pytest.raises(AuthenticationError) as exc:
        lime.companies.get("abc")
    assert exc.value.status_code == 401


def test_jsonapi_headers_and_body_on_write(client: LimeGoClient, respx_mock) -> None:
    route = respx_mock.post(f"{API}/companies").mock(return_value=jsonapi(201, {"data": company()}, etag='"3"'))
    client.companies.create(CompanyCreate(name="Acme AB"))
    req = route.calls.last.request
    assert req.headers["accept"] == JSONAPI
    assert req.headers["content-type"] == JSONAPI
    assert len(req.headers["idempotency-key"]) >= 1
    assert json.loads(req.content) == {"data": {"type": "companies", "attributes": {"name": "Acme AB"}}}


def test_get_has_no_idempotency_key_or_content_type(client: LimeGoClient, respx_mock) -> None:
    route = respx_mock.get(f"{API}/companies/abc").mock(return_value=jsonapi(200, {"data": company()}))
    client.companies.get("abc")
    req = route.calls.last.request
    assert "idempotency-key" not in req.headers
    assert "content-type" not in req.headers
    assert req.headers["accept"] == JSONAPI


def test_retry_reuses_the_same_idempotency_key(respx_mock) -> None:
    mock_token(respx_mock)
    route = respx_mock.post(f"{API}/companies").mock(side_effect=[
        jsonapi(503, {"errors": [{"status": "503", "code": "unavailable", "title": "Down"}]}, **{"retry-after": "0"}),
        jsonapi(201, {"data": company()}),
    ])
    with LimeGoClient(client_id="c", client_secret="s", base_url=BASE, max_retries=2) as lime:
        lime.companies.create(CompanyCreate(name="Acme AB"))
    keys = {c.request.headers["idempotency-key"] for c in route.calls}
    assert route.call_count == 2 and len(keys) == 1


def test_caller_supplied_idempotency_key_is_used(client: LimeGoClient, respx_mock) -> None:
    route = respx_mock.post(f"{API}/companies").mock(return_value=jsonapi(201, {"data": company()}))
    client.companies.create(CompanyCreate(name="Acme AB"), idempotency_key="crm-sync-AVT-1")
    assert route.calls.last.request.headers["idempotency-key"] == "crm-sync-AVT-1"


def test_retry_after_above_cap_is_not_slept(respx_mock) -> None:
    """Staging currently answers 503 with Retry-After: 60 (observed 2026-10-10)."""
    mock_token(respx_mock)
    body = {"errors": [{"code": "unavailable", "meta": {"request_id": "rid-1"}, "status": "503",
                        "title": "Service temporarily unavailable"}]}
    route = respx_mock.get(f"{API}/companies/abc").mock(
        return_value=jsonapi(503, body, **{"retry-after": "60", "x-request-id": "rid-1"}))
    with LimeGoClient(client_id="c", client_secret="s", base_url=BASE, max_retries=3) as lime:
        with pytest.raises(ServiceUnavailableError) as exc:
            lime.companies.get("abc")
    assert route.call_count == 1
    assert exc.value.code == "unavailable"
    assert exc.value.request_id == "rid-1"
    assert exc.value.errors[0].meta == {"request_id": "rid-1"}
    assert "Service temporarily unavailable" in str(exc.value)


@pytest.mark.parametrize(("status", "exc_type"), [(409, ConflictError), (412, PreconditionFailedError)])
def test_status_mapping(client: LimeGoClient, respx_mock, status: int, exc_type: type) -> None:
    respx_mock.get(f"{API}/companies/abc").mock(
        return_value=jsonapi(status, {"errors": [{"status": str(status), "code": "x", "title": "t"}]}))
    with pytest.raises(exc_type):
        client.companies.get("abc")


def test_logs_never_contain_secrets(config: Config, respx_mock, caplog) -> None:
    mock_token(respx_mock, token="SUPERSECRETTOKEN")
    respx_mock.post(f"{API}/companies").mock(return_value=jsonapi(201, {"data": company()}))
    caplog.set_level(logging.DEBUG, logger="lime_go_agentic")
    with LimeGoClient(config) as lime:
        lime.companies.create(CompanyCreate(name="Hemligt Bolag AB"))
    text = caplog.text
    assert "POST" in text
    for secret in ("SUPERSECRETTOKEN", "s3cr3t", "Hemligt Bolag"):
        assert secret not in text


async def test_async_create_and_get(async_client, respx_mock) -> None:
    respx_mock.post(f"{API}/companies").mock(return_value=jsonapi(201, {"data": company()}, etag='"3"'))
    created = await async_client.companies.create(CompanyCreate(name="Acme AB"))
    assert created.etag == '"3"'
    assert created.attributes.name == "Acme AB"

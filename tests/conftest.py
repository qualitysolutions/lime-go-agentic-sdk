from __future__ import annotations

import httpx
import pytest

from lime_go_agentic import AsyncLimeGoClient, Config, LimeGoClient

BASE = "https://lime.test"
API = f"{BASE}/api/v1"
TOKEN_URL = f"{BASE}/oauth/token"
JSONAPI = "application/vnd.api+json"


@pytest.fixture
def config() -> Config:
    return Config(client_id="cid", client_secret="s3cr3t", base_url=BASE, max_retries=0)


def mock_token(respx_mock, *, token: str = "TESTTOKEN", scope: str = "companies:read deals:read"):
    return respx_mock.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": token, "token_type": "Bearer", "expires_in": 1800, "scope": scope},
        )
    )


def jsonapi(status: int, body: object, *, etag: str | None = None, **headers: str) -> httpx.Response:
    h = {"content-type": JSONAPI, **headers}
    if etag:
        h["etag"] = etag
    return httpx.Response(status, json=body, headers=h)


def company(cid: str = "11111111-1111-1111-1111-111111111111", name: str = "Acme AB", rev: str = "3") -> dict:
    """A companies resource object shaped exactly like the OpenAPI schema."""
    return {
        "type": "companies",
        "id": cid,
        "attributes": {
            "name": name,
            "business_id": "556000-0000",
            "status": "customer",
            "city": "Stockholm",
            "custom_fields": {"avtalsnummer": "AVT-1"},
            "created_at": "2026-10-01T08:00:00Z",
            "updated_at": "2026-10-02T09:30:00Z",
        },
        "relationships": {
            "owner": {"data": {"type": "owners", "id": "22222222-2222-2222-2222-222222222222"}},
            "tags": {"data": [{"type": "tags", "id": "33333333-3333-3333-3333-333333333333"}]},
        },
        "meta": {"revision": rev},
    }


@pytest.fixture
def client(config: Config, respx_mock):
    mock_token(respx_mock)
    c = LimeGoClient(config)
    yield c
    c.close()


@pytest.fixture
async def async_client(config: Config, respx_mock):
    mock_token(respx_mock)
    c = AsyncLimeGoClient(config)
    yield c
    await c.aclose()

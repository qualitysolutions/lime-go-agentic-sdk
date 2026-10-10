"""Read-only smoke tests against a live instance. Run with:  pytest -m integration

Needs LIME_GO_ENV (or LIME_GO_BASE_URL), LIME_GO_CLIENT_ID and LIME_GO_CLIENT_SECRET.
Only GETs are made, so it is safe to point at any instance.
"""

from __future__ import annotations

import os

import pytest

from lime_go_agentic import LimeGoClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("LIME_GO_CLIENT_ID"), reason="LIME_GO_* credentials not set"),
]


@pytest.fixture(scope="module")
def lime():
    with LimeGoClient() as client:
        yield client


def test_token_and_scopes(lime: LimeGoClient) -> None:
    assert isinstance(lime.granted_scopes, tuple)


@pytest.mark.parametrize("name", ["companies", "contacts", "deals", "activities", "tasks",
                                  "owners", "stages", "tags", "activity_types",
                                  "custom_field_definitions"])
def test_list_first_page_parses(lime: LimeGoClient, name: str) -> None:
    page = getattr(lime, name).list(page_size=5)
    for item in page.data:
        assert item.id


def test_get_returns_etag(lime: LimeGoClient) -> None:
    page = lime.companies.list(page_size=1)
    if not page.data:
        pytest.skip("no companies on this instance")
    company = lime.companies.get(page.data[0].id)
    assert company.etag, "single-resource responses should carry an ETag"


def test_changes_checkpoint(lime: LimeGoClient) -> None:
    page = lime.changes.read()
    assert page.cursor

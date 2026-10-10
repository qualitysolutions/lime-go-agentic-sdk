from __future__ import annotations

import pytest

from lime_go_agentic import Config, ConfigurationError, LimeGoClient


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in list(os.environ):
        if key.startswith("LIME_GO_"):
            monkeypatch.delenv(key)


def test_no_default_environment() -> None:
    with pytest.raises(ConfigurationError, match="base_url"):
        Config(client_id="a", client_secret="b")


def test_known_environment_resolves_base_url() -> None:
    cfg = Config(client_id="a", client_secret="b", environment="STAGING")
    assert cfg.base_url == "https://agentic.staging.lime-go.com"
    assert cfg.token_url == "https://agentic.staging.lime-go.com/oauth/token"


def test_unknown_environment_requires_base_url() -> None:
    with pytest.raises(ConfigurationError):
        Config(client_id="a", client_secret="b", environment="prod")
    cfg = Config(client_id="a", client_secret="b", environment="prod", base_url="https://x.example/")
    assert cfg.base_url == "https://x.example"


def test_missing_credentials() -> None:
    with pytest.raises(ConfigurationError):
        Config(client_id="", client_secret="b", environment="staging")


def test_from_env_is_environment_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIME_GO_ENV", "prod")
    monkeypatch.setenv("LIME_GO_CLIENT_ID", "generic")
    monkeypatch.setenv("LIME_GO_PROD_CLIENT_ID", "prod-id")
    monkeypatch.setenv("LIME_GO_PROD_CLIENT_SECRET", "prod-secret")
    monkeypatch.setenv("LIME_GO_PROD_BASE_URL", "https://prod.example")
    monkeypatch.setenv("LIME_GO_SCOPES", "deals:read  changes:read")
    cfg = Config.from_env()
    assert (cfg.client_id, cfg.client_secret, cfg.base_url) == ("prod-id", "prod-secret", "https://prod.example")
    assert cfg.scopes == ("deals:read", "changes:read")


def test_client_rejects_config_plus_kwargs() -> None:
    cfg = Config(client_id="a", client_secret="b", environment="staging")
    with pytest.raises(TypeError):
        LimeGoClient(cfg, client_id="x")

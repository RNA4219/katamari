"""OAuth authentication tests for M1.5."""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Iterator, Tuple

import pytest
from fastapi.testclient import TestClient


def _bootstrap_chainlit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch | None = None) -> Tuple[object, object, str | None, list[str]]:
    """Bootstrap Chainlit app for testing OAuth callbacks."""
    app_root = tmp_path / "app"
    app_root.mkdir()
    previous_root = os.environ.get("CHAINLIT_APP_ROOT")
    os.environ["CHAINLIT_APP_ROOT"] = str(app_root)

    project_root = Path(__file__).resolve().parents[2]
    added_paths: list[str] = []
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        added_paths.append(str(project_root))

    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
        added_paths.append(str(src_path))

    for module_name in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(module_name, None)
    sys.modules.pop("src.app", None)

    chainlit_server = import_module("chainlit.server")
    app_module = import_module("src.app")

    return chainlit_server.app, app_module, previous_root, added_paths


@pytest.fixture()
def oauth_context_no_provider(tmp_path: Path) -> Iterator[Tuple[object, object]]:
    """Fixture providing Chainlit app context without OAuth providers configured."""
    app, module, previous_root, added_paths = _bootstrap_chainlit(tmp_path)
    yield app, module

    for key in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(key, None)
    sys.modules.pop("src.app", None)

    for _ in added_paths:
        sys.path.pop(0)

    if previous_root is None:
        os.environ.pop("CHAINLIT_APP_ROOT", None)
    else:
        os.environ["CHAINLIT_APP_ROOT"] = previous_root


@pytest.fixture()
def oauth_context_with_github(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Tuple[object, object]]:
    """Fixture providing Chainlit app context with GitHub OAuth configured."""
    # Set OAuth env vars BEFORE importing the module
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_ID", "test-github-client-id")
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_SECRET", "test-github-client-secret")

    app, module, previous_root, added_paths = _bootstrap_chainlit(tmp_path, monkeypatch)
    yield app, module

    for key in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(key, None)
    sys.modules.pop("src.app", None)

    for _ in added_paths:
        sys.path.pop(0)

    if previous_root is None:
        os.environ.pop("CHAINLIT_APP_ROOT", None)
    else:
        os.environ["CHAINLIT_APP_ROOT"] = previous_root


@pytest.fixture()
def auth_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set up CHAINLIT_AUTH_SECRET for testing."""
    secret = "oauth-test-secret"
    monkeypatch.setenv("CHAINLIT_AUTH_SECRET", secret)
    return secret


def test_oauth_callback_impl_returns_default_user() -> None:
    """Test that OAuth callback implementation returns the default user from provider."""
    # Import cl.User for type checking
    import chainlit as cl

    # Simulate OAuth callback with mock user data
    raw_user_data = {
        "login": "testuser",
        "email": "testuser@example.com",
        "avatar_url": "https://example.com/avatar.png",
    }

    default_user = cl.User(
        identifier="testuser",
        metadata={"image": "https://example.com/avatar.png", "provider": "github"},
    )

    # Import and call the OAuth callback implementation directly
    import asyncio
    from src.app import _oauth_callback_impl

    result = asyncio.run(
        _oauth_callback_impl(
            provider_id="github",
            token="test-token",
            raw_user_data=raw_user_data,
            default_app_user=default_user,
            id_token=None,
        )
    )

    assert result is not None
    assert isinstance(result, cl.User)
    assert result.identifier == "testuser"
    assert result.metadata.get("provider") == "github"


def test_oauth_callback_impl_accepts_multiple_providers() -> None:
    """Test that OAuth callback implementation works with different providers."""
    import chainlit as cl
    from src.app import _oauth_callback_impl
    import asyncio

    providers = [
        ("github", {"login": "ghuser", "email": "gh@example.com"}),
        ("google", {"email": "google@example.com", "picture": "https://example.com/pic.png"}),
        ("azure-ad", {"userPrincipalName": "azure@example.com"}),
    ]

    for provider_id, user_data in providers:
        default_user = cl.User(
            identifier=user_data.get("login") or user_data.get("email") or user_data.get("userPrincipalName"),
            metadata={"provider": provider_id},
        )

        result = asyncio.run(
            _oauth_callback_impl(
                provider_id=provider_id,
                token="test-token",
                raw_user_data=user_data,
                default_app_user=default_user,
                id_token=None,
            )
        )

        assert result is not None, f"OAuth callback failed for provider: {provider_id}"
        assert result.metadata.get("provider") == provider_id


def test_oauth_callback_impl_with_id_token() -> None:
    """Test that OAuth callback implementation handles id_token parameter."""
    import chainlit as cl
    from src.app import _oauth_callback_impl
    import asyncio

    default_user = cl.User(
        identifier="testuser",
        metadata={"provider": "azure-ad"},
    )

    result = asyncio.run(
        _oauth_callback_impl(
            provider_id="azure-ad",
            token="test-token",
            raw_user_data={"userPrincipalName": "test@example.com"},
            default_app_user=default_user,
            id_token="test-id-token",
        )
    )

    assert result is not None
    assert result.identifier == "testuser"


def test_has_oauth_provider_configured_detects_github(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that _has_oauth_provider_configured detects GitHub OAuth."""
    # Clear any existing OAuth env vars
    for key in list(os.environ.keys()):
        if key.startswith("OAUTH_"):
            monkeypatch.delenv(key, raising=False)

    # Test without OAuth configured
    from src.app import _has_oauth_provider_configured
    assert _has_oauth_provider_configured() is False

    # Configure GitHub OAuth
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_ID", "test-id")
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_SECRET", "test-secret")

    assert _has_oauth_provider_configured() is True


def test_has_oauth_provider_configured_detects_google(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that _has_oauth_provider_configured detects Google OAuth."""
    # Clear any existing OAuth env vars
    for key in list(os.environ.keys()):
        if key.startswith("OAUTH_"):
            monkeypatch.delenv(key, raising=False)

    # Configure Google OAuth
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "test-id")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "test-secret")

    from src.app import _has_oauth_provider_configured
    assert _has_oauth_provider_configured() is True


def test_healthz_still_requires_bearer_without_oauth(
    oauth_context_no_provider: Tuple[object, object],
    auth_secret: str,
) -> None:
    """Test that /healthz endpoint still requires Bearer token without OAuth configured."""
    chainlit_app, _ = oauth_context_no_provider

    client = TestClient(chainlit_app)

    # Should reject without Bearer token
    response_no_auth = client.get("/healthz")
    assert response_no_auth.status_code == 401

    # Should accept with valid Bearer token
    response_with_auth = client.get(
        "/healthz", headers={"Authorization": f"Bearer {auth_secret}"}
    )
    assert response_with_auth.status_code == 200


def test_metrics_still_requires_bearer_without_oauth(
    oauth_context_no_provider: Tuple[object, object],
    auth_secret: str,
) -> None:
    """Test that /metrics endpoint still requires Bearer token without OAuth configured."""
    chainlit_app, _ = oauth_context_no_provider

    client = TestClient(chainlit_app)

    # Should reject without Bearer token
    response_no_auth = client.get("/metrics")
    assert response_no_auth.status_code == 401

    # Should accept with valid Bearer token
    response_with_auth = client.get(
        "/metrics", headers={"Authorization": f"Bearer {auth_secret}"}
    )
    assert response_with_auth.status_code == 200


def test_header_auth_callback_still_works(
    oauth_context_no_provider: Tuple[object, object],
    auth_secret: str,
) -> None:
    """Test that header auth callback still works."""
    from starlette.datastructures import Headers
    from src.app import _header_auth_callback
    import asyncio
    import chainlit as cl

    # Test with valid token
    valid_headers = Headers({"Authorization": f"Bearer {auth_secret}"})
    result = asyncio.run(_header_auth_callback(valid_headers))

    assert result is not None
    assert isinstance(result, cl.User)
    assert result.identifier == "ops"

    # Test with invalid token
    invalid_headers = Headers({"Authorization": "Bearer invalid-token"})
    result_invalid = asyncio.run(_header_auth_callback(invalid_headers))

    assert result_invalid is None
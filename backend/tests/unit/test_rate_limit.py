"""Unit tests for the rate-limit key function.

Tests `get_org_id_from_jwt_payload` in isolation — no FastAPI, no
httpx, no slowapi. Each test constructs a mock Request with the desired
Authorization header and asserts the returned rate-limit key string.

The function is a pure(ish) function: it reads from the request headers
and returns a string. No side effects, no IO.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from jose import jwt

from app.core.rate_limit import get_org_id_from_jwt_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_request(auth_header: str | None = None) -> MagicMock:
    """Build a minimal mock Request with the given Authorization header.

    If auth_header is None, no Authorization key is set in headers,
    simulating a request with no auth header at all.
    """
    request = MagicMock(name="request")
    if auth_header is not None:
        request.headers = {"Authorization": auth_header}
    else:
        request.headers = {}
    return request


def _encode(
    claims: dict[str, Any], secret: str = "test-secret-not-used-for-verification"
) -> str:
    """Build an unsigned HS256 JWT with the given claims.

    The key is never verified by get_org_id_from_jwt_payload — it calls
    get_unverified_claims. The secret is arbitrary.
    """
    return jwt.encode(claims, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_valid_jwt_returns_sub() -> None:
    """A JWT with a valid ``sub`` claim returns the ``sub`` value."""
    sub_value = "22222222-2222-2222-2222-222222222222"
    token = _encode({"sub": sub_value, "other": "irrelevant"})
    request = _mock_request(f"Bearer {token}")

    key = get_org_id_from_jwt_payload(request)

    assert key == sub_value


def test_jwt_missing_sub_returns_anonymous() -> None:
    """A JWT WITHOUT a ``sub`` claim returns the fallback key."""
    token = _encode({"organization_id": "11111111-1111-1111-1111-111111111111"})
    request = _mock_request(f"Bearer {token}")

    key = get_org_id_from_jwt_payload(request)

    assert key == "anonymous"


def test_missing_auth_header_returns_anonymous() -> None:
    """No Authorization header at all returns the fallback key."""
    request = _mock_request(auth_header=None)

    key = get_org_id_from_jwt_payload(request)

    assert key == "anonymous"


def test_malformed_jwt_returns_anonymous() -> None:
    """A garbage token that can't be decoded returns the fallback key."""
    request = _mock_request("Bearer this.is.not.a.valid.jwt")

    key = get_org_id_from_jwt_payload(request)

    assert key == "anonymous"


def test_empty_token_returns_anonymous() -> None:
    """A 'Bearer ' header with no actual token returns the fallback key."""
    request = _mock_request("Bearer ")

    key = get_org_id_from_jwt_payload(request)

    assert key == "anonymous"


def test_jwt_sub_is_empty_string_returns_anonymous() -> None:
    """A JWT with an empty-string ``sub`` returns the fallback key.

    This exercises the ``if not sub`` guard inside the key function.
    """
    token = _encode({"sub": ""})
    request = _mock_request(f"Bearer {token}")

    key = get_org_id_from_jwt_payload(request)

    assert key == "anonymous"


def test_jwt_sub_is_non_string_returns_anonymous() -> None:
    """A JWT where ``sub`` is not a string (e.g. integer) returns the
    fallback key.  This exercises the ``isinstance(sub, str)`` guard."""
    token = _encode({"sub": 12345})
    request = _mock_request(f"Bearer {token}")

    key = get_org_id_from_jwt_payload(request)

    assert key == "anonymous"

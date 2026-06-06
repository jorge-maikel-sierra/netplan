"""Slowapi-backed rate limiter keyed by organization_id.

Why org_id and not user_id? Spec REQ-MST-005 is explicit: the bucket
is per-organization, not per-user or per-IP. A user switching orgs
should keep separate buckets, but a project with multiple collaborators
in the same org should share one.

The key_func decodes the JWT payload WITHOUT verifying the signature.
This is intentional and safe in our flow:

  1. slowapi reads the Authorization header, decodes the payload,
     extracts organization_id. This is the cheap, pre-auth rate limit.
  2. The actual route handler then runs get_current_user, which DOES
     verify the signature and look up the profile. If that fails, the
     request never reaches the service.

So an attacker who tampers with the JWT to use a different org_id can
either (a) have a real signature that belongs to a different org —
they're just consuming that org's quota, no harm done — or (b) have a
forged signature that fails get_current_user's check and never reaches
the service. There is no way to bypass the service's tenant isolation
via the rate-limit key.
"""
from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from jose import jwt
from jose.exceptions import JWTError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request


# ---------------------------------------------------------------------------
# Key function
# ---------------------------------------------------------------------------


_FALLBACK_KEY = "anonymous"


def get_org_id_from_jwt_payload(request: Request) -> str:
    """Extract the organization_id claim from the JWT Authorization header.

    Returns the string form of the UUID, or `_FALLBACK_KEY` ("anonymous")
    if the header is missing / malformed. slowapi will then bucket all
    anonymous callers together — which is fine because such requests
    will be rejected by get_current_user anyway.

    NO signature verification is performed here on purpose (see module
    docstring). The full validation happens later in the route handler.
    """
    try:
        auth = request.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return _FALLBACK_KEY
        token = auth.split(" ", 1)[1].strip()
        if not token:
            return _FALLBACK_KEY
        claims: dict[str, Any] = jwt.get_unverified_claims(token)
        org_id = claims.get("organization_id")
        if not org_id or not isinstance(org_id, str):
            return _FALLBACK_KEY
        return org_id
    except (JWTError, ValueError, AttributeError, IndexError):
        return _FALLBACK_KEY


# ---------------------------------------------------------------------------
# Limiter instance
# ---------------------------------------------------------------------------


# The key_func is set globally on the Limiter so all `@limiter.limit(...)`
# decorations pick it up automatically. Per-endpoint overrides are still
# possible by passing `key_func=` to `.limit(...)`.
#
# headers_enabled=False: slowapi's _inject_headers requires the endpoint
# to return a starlette.responses.Response so it can append X-RateLimit-*
# headers. Our endpoint returns a Pydantic model that FastAPI serializes
# later, so we can't safely mutate the response from the decorator. The
# Retry-After header is still set by our custom 429 handler.
limiter = Limiter(
    key_func=get_org_id_from_jwt_payload,
    headers_enabled=False,
)


# ---------------------------------------------------------------------------
# Custom exception handler
# ---------------------------------------------------------------------------


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded, response: Any = None
) -> JSONResponse:
    """Convert a slowapi RateLimitExceeded into the project's error format.

    The handler is registered with FastAPI's `add_exception_handler`, so
    FastAPI calls it with (request, exc). Some slowapi versions also
    pass a `response` keyword argument, so we accept it for
    compatibility.

    retry_after is the number of seconds the client should wait before
    retrying. We parse it from the exc attribute when available.
    """
    retry_after = 60  # safe default
    try:
        retry_after = int(getattr(exc, "retry_after", 60) or 60)
    except (TypeError, ValueError):
        retry_after = 60

    body = {
        "error": "RATE_LIMITED",
        "code": 429,
        "detail": f"Demasiadas solicitudes. Reintentá en {retry_after} segundos.",
        "retry_after": retry_after,
    }
    json_response = JSONResponse(status_code=429, content=body)
    json_response.headers["Retry-After"] = str(retry_after)
    return json_response

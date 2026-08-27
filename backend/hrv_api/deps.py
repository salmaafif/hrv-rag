"""
deps.py — request-scoped dependencies shared by every route.

Separated from `app.py` for the same reason the frontend keeps `app/` apart from
`pages/`: this is a rule about who may call the service, not about what any one
endpoint does, and a route file should not have to restate it to be read.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str = Header(default="")) -> bool:
    """
    Reject callers without a key this service issued, and report whether that
    key is also scoped for the technical layer (decision A6).

    Not optional, even during development. The Gemini quota behind this endpoint
    belongs to one person, and an open URL is an open invitation to exhaust it
    before the team has finished testing.

    When `HRV_API_KEYS` is unset the service refuses everything rather than
    allowing everything, because the failure mode of the opposite default is
    silent and expensive.

    The return value is a second, narrower fact: whether the SAME key also
    appears in `HRV_API_KEYS_DEBUG`. `docs/ARSITEKTUR_KARIRLINK_HRV.md` §3.1
    points out that `AnalyzeRequest.include_technical` alone is not an
    enforcement of decision K4, only a body flag — any caller can set it on
    itself. This makes the request body insufficient on its own: a route must
    combine `request.include_technical` with the CALLER's scope, returned
    here, before honouring it. A key can be both a normal key and a debug
    key at once; the two sets are not required to be disjoint.
    """
    allowed = {k.strip() for k in os.getenv("HRV_API_KEYS", "").split(",") if k.strip()}
    if not allowed:
        raise HTTPException(503, "service not configured: HRV_API_KEYS is unset")
    if x_api_key not in allowed:
        raise HTTPException(401, "invalid or missing X-API-Key")

    debug_keys = {k.strip() for k in os.getenv("HRV_API_KEYS_DEBUG", "").split(",")
                 if k.strip()}
    return x_api_key in debug_keys

"""
deps.py — request-scoped dependencies shared by every route.

Separated from `app.py` for the same reason the frontend keeps `app/` apart from
`pages/`: this is a rule about who may call the service, not about what any one
endpoint does, and a route file should not have to restate it to be read.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """
    Reject callers without a key this service issued.

    Not optional, even during development. The Gemini quota behind this endpoint
    belongs to one person, and an open URL is an open invitation to exhaust it
    before the team has finished testing.

    When `HRV_API_KEYS` is unset the service refuses everything rather than
    allowing everything, because the failure mode of the opposite default is
    silent and expensive.
    """
    allowed = {k.strip() for k in os.getenv("HRV_API_KEYS", "").split(",") if k.strip()}
    if not allowed:
        raise HTTPException(503, "service not configured: HRV_API_KEYS is unset")
    if x_api_key not in allowed:
        raise HTTPException(401, "invalid or missing X-API-Key")

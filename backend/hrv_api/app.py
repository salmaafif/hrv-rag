"""
app.py — the HTTP surface KARIRLINK's gateway calls.

Two endpoints, matching `frontend/src/types/api.ts` field for field. That file is
the contract handed to the web team, and their PRD lists the output format of each
FastAPI module as an open question — so this is the answer to it, not a
reinterpretation of it.

WHAT THIS SERVICE IS RESPONSIBLE FOR, AND WHAT IT IS NOT. It computes every number
and writes the Indonesian prose. It cannot enforce how any of that is DISPLAYED,
and two of the project's rules are about display: the user must not be shown
feature names or scores, and the output is an indication of physiological pressure
rather than a diagnosis of anxiety. Once this is an API those become the caller's
obligations, so the technical layer is withheld unless it is explicitly asked for
— the safe thing is the default, rather than something the integrator has to
remember.

GRACEFUL DEGRADATION IS DELIBERATE. The label comes from a deterministic rule that
needs no API key. If Gemini is unreachable, out of quota, or caught inventing a
number, the measurements are still returned and only the prose is missing. The
KARIRLINK PRD treats this module as an optional dependency that must fail softly,
and this is what that means in practice.

LAYOUT. This file used to hold everything: configuration, authentication, both
route handlers, and response assembly. It now holds only the assembly of the
application itself, and the rest is arranged the way `frontend/src` is, so that
somebody who has read one side can navigate the other:

    routes/     one file per endpoint          (frontend: pages/)
    services/   the work each endpoint asks for (frontend: app/, lib/)
    schemas.py  the request and response contract (frontend: types/)
    deps.py     rules about who may call at all
    responses.py  the shared response envelope

Running it:
    pip install -e .   &&   uvicorn hrv_api.app:app --reload
Environment:
    GEMINI_API_KEY   required only for the narrative
    HRV_API_KEYS     comma-separated keys this service will accept
    HRV_CORS_ORIGINS comma-separated origins allowed to call it
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import health, session, timeline

log = logging.getLogger(__name__)

app = FastAPI(
    title="KARIRLINK — HRV stress indication",
    version="1.0",
    description=(
        "Interprets heart-rate variability during interview practice. Returns an "
        "indication of physiological pressure, NOT a diagnosis of anxiety."
    ),
)

# The gateway lives on another origin, so the browser will preflight. Origins are
# configured rather than wildcarded: this endpoint spends a real Gemini quota, and
# `*` would let any page on the internet spend it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv("HRV_CORS_ORIGINS", "").split(",") if o],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(timeline.router)
app.include_router(session.router)

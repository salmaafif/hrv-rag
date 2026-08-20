"""health.py — liveness only."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Liveness only. Says nothing about Gemini, which may be down separately."""
    return {"status": "ok"}

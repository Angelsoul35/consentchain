"""ConsentChain HTTP API."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .scopes import DataCategory, Purpose
from .service import ConsentService

app = FastAPI(
    title="ConsentChain",
    version="1.0.0",
    summary="On-chain patient-consent registry with an AI access-request classifier.",
)

_service: ConsentService | None = None


def get_service() -> ConsentService:
    global _service
    if _service is None:
        _service = ConsentService()
    return _service


def _parse_purpose(name: str) -> Purpose:
    try:
        return Purpose[name.strip().upper()]
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"unknown purpose: {name}") from exc


def _parse_categories(names: list[str]) -> list[DataCategory]:
    out: list[DataCategory] = []
    for name in names:
        try:
            out.append(DataCategory[name.strip().upper()])
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=f"unknown category: {name}") from exc
    return out


class GrantRequest(BaseModel):
    patient: str
    requester: str
    purpose: str
    categories: list[str] = Field(min_length=1)
    ttl_days: int = Field(default=365, ge=1, le=3650)


class RevokeRequest(BaseModel):
    patient: str
    requester: str
    purpose: str


class EvaluateRequest(BaseModel):
    patient: str
    requester: str
    text: str = Field(min_length=1)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok"}


@app.post("/consent/grant", tags=["consent"])
def grant(request: GrantRequest) -> dict:
    return get_service().grant_consent(
        request.patient,
        request.requester,
        _parse_purpose(request.purpose),
        _parse_categories(request.categories),
        ttl_days=request.ttl_days,
    )


@app.post("/consent/revoke", tags=["consent"])
def revoke(request: RevokeRequest) -> dict:
    return get_service().revoke_consent(
        request.patient, request.requester, _parse_purpose(request.purpose)
    )


@app.post("/access/evaluate", tags=["access"])
def evaluate_access(request: EvaluateRequest) -> dict:
    return get_service().evaluate_request(request.patient, request.requester, request.text)

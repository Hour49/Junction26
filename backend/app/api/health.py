"""GET /health: liveness check for the demo machine and CI smoke tests."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Health(BaseModel):
    status: Literal["ok"]


@router.get("/health")
def health() -> Health:
    return Health(status="ok")

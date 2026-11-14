"""Load destination checklist YAML into a validated structure."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


class RequiredDoc(BaseModel):
    type: str
    label: str
    min_count: int = 1
    when: Optional[str] = None
    source: Optional[str] = None


class RuleDef(BaseModel):
    id: str
    check: str
    mode: str = "code"
    docs: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    on_fail: Optional[str] = None
    fail_status: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = None


class Checklist(BaseModel):
    id: str
    version: str
    destination: dict[str, Any] = Field(default_factory=dict)
    filing_center: Optional[str] = None
    reference_currency: str = "EUR"
    fx_rates_to_eur: dict[str, float] = Field(default_factory=dict)
    schengen_countries: list[str] = Field(default_factory=list)
    applicant_profiles: list[str] = Field(default_factory=list)
    required_documents: list[RequiredDoc] = Field(default_factory=list)
    rules: list[RuleDef] = Field(default_factory=list)
    outcome: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


def load_checklist(path: Path | str) -> Checklist:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids = [r["id"] for r in raw.get("rules", [])]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate rule ids in {path}")
    cl = Checklist.model_validate(raw)
    cl.raw = raw
    return cl

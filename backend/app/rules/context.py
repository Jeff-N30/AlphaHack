"""RuleContext + Facts — pure data for checklist checks (no I/O)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from app.models import DocType, Extraction


@dataclass
class Facts:
    """Extractions keyed by doc type. Built from case.yaml or the pipeline."""

    documents: dict[DocType, list[Extraction]] = field(default_factory=dict)
    submission_date: date = field(default_factory=date.today)
    profile: str = "employee"
    application_id: str = "test"

    def get(self, doc_type: DocType | str) -> list[Extraction]:
        if isinstance(doc_type, str):
            doc_type = DocType(doc_type)
        return list(self.documents.get(doc_type, []))

    def first(self, doc_type: DocType | str) -> Optional[Extraction]:
        docs = self.get(doc_type)
        return docs[0] if docs else None

    def has(self, doc_type: DocType | str) -> bool:
        return bool(self.get(doc_type))


@dataclass
class RuleContext:
    submission_date: date
    checklist_id: str
    checklist_version: str
    reference_currency: str = "EUR"
    fx_rates_to_eur: dict[str, float] = field(default_factory=lambda: {"EUR": 1.0})
    schengen_countries: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

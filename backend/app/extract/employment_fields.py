"""Deterministic employment-letter field recovery from document text.

LLM still extracts first; this only fills nulls from printed cues so one specimen
phrasing does not own the pipeline. Never invents a title.
"""
from __future__ import annotations

import re

# Labeled fields first (works across layouts), then inline “employed as …” cues.
_LABELED = re.compile(
    r"(?im)^\s*(?:"
    r"position|job\s*title|job\s*role|title|designation|role|"
    r"fonction|poste|emploi|qualit[eé]"
    r")\s*[:\-–]\s*(?P<title>[^\n|;]{2,80})"
)

_INLINE = [
    # EN: employed … as <title> since/from …
    re.compile(
        r"(?is)\b(?:employed|works?|serving|appointed)\b.{0,80}?\bas\b\s+"
        r"(?P<title>[A-Za-z][A-Za-z0-9/&\-\s.]{1,60}?)"
        r"(?=\s*(?:since|from|with|,|\.|$|monthly|salary|leave))",
    ),
    # FR: en qualité de / en tant que / comme
    re.compile(
        r"(?is)\b(?:en\s+qualit[eé]\s+de|en\s+tant\s+que|comme)\s+"
        r"(?P<title>[^\n,.;]{2,60}?)"
        r"(?=\s*(?:depuis|à\s+compter|,|\.|$|salaire|cong[eé]))",
    ),
    # Generic: "as <Title Case words>" near employ
    re.compile(
        r"(?is)\bas\s+(?P<title>(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}))"
        r"(?=\s*(?:since|from|,|\.|$))",
    ),
]

_STOP = re.compile(
    r"^\s*(?:our|the|a|an|company|employer|this|his|her|their)\b",
    re.I,
)


def recover_position_from_text(text: str) -> str | None:
    """Return a job title found in letter text, or None if none is clear."""
    if not text or not text.strip():
        return None
    m = _LABELED.search(text)
    if m:
        return _clean_title(m.group("title"))
    for pat in _INLINE:
        m = pat.search(text)
        if m:
            cleaned = _clean_title(m.group("title"))
            if cleaned:
                return cleaned
    return None


def _clean_title(raw: str) -> str | None:
    title = re.sub(r"\s+", " ", (raw or "").strip(" \t-:;,.|/"))
    title = re.sub(r"\s+(since|from|depuis|with|monthly|salary).*$", "", title, flags=re.I)
    title = re.sub(r"^(?:a|an|the|our|leur|un|une)\s+", "", title, flags=re.I)
    if len(title) < 2 or len(title) > 80:
        return None
    if _STOP.match(title):
        return None
    # Reject pure dates / amounts
    if re.fullmatch(r"[\d./\-\s]+", title):
        return None
    return title

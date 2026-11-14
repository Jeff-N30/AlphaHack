"""Deterministic name normalization and matching (never token_set_ratio)."""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

from app.models import Status

_TITLES = frozenset({"MR", "MRS", "MS", "MISS", "DR", "PROF"})
_PARTICLES = frozenset({"AL", "EL"})
# Do not strip AL/EL from these Western given/surnames
_AL_EL_KEEP = frozenset(
    {
        "ALEXANDER",
        "ALEXANDRA",
        "ALBERT",
        "ALFRED",
        "ALVIN",
        "ALAN",
        "ALLEN",
        "ALICE",
        "ALICIA",
        "ALLISON",
        "ELENA",
        "ELIAS",
        "ELIZABETH",
        "ELLA",
        "ELLEN",
        "ELLIOT",
        "ELTON",
    }
)


def normalize_name(raw: str) -> str:
    """Uppercase, strip accents/punct, '/'→space, drop MR/MRS/MS, AL/EL particles."""
    s = unicodedata.normalize("NFKD", raw or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper().replace("/", " ")
    s = re.sub(r"[^A-Z0-9\s-]", " ", s)
    s = s.replace("-", " ")
    tokens: list[str] = []
    for tok in s.split():
        if tok in _TITLES or tok in _PARTICLES:
            continue
        if tok not in _AL_EL_KEEP and len(tok) > 2 and tok[:2] in _PARTICLES and tok[2:].isalpha():
            # ALHAJJ / ELHAJJ glued particle → HAJJ
            tokens.append(tok[2:])
            continue
        tokens.append(tok)
    return " ".join(tokens)


def compare_names(
    reference: str,
    candidate: str,
    *,
    variant_threshold: int = 85,
    fail_below: int = 70,
) -> tuple[Status, float, tuple[str, str]]:
    """Compare names with rapidfuzz token_sort_ratio.

    exact after normalize → PASS
    score >= variant_threshold → NEEDS_HUMAN (near match)
    score >= fail_below → NEEDS_HUMAN
    else → FAIL
    """
    a = normalize_name(reference)
    b = normalize_name(candidate)
    if not a or not b:
        return Status.NEEDS_HUMAN, 0.0, (a, b)
    if a == b:
        return Status.PASS, 100.0, (a, b)
    score = float(fuzz.token_sort_ratio(a, b))
    if score >= 100:
        return Status.PASS, score, (a, b)
    if score >= variant_threshold:
        return Status.NEEDS_HUMAN, score, (a, b)
    if score >= fail_below:
        return Status.NEEDS_HUMAN, score, (a, b)
    return Status.FAIL, score, (a, b)

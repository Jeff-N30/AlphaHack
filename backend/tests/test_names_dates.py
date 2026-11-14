"""Name normalizer + date helpers (PROMPT step 3)."""
from __future__ import annotations

from datetime import date

from app.models import Status
from app.rules.dates import add_months, inclusive_days
from app.rules.names import compare_names, normalize_name


def test_normalize_nassar_karim() -> None:
    assert normalize_name("NASSAR/KARIM MR") == "NASSAR KARIM"
    assert normalize_name("KARIM NASSAR") == "KARIM NASSAR"


def test_compare_exact_pass() -> None:
    st, score, _ = compare_names("NASSAR/KARIM MR", "KARIM NASSAR")
    assert st == Status.PASS
    assert score == 100.0


def test_compare_mohamad_variant_needs_human() -> None:
    st, score, _ = compare_names("MOHAMMAD AL HAJJ", "AL HAJJ / MOHAMAD")
    assert st == Status.NEEDS_HUMAN
    assert score >= 85


def test_compare_el_al_pass() -> None:
    st, score, _ = compare_names("EL HAJJ", "AL-HAJJ")
    assert st == Status.PASS
    assert score == 100.0


def test_compare_partial_not_pass() -> None:
    st, _, _ = compare_names("KARIM", "KARIM NASSAR")
    assert st != Status.PASS


def test_compare_unrelated_fail() -> None:
    st, score, _ = compare_names("GEORGES HADDAD", "RANA SALEH")
    assert st == Status.FAIL
    assert score < 70


def test_add_months() -> None:
    assert add_months(date(2027, 1, 5), 3) == date(2027, 4, 5)


def test_inclusive_days() -> None:
    assert inclusive_days(date(2026, 12, 18), date(2026, 12, 28)) == 11

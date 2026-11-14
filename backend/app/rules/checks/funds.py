from __future__ import annotations

from typing import Any

from app.models import DocType
from app.rules.checks._util import as_date, ev, fail, needs_human, ok, stay_days
from app.rules.context import Facts, RuleContext
from app.rules.dates import add_months
from app.rules.registry import register


@register("statement_window")
def statement_window(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    bank = facts.first(DocType.bank_statement)
    assert bank is not None
    months = int(params.get("months", 6))
    max_age = int(params.get("max_age_days", 31))
    start, end = as_date(bank.period_start), as_date(bank.period_end)
    issued = as_date(bank.issue_date)
    # period_start <= period_end - months + 1 day
    threshold = add_months(end, -months)
    # add 1 day: May 1 <= (Oct 31 - 6m) + 1d → Apr 30 + 1 = May 1
    from datetime import timedelta

    threshold = threshold + timedelta(days=1)
    age = (ctx.submission_date - issued).days
    evidence = [
        ev("bank_statement", "period_start", start),
        ev("bank_statement", "period_end", end),
        ev("bank_statement", "issue_date", issued),
        ev("bank_statement", "age_days", age),
    ]
    if start <= threshold and age <= max_age:
        return ok("BANK.WINDOW", f"Window {months}m and age {age}d OK", evidence=evidence)
    reasons = []
    if start > threshold:
        reasons.append(f"period too short (start {start} > {threshold})")
    if age > max_age:
        reasons.append(f"statement too old ({age}d > {max_age})")
    return fail("BANK.WINDOW", "; ".join(reasons), evidence=evidence)


@register("llm_bool")
def llm_bool(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    """mode=llm_flag: True → PASS; False/missing → NEEDS_HUMAN (never FAIL)."""
    field = params.get("field") or ""
    # field like bank_statement.has_bank_stamp
    parts = field.split(".")
    if len(parts) != 2:
        return needs_human("LLM_BOOL", f"Bad field path {field}")
    doc = facts.first(DocType(parts[0]))
    assert doc is not None
    val = getattr(doc, parts[1], None)
    evidence = [ev(parts[0], parts[1], val)]
    if val is True:
        return ok("LLM_BOOL", f"{field}=true", evidence=evidence)
    return needs_human("LLM_BOOL", f"{field} not confirmed", evidence=evidence)


@register("sufficient_funds")
def sufficient_funds(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    bank = facts.first(DocType.bank_statement)
    assert bank is not None
    days = stay_days(facts)
    if days is None:
        return needs_human("BANK.SUFFICIENT_FUNDS", "Cannot compute stay length")
    rates = params.get("eur_per_day") or {}
    has_hotel = facts.has(DocType.hotel_booking)
    # attestation not in demo facts
    per_day = float(rates.get("hotel" if has_hotel else "no_proof", 65 if has_hotel else 120))
    need = per_day * days
    ccy = str(bank.account_currency).upper()
    fx = ctx.fx_rates_to_eur
    if ccy not in fx:
        return needs_human(
            "BANK.SUFFICIENT_FUNDS",
            f"Unknown currency {ccy} — no FX guess",
            evidence=[ev("bank_statement", "account_currency", ccy)],
        )
    eur = float(bank.closing_balance) * float(fx[ccy])
    evidence = [
        ev("bank_statement", "closing_balance", f"{bank.closing_balance} {ccy}"),
        ev("bank_statement", "closing_eur", round(eur, 2)),
        ev("flight_booking", "stay_days", days),
        ev("funds", "required_eur", round(need, 2)),
    ]
    if eur + 1e-6 >= need:
        return ok("BANK.SUFFICIENT_FUNDS", f"EUR {eur:.2f} >= {need:.2f}", evidence=evidence)
    return fail(
        "BANK.SUFFICIENT_FUNDS",
        f"EUR {eur:.2f} below required {need:.2f} ({per_day}/day × {days}d)",
        evidence=evidence,
    )


@register("large_recent_deposit")
def large_recent_deposit(facts: Facts, params: dict[str, Any], ctx: RuleContext):
    bank = facts.first(DocType.bank_statement)
    assert bank is not None
    window = int(params.get("window_days", 30))
    pct = float(params.get("pct_of_closing_balance", 50))
    end = as_date(bank.period_end)
    closing = float(bank.closing_balance)
    threshold = closing * (pct / 100.0)
    from datetime import timedelta

    start_w = end - timedelta(days=window)
    hits = []
    for t in bank.transactions or []:
        td = as_date(t.date)
        if td >= start_w and td <= end and float(t.amount) >= threshold and float(t.amount) > 0:
            hits.append(t)
    evidence = [ev("bank_statement", "closing_balance", closing)]
    if hits:
        t = hits[0]
        evidence.append(ev("bank_statement", "large_deposit", f"{t.amount} on {t.date}"))
        return needs_human(
            "BANK.LARGE_RECENT_DEPOSIT",
            f"Large deposit {t.amount} within {window}d (≥{pct}% of closing)",
            evidence=evidence,
        )
    return ok("BANK.LARGE_RECENT_DEPOSIT", "No large recent deposit", evidence=evidence)

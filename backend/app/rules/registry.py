"""Check function registry: name → callable(facts, params, ctx) -> CheckResult."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.models import CheckResult
from app.rules.context import Facts, RuleContext

CheckFn = Callable[[Facts, dict[str, Any], RuleContext], CheckResult]

REGISTRY: dict[str, CheckFn] = {}


def register(name: str):
    def deco(fn: CheckFn) -> CheckFn:
        REGISTRY[name] = fn
        return fn

    return deco


def get_check(name: str) -> CheckFn:
    if name not in REGISTRY:
        raise KeyError(f"unknown check: {name}")
    return REGISTRY[name]


def ensure_loaded() -> None:
    """Import check modules so @register runs."""
    import app.rules.checks  # noqa: F401

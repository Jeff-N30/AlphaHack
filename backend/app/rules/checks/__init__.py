"""Import all check modules so @register populates REGISTRY."""
from app.rules.checks import (  # noqa: F401
    civil,
    employment,
    funds,
    identity,
    insurance,
    passport,
    presence,
    suspicion,
    trip,
)

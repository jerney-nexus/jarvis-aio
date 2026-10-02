"""Log-only bridge: live authorization gate ↔ kernel.authority (hardening H1).

The actuator path already runs every protected action through `policy.confirm_gate`
(the live, authoritative gate). This bridge computes what the Phase 4 authority
**engine** would have decided for the same action and records whether the two
agree — **log-only, never changing behaviour** — so enforcement can be flipped
from parity to deny only once the engine matches the gate on real traffic.

The running tally lives in `hass.data[DOMAIN]["_authority_parity"]` and is
exposed via `parity_summary()` for diagnostics. Entirely best-effort: any failure
here is swallowed and the actuator path is untouched.
"""
from __future__ import annotations

import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_PARITY_KEY = "_authority_parity"


def _parity(hass):
    from .kernel import AuthorityParity
    store = hass.data.setdefault(DOMAIN, {})
    p = store.get(_PARITY_KEY)
    if p is None:
        p = AuthorityParity()
        store[_PARITY_KEY] = p
    return p


def record_control_parity(hass, domain: str, service: str, *, allowed: bool,
                          identity=None, confidence: float = 1.0):
    """Record the authority engine's decision for ``domain.service`` against the
    live gate's ``allowed`` outcome. LOG-ONLY. Returns the engine decision (or
    None on failure)."""
    try:
        from .kernel import AuthorityRequest, authority as A, authorize
        cap = f"{domain}.{service}"
        decision = authorize(AuthorityRequest(
            capability=cap, identity=identity, confidence=confidence))
        # Map the gate result into the engine's vocabulary: the gate either lets
        # the action proceed (ALLOW) or holds it for confirmation (CONFIRM).
        actual = A.ALLOW if allowed else A.CONFIRM
        if not _parity(hass).record(decision, actual):
            _LOGGER.debug(
                "authority parity mismatch: %s engine=%s actual=%s (%s)",
                cap, decision.decision, actual, decision.reason)
        return decision
    except Exception as exc:  # never affect the actuator path
        _LOGGER.debug("authority parity record failed: %s", exc)
        return None


def parity_summary(hass) -> dict:
    """The current engine-vs-gate agreement tally (for diagnostics/panel)."""
    try:
        return _parity(hass).summary()
    except Exception:
        return {}

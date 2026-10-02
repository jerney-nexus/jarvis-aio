"""Authority / capability engine (kernel Phase 4, docs/KERNEL_PLAN.md).

The safety keystone: one place that answers "may this capability be exercised,
by this actor, in this context?" with **allow / deny / confirm**. Today that
judgement is spread across `voice_confirm` (is this action protected?),
`output_gate` (may we interrupt?) and the autonomy grants; this module gives them
a single, testable check to delegate to, and a capability-**token** model so a
delegated sub-agent (FRIDAY / HOMER) can never exercise more than it was granted.

Design invariants (from the kernel plan):
  * **No escalation by delegation.** A token-bearing actor is denied any
    capability its token does not grant, and a derived token can only *narrow*
    its parent's capabilities, never widen them.
  * **Security-sensitive capabilities require explicit authority** — they resolve
    to CONFIRM (or DENY without an identified requester), never a silent allow.
  * **Fail closed.** Any error in a policy resolves to DENY.

Pure: no Home Assistant import, no I/O — trivially testable. **Phase 4 ships this
additively, to run log-only / allow-as-before first**: callers compute the
engine's decision alongside their existing behaviour and record parity before any
actuator is actually routed through it.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, Iterable, Optional

_LOGGER = logging.getLogger(__name__)

# ── decisions ─────────────────────────────────────────────────────────────────
ALLOW = "allow"
DENY = "deny"
CONFIRM = "confirm"  # permitted only with explicit (human) confirmation

# ── capability sensitivity tiers ──────────────────────────────────────────────
SAFE = "safe"            # read / announce — no special authority
SENSITIVE = "sensitive"  # actuation that matters (lights, covers, modes, lock)
SECURITY = "security"    # safety/security-critical (unlock, disarm, lockdown off)

# Capability → sensitivity. Keyed by exact capability or a "domain." prefix; the
# longest matching key wins. Unknown capabilities are treated as SENSITIVE
# (conservative: an unrecognised actuation is never silently "safe").
_SENSITIVITY: Dict[str, str] = {
    "announce": SAFE,
    "read": SAFE,
    "query": SAFE,
    "camera.analyze": SAFE,
    "media_player": SAFE,
    "light": SENSITIVE,
    "switch": SENSITIVE,
    "fan": SENSITIVE,
    "climate": SENSITIVE,
    "cover": SENSITIVE,
    "scene": SENSITIVE,
    "script": SENSITIVE,
    "mode": SENSITIVE,
    "lock.lock": SENSITIVE,
    "lock.unlock": SECURITY,
    "alarm_control_panel.alarm_disarm": SECURITY,
    "alarm.disarm": SECURITY,
    "lockdown.clear": SECURITY,
    "intrusion.dismiss": SECURITY,
    "delete": SECURITY,
}


def sensitivity(capability: str) -> str:
    """The sensitivity tier for a capability (longest-prefix match; unknown →
    SENSITIVE so an unrecognised actuation is never treated as safe)."""
    cap = (capability or "").strip()
    best_key = ""
    best_sev = None
    for key, sev in _SENSITIVITY.items():
        if cap == key or cap.startswith(key + "."):
            if len(key) > len(best_key):
                best_key, best_sev = key, sev
    return best_sev if best_sev is not None else SENSITIVE


@dataclass(frozen=True)
class CapabilityToken:
    """A grant a (sub-)agent carries. ``*`` means "all capabilities" (the root)."""

    holder: str
    capabilities: FrozenSet[str] = frozenset()
    issuer: Optional[str] = None
    scope: Optional[str] = None

    def grants(self, capability: str) -> bool:
        return "*" in self.capabilities or capability in self.capabilities

    def derive(self, holder: str, capabilities: Iterable[str],
               *, scope: Optional[str] = None) -> "CapabilityToken":
        """A child token for ``holder``. Its capabilities are the requested set
        **intersected** with this token's — delegation narrows, never escalates.
        """
        requested = frozenset(capabilities)
        granted = requested if "*" in self.capabilities else (requested & self.capabilities)
        return CapabilityToken(holder=holder, capabilities=granted,
                               issuer=self.holder, scope=scope or self.scope)


@dataclass(frozen=True)
class AuthorityRequest:
    capability: str
    identity: Optional[str] = None      # human on whose behalf / who is present
    actor: str = "jarvis"               # agent making the request
    token: Optional[CapabilityToken] = None
    context: dict = field(default_factory=dict)
    situation: Optional[str] = None
    confidence: float = 1.0
    intent: Optional[str] = None
    scope: Optional[str] = None
    ts: float = field(default_factory=time.time)


@dataclass(frozen=True)
class AuthorityDecision:
    decision: str
    reason: str
    capability: str
    sensitivity: str

    @property
    def allowed(self) -> bool:
        return self.decision == ALLOW

    @property
    def denied(self) -> bool:
        return self.decision == DENY

    @property
    def needs_confirmation(self) -> bool:
        return self.decision == CONFIRM


Policy = Callable[[AuthorityRequest], AuthorityDecision]


def default_policy(req: AuthorityRequest) -> AuthorityDecision:
    """The baseline capability policy (see module invariants)."""
    cap = req.capability
    sev = sensitivity(cap)

    # 1. Delegation can't escalate: a token-bearing actor must hold the capability.
    if req.token is not None and not req.token.grants(cap):
        return AuthorityDecision(
            DENY, f"{req.actor}'s token does not grant '{cap}'", cap, sev)

    # 2. Security-sensitive capabilities require explicit authority.
    if sev == SECURITY:
        if not req.identity:
            return AuthorityDecision(
                DENY, "security-sensitive capability requires an identified requester",
                cap, sev)
        return AuthorityDecision(
            CONFIRM, "security-sensitive capability requires explicit confirmation",
            cap, sev)

    # 3. Sensitive actuation: confirm when unsure, else allow.
    if sev == SENSITIVE:
        if req.confidence < 0.5:
            return AuthorityDecision(
                CONFIRM, "low confidence on a sensitive action", cap, sev)
        return AuthorityDecision(ALLOW, "sensitive action within policy", cap, sev)

    # 4. Safe capabilities.
    return AuthorityDecision(ALLOW, "safe capability", cap, sev)


def authorize(request: AuthorityRequest, *, policy: Optional[Policy] = None) -> AuthorityDecision:
    """Resolve an authority request to ALLOW / DENY / CONFIRM. Fails closed (DENY)
    if the policy raises — this is the safety keystone, so an error is never an
    accidental allow."""
    policy = policy or default_policy
    try:
        return policy(request)
    except Exception as exc:  # fail closed
        _LOGGER.debug("authority: policy error, denying: %s", exc)
        return AuthorityDecision(
            DENY, f"policy error: {exc}", request.capability,
            sensitivity(request.capability))

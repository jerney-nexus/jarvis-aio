"""Causal learning (kernel Phase 7, docs/KERNEL_PLAN.md).

Closes the loop the audit calls for: observation → hypothesis → action → outcome →
**causal confidence**. Today `pattern_analyzer`, `rca` and `feedback` each learn
slices of this; this primitive gives them a shared, principled measure of *whether
a cause actually drives an effect*, not just that they co-occur.

Each hypothesis "C → E" accumulates a 2×2 contingency (cause present/absent ×
effect present/absent) and scores causal strength with **ΔP** — the causal
contrast ``P(E|C) − P(E|¬C)`` — which, unlike raw co-occurrence, discounts an
effect that happens just as often without the cause. Confidence shrinks ΔP toward
0 when the sample is small, so a single lucky trial never reads as certainty.

Pure: no Home Assistant import, no I/O — a `CausalHypothesis` is immutable and
``observed()`` returns a new one; the `CausalModel` is a thin in-memory tally.
Phase 7 ships it additively; the learning modules adopt it later.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

# Shrinkage constant: ΔP is scaled by trials / (trials + _PRIOR) so a handful of
# observations can't assert strong causation. ~5 balanced trials → half strength.
_PRIOR = 5.0


@dataclass(frozen=True)
class CausalHypothesis:
    """A hypothesis that ``cause`` drives ``effect``, with its 2×2 evidence."""

    cause: str
    effect: str
    n11: int = 0   # cause present, effect present
    n10: int = 0   # cause present, effect absent
    n01: int = 0   # cause absent,  effect present
    n00: int = 0   # cause absent,  effect absent

    def observed(self, cause_present: bool, effect_present: bool) -> "CausalHypothesis":
        """Return a copy with one more trial tallied into the contingency table."""
        if cause_present and effect_present:
            return replace(self, n11=self.n11 + 1)
        if cause_present and not effect_present:
            return replace(self, n10=self.n10 + 1)
        if not cause_present and effect_present:
            return replace(self, n01=self.n01 + 1)
        return replace(self, n00=self.n00 + 1)

    @property
    def trials(self) -> int:
        return self.n11 + self.n10 + self.n01 + self.n00

    @property
    def p_effect_given_cause(self) -> Optional[float]:
        d = self.n11 + self.n10
        return (self.n11 / d) if d else None

    @property
    def p_effect_given_not_cause(self) -> Optional[float]:
        d = self.n01 + self.n00
        return (self.n01 / d) if d else None

    @property
    def delta_p(self) -> float:
        """Causal contrast P(E|C) − P(E|¬C) in [-1, 1]. 0 when a side is unseen."""
        pc = self.p_effect_given_cause
        pnc = self.p_effect_given_not_cause
        if pc is None or pnc is None:
            return 0.0
        return pc - pnc

    @property
    def confidence(self) -> float:
        """Signed causal confidence in (-1, 1): ΔP shrunk by sample size.

        Needs observations on BOTH sides of the cause — ΔP is undefined otherwise,
        so confidence is 0 until the cause has been seen present and absent.
        """
        if self.p_effect_given_cause is None or self.p_effect_given_not_cause is None:
            return 0.0
        return self.delta_p * (self.trials / (self.trials + _PRIOR))

    @property
    def direction(self) -> str:
        c = self.confidence
        if c > 0.05:
            return "causes"
        if c < -0.05:
            return "prevents"
        return "none"


class CausalModel:
    """An in-memory tally of causal hypotheses keyed by (cause, effect)."""

    def __init__(self) -> None:
        self._h: Dict[Tuple[str, str], CausalHypothesis] = {}

    def observe(self, cause: str, effect: str, *, cause_present: bool,
                effect_present: bool) -> CausalHypothesis:
        """Record one trial for the ``cause → effect`` hypothesis."""
        key = (cause, effect)
        h = self._h.get(key) or CausalHypothesis(cause=cause, effect=effect)
        h = h.observed(cause_present, effect_present)
        self._h[key] = h
        return h

    def get(self, cause: str, effect: str) -> Optional[CausalHypothesis]:
        return self._h.get((cause, effect))

    def confidence(self, cause: str, effect: str) -> float:
        h = self._h.get((cause, effect))
        return h.confidence if h else 0.0

    def ranked(self, *, min_abs_confidence: float = 0.0) -> List[CausalHypothesis]:
        """Hypotheses by strongest absolute causal confidence first."""
        out = [h for h in self._h.values() if abs(h.confidence) >= min_abs_confidence]
        return sorted(out, key=lambda h: abs(h.confidence), reverse=True)

# JARVIS Constitution

> The invariants JARVIS must never violate, and the ordering it resolves conflicts
> by. This is a short, deliberately stable document: the kernel migration
> (`docs/KERNEL_PLAN.md`) and the adoption matrix (`KERNEL_ADOPTION.md`) describe
> *how* the system is being built; this describes *what must stay true* no matter
> how it is built. If an implementation ever contradicts a rule here, the
> implementation is wrong.

## 1. Precedence ladder

When two concerns compete, the higher tier wins. This ladder is encoded once, in
`custom_components/jarvis/kernel/priority.py`, so attention, authority and the
planner resolve conflicts the same way instead of with ad-hoc `if urgent` checks.

| Rank | Tier | Examples |
| --- | --- | --- |
| 1 (highest) | **life safety** | smoke/CO, medical, fire, a person in danger |
| 2 | **security** | intrusion, unexpected unlock, perimeter breach |
| 3 | **property** | water leak, freeze, appliance fault, left-on hazard |
| 4 | **household** | routines, schedules, comfort automations |
| 5 | **convenience** | nice-to-have automations, proactive suggestions |
| 6 (lowest) | **personality** | tone, banter, flavour, voice persona |

**Invariant P1 — personality never overrides safety.** No stylistic,
conversational, or persona concern may suppress, delay, or soften a life-safety or
security action. `priority.may_override(PERSONALITY, <safety tier>)` is `False` by
construction, and no code path may route around it.

**Invariant P2 — a lower tier never overrides a strictly higher one.** Equal tiers
may arbitrate among themselves; a lower tier may not win against a higher one.

## 2. Authority

**Invariant A1 — authority is log-only until explicitly promoted.** The capability
engine (`kernel/authority.py`) runs in parity through `authority_bridge`: for every
control action it records what it *would* have decided versus what the legacy
confirm-gate actually did. It must not deny or alter a live action while in parity.

**Invariant A2 — enforcement is owner-gated.** Flipping authority from parity to
`enforce` on the live home system is a deliberate, human-approved step, taken only
after parity holds on real traffic. No automated process, prompt, or external input
may flip it. (This is why `KERNEL_ADOPTION.md` shows no primitive at `enforce`.)

**Invariant A3 — capabilities expire and can be revoked.** Tokens carry an optional
expiry and a revocation set; an expired or revoked token is denied even if its scope
would otherwise allow the action. Derived (child) tokens never outlive their parent.

## 3. Safety defaults

**Invariant S1 — fail safe, not open.** When a safety-relevant input is unavailable
or unknown (e.g. the alarm panel is `unavailable` at startup), JARVIS holds the
safe state rather than assuming all-clear. Only a positive, confirmed signal lifts a
protective hold.

**Invariant S2 — no silent control.** Every control action JARVIS takes is
attributable: it records who/what requested it, the decision, and the outcome, so
the ledger can reconstruct what happened. A control path that cannot be recorded is
a bug.

**Invariant S3 — degrade, don't crash.** A non-critical subsystem failing (a
monitor, an optional sensor, a model provider) must degrade to a logged non-fatal
warning, never take down the integration or a safety path.

## 4. Change discipline

**Invariant C1 — additive first.** New kernel capability lands pure and
unit-tested, then shadow, then parity, before it can influence a live decision. No
primitive jumps straight to authoritative. The adoption matrix
(`KERNEL_ADOPTION.md`) must reflect reality; `scripts/kernel_adoption.py --check`
guards against drift.

**Invariant C2 — the invariants above outrank convenience.** If a feature can only
ship by weakening a rule in this document, it does not ship until the rule is
deliberately, explicitly revised here first.

---

*These invariants are intentionally few. Add one only when it is genuinely
inviolable — the value of this document is that every line is load-bearing.*

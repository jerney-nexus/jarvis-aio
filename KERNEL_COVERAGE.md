# Behavioral kernel-coverage matrix

> Generated signal, kept honest by `scripts/kernel_coverage.py`. Run it for the
> live table, `--markdown` for the block below, `--check` in CI. **Do not inflate
> the declared stages to make the number look better** — raise a cell only when
> the real execution path reaches that stage, and update its evidence with it.

`KERNEL_ADOPTION.md` answers *"does a live module reference a kernel primitive?"*
This answers the sharper question the external MCU audit raised:

> **What fraction of behaviour-bearing paths actually pass through the kernel
> contract** — Event → WorldModel → Situation → Authority → Plan → Verify →
> Outcome?

A module can `from .kernel import authorize` and still have actuators that bypass
Authority, so *reference* coverage overstates reality. This matrix tracks, per
behaviour-bearing path, how far each pipeline contract is actually wired
(`· none  ◐ shadow  ◑ parity  ● full`), and the script verifies every non-`none`
claim against evidence that must exist in the path's source — the matrix cannot
drift into fiction.

## Current matrix

<!-- BEGIN kernel-coverage (python3 scripts/kernel_coverage.py --markdown) -->
| Path | event | world_model | situation | authority | plan | verify | outcome |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `control_device` | ◑ | ◑ | · | ◑ | ◐ | ● | ● |
| `bulk_control` | · | · | · | · | · | · | · |
| `execute_plan` | · | · | · | · | · | · | · |
| `intrusion` | · | · | ◑ | · | · | · | · |
| `goals` | · | · | · | · | · | · | · |
| `proactive` | · | · | · | · | · | · | · |
| `friday` | · | · | · | · | · | · | · |
| `homer` | · | · | · | · | · | · | · |

**Kernel coverage: 8.9%** (· none ◐ shadow ◑ parity ● full)
<!-- END kernel-coverage -->

**8.9% is the honest number today** — most paths are still legacy, exactly the
state the audit flagged ("the kernel is not yet the operating system of JARVIS").
This figure is the one to move: *"X% of behaviour-bearing paths are
kernel-authoritative"* is far more meaningful than *"Kernel Phase N completed."*

**Phase A (the third MCU audit's one actionable recommendation)** is underway:
make `control_device` a complete end-to-end kernel path, then template every
other consequential actuator onto it. It ships one contract at a time, each its
own release, with authority staying **log-only / owner-gated** — the spine is
built structurally first; the enforce flip is a separate, explicit decision.

## What the cells mean today

- **`control_device`** — the Phase A golden path in progress. **WorldModel** at
  parity (8.30.0): its pre-action context snapshot is read through the
  `WorldModel` facade, the canonical context authority, rather than a bare
  `states.get` (parity, not full, because the post-action read-back still reads
  raw HA state). Authority at **parity** (`authority_bridge`, log-only) and a
  real verify-after-act (`_verify_control`, `●`). **Outcome** at full (8.31.0):
  the verify step produces the canonical `kernel.actuator.ActuatorOutcome`
  (requested → executed → observed → **verified / mismatch / failed**) as the
  path's real outcome record — the audit's point 18, *"the service returned
  success" is not "the world reached the expected state"*. **Event** at parity
  (8.32.0): the actuation is published as a canonical `JarvisEvent`
  (`from_actuation`) onto the kernel event bus, which the ledger records —
  parity, not full, because it enters the stream but no cognitive consumer
  reacts to it yet (the audit's item #8, the event bus as nervous system).
  **Plan** at shadow (8.33.0): the actuation is expressed as a canonical
  one-step `kernel.plan.Plan` (preconditions → act → postconditions, with an
  idempotency key) and logged — shadow, because `execute_plan` is synchronous
  while HA actuation is `await`-ed, so the plan does not yet *own* execution.
  The farthest-along path.
- **`intrusion`** — mirrors its lifecycle into the kernel **Situation** state
  machine at parity.
- **`bulk_control` / `execute_plan`** — still the legacy in-agent paths (bulk uses
  only the `policy` confirmation gate; execute_plan does not use `kernel.plan`).
- **`goals` / `proactive` / `friday` / `homer`** — not yet wired to any kernel
  contract.

> **Actuator contract (8.26.0 → 8.31.0):** `control_device` constructs a
> canonical `kernel.actuator.ActuatorRequest` (who/intent/target/correlation/
> idempotency/**expected_outcome**), and the verify step now produces the
> matching `ActuatorOutcome` (requested → executed → observed → verified). That
> is why the **outcome** cell above is `●` and `KERNEL_ADOPTION.md` lists
> `actuator` at **parity** (8.31.0), up from shadow. The actuation also now
> publishes a canonical `JarvisEvent` (8.32.0, `event` ◑) and is expressed as a
> one-step `kernel.plan.Plan` (8.33.0, `plan` ◐). Still ahead: routing
> *execution itself* through the plan/actuator contract (so the kernel, not the
> legacy branch, performs the `await`ed service call) — the step that raises
> `plan` from shadow to full and that an async plan driver unblocks.

## How to raise the number

The matrix is driven by `_PATHS` in `scripts/kernel_coverage.py`. To record real
progress:

1. Wire the path onto the kernel contract (e.g. route `control_device` through the
   `ActuatorRequest` contract, or have a path publish a `JarvisEvent`).
2. Raise that cell's `stage` in `_PATHS` and set `evidence` to a symbol that must
   appear in the path's source.
3. `python3 scripts/kernel_coverage.py --check` (CI runs it) — fails if a declared
   stage has no evidence.
4. Regenerate the block above with `--markdown`.

No primitive is at `enforce` and authority stays **log-only / owner-gated**; this
matrix measures wiring, not a licence to flip enforcement.

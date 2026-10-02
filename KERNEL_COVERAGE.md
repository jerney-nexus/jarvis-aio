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
| `control_device` | · | · | · | ◑ | · | ● | · |
| `bulk_control` | · | · | · | · | · | · | · |
| `execute_plan` | · | · | · | · | · | · | · |
| `intrusion` | · | · | ◑ | · | · | · | · |
| `goals` | · | · | · | · | · | · | · |
| `proactive` | · | · | · | · | · | · | · |
| `friday` | · | · | · | · | · | · | · |
| `homer` | · | · | · | · | · | · | · |

**Kernel coverage: 4.2%** (· none ◐ shadow ◑ parity ● full)
<!-- END kernel-coverage -->

**4.2% is the honest number today** — most paths are still legacy, exactly the
state the audit flagged ("the kernel is not yet the operating system of JARVIS").
This figure is the one to move: *"X% of behaviour-bearing paths are
kernel-authoritative"* is far more meaningful than *"Kernel Phase N completed."*

## What the cells mean today

- **`control_device`** — Authority at **parity** (`authority_bridge`, log-only)
  and a real verify-after-act (`_verify_control`, `●`). The farthest-along path.
- **`intrusion`** — mirrors its lifecycle into the kernel **Situation** state
  machine at parity.
- **`bulk_control` / `execute_plan`** — still the legacy in-agent paths (bulk uses
  only the `policy` confirmation gate; execute_plan does not use `kernel.plan`).
- **`goals` / `proactive` / `friday` / `homer`** — not yet wired to any kernel
  contract.

> **Actuator contract (8.26.0):** `control_device` now constructs a canonical
> `kernel.actuator.ActuatorRequest` (who/intent/target/correlation/idempotency)
> and logs it in **shadow** — a step toward the universal execution contract. It
> is recorded in `KERNEL_ADOPTION.md` (`actuator` = shadow), not here, because
> shadow-*logging* the request object does not yet make the path *pass through* a
> pipeline contract. These cells rise only when execution actually routes through
> the contract (Authority → preconditions → actuator → postconditions → outcome).

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

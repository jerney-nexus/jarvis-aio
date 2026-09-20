"""Turn camera perception into learnable semantic events.

The camera stack already emits a ``jarvis_camera_event`` on the HA bus for every
Frigate/Nest object detection — but nothing *learns* from it: it was only a
focus hint for the command-center panel. Meanwhile the raw ``image.*`` snapshot
entities that back those cameras change tens of thousands of times with opaque,
unlearnable state, so feeding them to the pattern miner just drowns real
routines (see issue-driven guidance in ``entity_filter`` / the docs).

This module bridges the gap: it takes the *semantic* camera signal — "a person
was seen at the front door", "a vehicle in the driveway", "a package at the
porch" — normalises it, collapses repeat detections of the same thing in the
same place into one event per window, and records it into the **same**
``state_changes`` learning store the pattern analyzer already mines. The result:

  * A synthetic entity ``camera_event.<location>`` whose state is the semantic
    label (``person`` / ``vehicle`` / ``animal`` / ``package`` / ``activity``),
    stamped with area, hour and day-of-week like any other learnable change.
  * The temporal miner can now learn "front_door sees a person ~17:40 on
    weekdays"; the sequence miner can learn "driveway sees a vehicle → the
    garage opens shortly after" and suggest that automation — camera perception
    as a first-class trigger. Camera events are never proposed as *actions*
    (``pattern_analyzer._action_for`` returns nothing for them), which is
    correct: you act on what a camera sees, you don't actuate the camera.

Design constraints:
  * **Semantic, not raw.** Only classified detections become events; opaque
    snapshot churn never does. This is what keeps the signal learnable.
  * **De-duped.** At most one learnable event per (location, label) per window
    (default 5 min), so a camera firing "person" every two seconds collapses to
    one meaningful "a person was here around then".
  * **Reuses the pipeline.** Recording goes through the running Cognitive Core's
    ``state_logger`` with ``force_include=True``; no new tables, no new miner.
  * **Never raises.** Every reader/writer is guarded; a bad event is dropped.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

_LOGGER = logging.getLogger(__name__)

# Raw detector label → normalised semantic label. Generic motion/object still
# yields a coarse "activity" so motion-only sources (e.g. Nest) contribute a
# location+time signal; a truly empty label is skipped.
_LABEL_MAP = {
    # Frigate/Nest object classes
    "person": "person", "people": "person", "face": "person",
    "known_resident": "person", "resident": "person",
    "car": "vehicle", "truck": "vehicle", "bus": "vehicle",
    "motorcycle": "vehicle", "bicycle": "vehicle", "vehicle": "vehicle",
    "dog": "animal", "cat": "animal", "bird": "animal", "animal": "animal",
    "package": "package", "parcel": "package", "mail": "package",
    "delivery": "package",
    "motion": "activity", "object": "activity", "movement": "activity",
}

# Vision-analysis categories that mean "nothing happened" — never recorded, so a
# quiet scene doesn't create a spurious learnable event.
_SKIP_LABELS = {"empty", "none", "nothing", "clear", "other", "unknown", "quiet"}

# One learnable event per (location, label) per this many seconds. Collapses a
# burst of identical detections into a single "this happened around then".
DEDUP_WINDOW_S = 300.0


def normalize_label(raw: object) -> Optional[str]:
    """Map a detector label to a semantic class, or None to skip.

    Known object classes collapse to person/vehicle/animal/package; generic
    motion/object become "activity"; empty/unknown is skipped."""
    s = str(raw or "").strip().lower()
    if not s or s in _SKIP_LABELS:
        return None
    return _LABEL_MAP.get(s, "activity")


def _slug(text: str) -> str:
    """Filesystem-free slug for a synthetic entity object id."""
    out = []
    for ch in str(text or "").strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -/._":
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "unknown"


def synthetic_entity_id(location: str) -> str:
    """``camera_event.<location-slug>`` — the learnable entity for a place."""
    return f"camera_event.{_slug(location)}"


class _Deduper:
    """Per-key time gate: True at most once per ``window`` seconds per key."""

    def __init__(self, window_s: float = DEDUP_WINDOW_S) -> None:
        self.window = float(window_s)
        self._seen: dict = {}

    def should_record(self, key, now: float) -> bool:
        last = self._seen.get(key)
        if last is None or (now - last) >= self.window:
            self._seen[key] = now
            # Opportunistic prune so the map can't grow unbounded.
            if len(self._seen) > 2048:
                cutoff = now - self.window
                self._seen = {k: t for k, t in self._seen.items() if t >= cutoff}
            return True
        return False


_DEDUPER = _Deduper()


def _camera_area(hass, entity_id: str) -> str:
    """The HA area_id for a camera entity, or '' — via entity then device."""
    try:
        from homeassistant.helpers import entity_registry as er, device_registry as dr
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            return ""
        if entry.area_id:
            return entry.area_id
        if entry.device_id:
            dev = dr.async_get(hass).async_get(entry.device_id)
            return (dev.area_id or "") if dev else ""
    except Exception:
        return ""
    return ""


def record_camera_event(hass, *, camera_entity: str, label: object,
                        source: str = "", person: Optional[str] = None,
                        now: Optional[float] = None) -> bool:
    """Normalise, de-dup, and record one semantic camera detection as a
    learnable ``state_changes`` row. Returns True if a row was written.

    ``camera_entity`` is the ``camera.*`` (or other) entity the detection came
    from; its HA area names the synthetic ``camera_event.<area>`` entity when
    available, else a slug of the camera id. Never raises."""
    try:
        norm = normalize_label(label)
        if not norm:
            return False
        area_id = _camera_area(hass, camera_entity) if camera_entity else ""
        location = area_id or _slug((camera_entity or "").split(".", 1)[-1])
        entity_id = synthetic_entity_id(location)
        now_epoch = time.time() if now is None else float(now)
        if not _DEDUPER.should_record((entity_id, norm), now_epoch):
            return False

        from . import cognitive_core
        core = getattr(cognitive_core, "_CORE", None)
        logger = getattr(core, "state_logger", None) if core else None
        if not core or not getattr(core, "running", False) or logger is None:
            return False

        logger.log_state_change(
            entity_id, "", norm,
            area_id=area_id,
            triggered_by="camera:" + (str(source) or "vision"),
            person=str(person) if person else "unknown",
            person_confidence=0.0,
            force_include=True,
        )
        _LOGGER.debug("camera_learning: recorded %s -> %s (area=%s, src=%s)",
                      entity_id, norm, area_id or "?", source)
        return True
    except Exception:  # noqa: BLE001 - learning must never break perception
        _LOGGER.debug("camera_learning: record failed", exc_info=True)
        return False


def on_camera_event(hass, event) -> None:
    """HA bus handler for ``jarvis_camera_event`` (fired by the camera stack for
    Frigate/Nest detections). Turns it into a learnable semantic event."""
    try:
        data = getattr(event, "data", {}) or {}
        record_camera_event(
            hass,
            camera_entity=str(data.get("entity_id") or ""),
            label=data.get("label"),
            source=str(data.get("source") or ""),
        )
    except Exception:  # noqa: BLE001
        _LOGGER.debug("camera_learning: on_camera_event failed", exc_info=True)

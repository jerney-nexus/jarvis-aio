"""JARVIS kernel — canonical types and seams for the staged architecture.

This package is introduced by the kernel migration plan (docs/KERNEL_PLAN.md) as
a quiet foundation layer: pure, well-tested building blocks that the rest of the
integration migrates onto one caller at a time. Nothing here changes behaviour on
its own — Phase 0 is purely additive.

Phase 0 contents:
    * event.py       — the canonical JarvisEvent record + source adapters.
    * persistence.py — a single SQLite access seam (connection + migrations).
"""
from __future__ import annotations

from . import persistence
from .event import (
    EVENT_CAMERA_ANALYSIS,
    EVENT_STATE_CHANGED,
    EVENT_VOICE_TURN,
    JarvisEvent,
    from_camera_analysis,
    from_state_changed,
    from_voice_turn,
)

__all__ = [
    "JarvisEvent",
    "EVENT_STATE_CHANGED",
    "EVENT_CAMERA_ANALYSIS",
    "EVENT_VOICE_TURN",
    "from_state_changed",
    "from_camera_analysis",
    "from_voice_turn",
    "persistence",
]

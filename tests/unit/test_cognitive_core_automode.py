"""Regression test: the cognitive tick must submit auto-mode evaluation to a
real executor job rather than invoking it inline on the event-loop thread
(the fix for the blocking-call warning in modes.py:_persist)."""
import asyncio
import threading

import pytest


@pytest.fixture
def core_for_tick(cognitive_core, fake_hass):
    # FakeHass.async_add_executor_job normally runs the callable inline, which
    # would make a regression to a direct (non-executor) call pass silently.
    # Use a real thread-pool executor here so the test can tell the difference.
    async def _async_add_executor_job(func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)

    fake_hass.async_add_executor_job = _async_add_executor_job

    core = cognitive_core._CORE
    original = {
        "hass": core.hass,
        "config": core.config,
        "lockdown_mgr": core.lockdown_mgr,
        "proactive_mgr": core.proactive_mgr,
        "safety_mgr": core.safety_mgr,
    }
    core.hass = fake_hass
    core.config = {}
    core.lockdown_mgr = None
    core.proactive_mgr = None

    class _StopAfterAutoMode:
        # auto-mode eval runs before the (unguarded) safety tick call; raising
        # here lets the test stop the tick right after the section under test.
        async def tick(self, *a, **k):
            raise RuntimeError("stop-marker: reached safety tick")

    core.safety_mgr = _StopAfterAutoMode()
    try:
        yield cognitive_core
    finally:
        for attr, value in original.items():
            setattr(core, attr, value)


async def test_auto_mode_eval_runs_on_executor_thread(core_for_tick, load, monkeypatch):
    modes = load("modes")
    main_thread = threading.current_thread()
    seen_threads = []

    def _fake_auto_evaluate(anyone_home):
        seen_threads.append(threading.current_thread())
        return None

    monkeypatch.setattr(modes, "auto_evaluate", _fake_auto_evaluate)

    with pytest.raises(RuntimeError, match="stop-marker"):
        await core_for_tick._tick()

    assert seen_threads, "auto_evaluate was never invoked"
    assert seen_threads[0] is not main_thread

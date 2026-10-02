"""Tests for the in-process event bus (kernel Phase 1)."""
import pytest


@pytest.fixture
def mods(load):
    return load("kernel.event_bus"), load("kernel.event")


def test_publish_delivers_to_type_and_all_subscribers(mods):
    bus_mod, ev_mod = mods
    bus = bus_mod.JarvisEventBus()
    seen_type, seen_all = [], []
    bus.subscribe("state_changed", lambda e: seen_type.append(e))
    bus.subscribe_all(lambda e: seen_all.append(e))

    e1 = ev_mod.JarvisEvent(type="state_changed", source="ha")
    e2 = ev_mod.JarvisEvent(type="voice.turn", source="voice")
    bus.publish(e1)
    bus.publish(e2)

    assert seen_type == [e1]          # only the matching type
    assert seen_all == [e1, e2]       # all events


def test_unsubscribe_stops_delivery(mods):
    bus_mod, ev_mod = mods
    bus = bus_mod.JarvisEventBus()
    got = []
    unsub = bus.subscribe_all(lambda e: got.append(e))
    bus.publish(ev_mod.JarvisEvent(type="x", source="s"))
    unsub()
    bus.publish(ev_mod.JarvisEvent(type="x", source="s"))
    assert len(got) == 1


def test_failing_subscriber_is_isolated(mods):
    bus_mod, ev_mod = mods
    bus = bus_mod.JarvisEventBus()
    good = []

    def boom(e):
        raise RuntimeError("bad subscriber")

    bus.subscribe_all(boom)
    bus.subscribe_all(good.append)
    # publish must not raise, and the good subscriber still runs.
    bus.publish(ev_mod.JarvisEvent(type="x", source="s"))
    assert len(good) == 1


def test_subscriber_count(mods):
    bus_mod, _ = mods
    bus = bus_mod.JarvisEventBus()
    assert bus.subscriber_count() == 0
    bus.subscribe("a", lambda e: None)
    bus.subscribe_all(lambda e: None)
    assert bus.subscriber_count() == 2

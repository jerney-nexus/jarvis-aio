"""Tests for the model/provider router (kernel Phase 6). Pure."""
import pytest


@pytest.fixture
def R(load):
    return load("kernel.router")


def _providers(R):
    return [
        R.Provider(name="local", capabilities=frozenset({"chat"}), local=True,
                   latency_ms=50, cost=0.0, quality=0.6, available=True),
        R.Provider(name="cloud", capabilities=frozenset({"chat", "vision"}), local=False,
                   latency_ms=400, cost=1.0, quality=0.95, available=True),
    ]


def test_prefers_local_when_it_qualifies(R):
    req = R.TaskRequirements(capability="chat", privacy=R.PRIVACY_PREFER_LOCAL)
    res = R.route(req, _providers(R))
    assert res.ok and res.provider.name == "local" and "local-first" in res.reason


def test_privacy_any_picks_highest_quality(R):
    req = R.TaskRequirements(capability="chat", privacy=R.PRIVACY_ANY)
    res = R.route(req, _providers(R))
    assert res.provider.name == "cloud"   # local-first off → best quality wins


def test_local_only_excludes_cloud(R):
    req = R.TaskRequirements(capability="vision", privacy=R.PRIVACY_LOCAL_ONLY)
    res = R.route(req, _providers(R))
    # Only cloud has vision, but local-only forbids it → no eligible provider.
    assert not res.ok and "no eligible" in res.reason


def test_capability_filter(R):
    req = R.TaskRequirements(capability="vision")
    res = R.route(req, _providers(R))
    assert res.provider.name == "cloud"   # only cloud has vision


def test_unavailable_excluded(R):
    provs = _providers(R)
    provs[0] = R.Provider(name="local", capabilities=frozenset({"chat"}), local=True,
                          available=False, quality=0.6)
    req = R.TaskRequirements(capability="chat", privacy=R.PRIVACY_PREFER_LOCAL)
    res = R.route(req, provs)
    assert res.provider.name == "cloud"   # local down → falls back to cloud


def test_latency_and_cost_caps(R):
    req = R.TaskRequirements(capability="chat", max_latency_ms=100)
    res = R.route(req, _providers(R))
    assert res.provider.name == "local"   # cloud too slow

    req2 = R.TaskRequirements(capability="chat", max_cost=0.5, privacy=R.PRIVACY_ANY)
    res2 = R.route(req2, _providers(R))
    assert res2.provider.name == "local"   # cloud too expensive


def test_min_quality_filter(R):
    req = R.TaskRequirements(capability="chat", min_quality=0.9, privacy=R.PRIVACY_PREFER_LOCAL)
    res = R.route(req, _providers(R))
    assert res.provider.name == "cloud"   # local quality 0.6 < 0.9


def test_wildcard_capability_provider(R):
    provs = [R.Provider(name="omni", capabilities=frozenset({"*"}), quality=0.8)]
    res = R.route(R.TaskRequirements(capability="anything"), provs)
    assert res.ok and res.provider.name == "omni"

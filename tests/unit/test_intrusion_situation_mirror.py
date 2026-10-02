"""Phase 3 consumer: intrusion mirrors its lifecycle into kernel.situation (shadow).

Exercises `intrusion._mirror_situation_sync` directly (the shadow logic) with a
real SituationManager on a tmp SQLite db injected into the module. The async
hooks (`async_record_event` / `async_dismiss_intrusion`) just call this off-loop.
"""
import pytest

from fakes import FakeHass


@pytest.fixture
def intr(load):
    return load("intrusion")


@pytest.fixture
def wired(intr, load, tmp_path, monkeypatch):
    """intrusion with a fresh, isolated SituationManager and no open episode."""
    S = load("kernel.situation")
    mgr = S.SituationManager(str(tmp_path / "situations.db"))
    monkeypatch.setattr(intr, "_situation_mgr", mgr)
    monkeypatch.setattr(intr, "_situation_id", None)
    return S, mgr


def test_investigating_opens_and_enters_investigating(intr, wired):
    S, mgr = wired
    intr._mirror_situation_sync(FakeHass(), "investigating",
                                reason="motion while away", breach_area="garage")
    opens = mgr.open_situations("intrusion")
    assert len(opens) == 1
    sit = opens[0]
    assert sit.state == S.INVESTIGATING and sit.location == "garage"
    assert sit.history[0]["to"] == S.POSSIBLE        # opened
    assert sit.history[-1]["to"] == S.INVESTIGATING


def test_confirmed_episode(intr, wired):
    S, mgr = wired
    h = FakeHass()
    intr._mirror_situation_sync(h, "investigating", breach_area="garage")
    intr._mirror_situation_sync(h, "confirmed", reason="person on camera")
    opens = mgr.open_situations("intrusion")
    assert len(opens) == 1 and opens[0].state == S.CONFIRMED
    assert [h_["to"] for h_ in opens[0].history] == [
        S.POSSIBLE, S.INVESTIGATING, S.CONFIRMED]


def test_unresolved_resolves_episode(intr, wired):
    S, mgr = wired
    h = FakeHass()
    intr._mirror_situation_sync(h, "investigating", breach_area="garage")
    intr._mirror_situation_sync(h, "unresolved", reason="no response")
    assert mgr.open_situations("intrusion") == []
    assert intr._situation_id is None


def test_dismissed_marks_benign_then_resolved(intr, wired):
    S, mgr = wired
    h = FakeHass()
    intr._mirror_situation_sync(h, "investigating", breach_area="garage")
    sid = intr._situation_id
    intr._mirror_situation_sync(h, "dismissed", reason="it's just me")
    assert mgr.open_situations("intrusion") == []
    sit = mgr.get(sid)
    states = [h_["to"] for h_ in sit.history]
    assert S.BENIGN in states and sit.state == S.RESOLVED


def test_confirmed_without_prior_investigating(intr, wired):
    S, mgr = wired
    intr._mirror_situation_sync(FakeHass(), "confirmed", breach_area="garage")
    opens = mgr.open_situations("intrusion")
    assert len(opens) == 1 and opens[0].state == S.CONFIRMED


def test_new_episode_after_resolution(intr, wired):
    S, mgr = wired
    h = FakeHass()
    intr._mirror_situation_sync(h, "investigating", breach_area="garage")
    intr._mirror_situation_sync(h, "unresolved")
    intr._mirror_situation_sync(h, "investigating", breach_area="porch")
    opens = mgr.open_situations("intrusion")
    assert len(opens) == 1 and opens[0].location == "porch"  # fresh episode


def test_repeated_investigating_is_idempotent(intr, wired):
    S, mgr = wired
    h = FakeHass()
    intr._mirror_situation_sync(h, "investigating", breach_area="garage")
    intr._mirror_situation_sync(h, "investigating", breach_area="garage")
    opens = mgr.open_situations("intrusion")
    assert len(opens) == 1 and opens[0].state == S.INVESTIGATING


def test_mirror_never_raises_on_bad_manager(intr, monkeypatch):
    # A broken manager must not propagate out of the shadow mirror.
    class _Boom:
        def get(self, *_a, **_k):
            raise RuntimeError("db down")
    monkeypatch.setattr(intr, "_situation_mgr", _Boom())
    monkeypatch.setattr(intr, "_situation_id", "sit_x")
    intr._mirror_situation_sync(FakeHass(), "confirmed")   # must not raise

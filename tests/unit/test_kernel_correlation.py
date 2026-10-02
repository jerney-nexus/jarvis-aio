"""Tests for the ambient correlation id (kernel Phase 1)."""
import pytest


@pytest.fixture
def corr(load):
    return load("kernel.correlation")


def test_default_is_none(corr):
    assert corr.current() is None


def test_scope_sets_and_restores(corr):
    assert corr.current() is None
    with corr.scope("abc"):
        assert corr.current() == "abc"
    assert corr.current() is None


def test_nested_scope_restores_outer(corr):
    with corr.scope("outer"):
        assert corr.current() == "outer"
        with corr.scope("inner"):
            assert corr.current() == "inner"
        assert corr.current() == "outer"
    assert corr.current() is None


def test_falsy_scope_is_passthrough(corr):
    with corr.scope("outer"):
        with corr.scope(None):           # no-op: keeps the outer chain
            assert corr.current() == "outer"
        with corr.scope(""):
            assert corr.current() == "outer"
        assert corr.current() == "outer"


def test_set_and_reset_tokens(corr):
    token = corr.set_current("x")
    try:
        assert corr.current() == "x"
    finally:
        corr.reset(token)
    assert corr.current() is None

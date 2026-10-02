"""Integration-layer conftest.

The unit suite (tests/unit/) uses hand-rolled fakes for speed. This layer is for
the small number of tests that need a REAL Home Assistant instance — config-flow
validation, actual entity/service registration, the setup path — where a fake
can't credibly prove the integration loads.

It relies on `pytest-homeassistant-custom-component` (PHACC), which provides the
real `hass` fixture. PHACC is a heavy, version-pinned dependency, so it is NOT
required for the unit suite; these tests skip cleanly when it is absent.

    pip install pytest-homeassistant-custom-component
"""
import pathlib
import sys

import pytest

# Ensure the repo root is on sys.path so `import custom_components.jarvis`
# resolves to THIS repo. The bare `pytest` console script does not put the
# working directory on sys.path (unlike `python -m pytest`), so without this the
# `custom_components` namespace package can resolve to a path that doesn't
# include this repo and HA's loader reports `IntegrationNotFound: jarvis`.
# Dropping a pre-imported `custom_components` forces the namespace to be rebuilt
# with the repo root included.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
sys.modules.pop("custom_components", None)

# Skip this entire directory unless PHACC is installed.
pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="install pytest-homeassistant-custom-component to run integration tests",
)

# PHACC requires this opt-in fixture to enable loading custom integrations.
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,  # re-exported for test modules
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """PHACC gate: makes `custom_components/jarvis` importable by `hass`."""
    yield

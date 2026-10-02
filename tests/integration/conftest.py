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

import pytest

# Skip this entire directory unless PHACC is installed.
pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="install pytest-homeassistant-custom-component to run integration tests",
)

# PHACC ships its OWN `custom_components` as a *regular* package (it has an
# __init__.py, under testing_config/). This repo's `custom_components` is a
# namespace package (no __init__.py), and a regular package always wins over a
# namespace one regardless of sys.path order — so under pytest `import
# custom_components` binds to PHACC's, which has no `jarvis`, and both the import
# and HA's integration discovery fail with `IntegrationNotFound: jarvis`.
# Fix: merge this repo's custom_components directory into that package's __path__
# so `custom_components.jarvis` (and HA's loader scan of __path__) finds it.
import custom_components  # noqa: E402

_REPO_CC = str(pathlib.Path(__file__).resolve().parents[2] / "custom_components")
if _REPO_CC not in list(custom_components.__path__):
    custom_components.__path__.append(_REPO_CC)

# PHACC requires this opt-in fixture to enable loading custom integrations.
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,  # re-exported for test modules
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """PHACC gate: makes `custom_components/jarvis` importable by `hass`."""
    yield

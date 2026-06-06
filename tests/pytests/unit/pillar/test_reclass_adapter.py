"""
Tests for the reclass ext_pillar adapter.

This module was historically removed during the community-extensions purge
that landed on the 3008 branch.  The tests guard against another regression
of that kind by exercising:

* The module imports cleanly under the ``salt.pillar.reclass_adapter`` name.
* The ``__virtualname__`` is the documented ``reclass`` so the loader binds
  ``ext_pillar: - reclass:`` entries to the adapter.
* ``__virtual__`` reports a clean failure (rather than raising) when the
  ``reclass`` third-party package is unavailable.
* ``ext_pillar`` delegates to the bundled ``reclass.adapters.salt`` entry
  point and forwards the per-minion arguments unchanged.
"""

import sys
import types

import pytest

import salt.pillar.reclass_adapter as reclass_adapter
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {reclass_adapter: {"__opts__": {"ext_pillar": []}}}


def test_virtualname_is_reclass():
    """
    The loader matches ``ext_pillar`` entries by ``__virtualname__``; the
    documented name has always been ``reclass`` (the module is named
    ``reclass_adapter`` only because ``reclass`` would shadow the upstream
    package on import).
    """
    assert reclass_adapter.__virtualname__ == "reclass"


def test_virtual_returns_false_without_reclass_package():
    """
    When the upstream ``reclass`` package is not importable and no source
    path is configured, ``__virtual__`` must return ``False`` instead of
    raising.  A raising ``__virtual__`` would crash the loader scan.
    """
    with patch.dict(sys.modules, {"reclass": None}):
        assert reclass_adapter.__virtual__() is False


def test_ext_pillar_delegates_to_reclass_adapter():
    """
    ``ext_pillar`` must call ``reclass.adapters.salt.ext_pillar`` with the
    minion id, current pillar, and any keyword options passed through from
    the master config.
    """
    fake_reclass = types.ModuleType("reclass")
    fake_adapters = types.ModuleType("reclass.adapters")
    fake_salt = types.ModuleType("reclass.adapters.salt")
    fake_errors = types.ModuleType("reclass.errors")

    class ReclassException(Exception):
        pass

    fake_errors.ReclassException = ReclassException
    expected = {"pillar": "data"}
    fake_salt.ext_pillar = MagicMock(return_value=expected)

    modules = {
        "reclass": fake_reclass,
        "reclass.adapters": fake_adapters,
        "reclass.adapters.salt": fake_salt,
        "reclass.errors": fake_errors,
    }

    with patch.dict(sys.modules, modules), patch.dict(
        reclass_adapter.__opts__,
        {"ext_pillar": [], "file_roots": {}},
        clear=False,
    ):
        result = reclass_adapter.ext_pillar(
            "minion-1",
            {"existing": "pillar"},
            storage_type="yaml_fs",
            inventory_base_uri="/srv/salt",
        )

    assert result == expected
    fake_salt.ext_pillar.assert_called_once_with(
        "minion-1",
        {"existing": "pillar"},
        storage_type="yaml_fs",
        inventory_base_uri="/srv/salt",
    )

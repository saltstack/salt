"""
    Tests for the saltutil state
"""

import inspect

import pytest
import salt.modules.saltutil as saltutil_module
import salt.states.saltutil as saltutil_state
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {saltutil_state: {"__opts__": {"test": False}}}


def test_saltutil_sync_all_nochange():
    sync_output = {
        "clouds": [],
        "engines": [],
        "executors": [],
        "grains": [],
        "beacons": [],
        "utils": [],
        "returners": [],
        "modules": [],
        "renderers": [],
        "log_handlers": [],
        "thorium": [],
        "states": [],
        "sdb": [],
        "proxymodules": [],
        "output": [],
        "pillar": [],
        "matchers": [],
        "serializers": [],
    }
    state_id = "somename"
    state_result = {
        "changes": {},
        "comment": "No updates to sync",
        "name": "somename",
        "result": True,
    }

    mock_moduleout = MagicMock(return_value=sync_output)
    with patch.dict(saltutil_state.__salt__, {"saltutil.sync_all": mock_moduleout}):
        result = saltutil_state.sync_all(state_id, refresh=True)
        assert result == state_result


def test_saltutil_sync_all_test():
    sync_output = {
        "clouds": [],
        "engines": [],
        "executors": [],
        "grains": [],
        "beacons": [],
        "utils": [],
        "returners": [],
        "modules": [],
        "renderers": [],
        "log_handlers": [],
        "thorium": [],
        "states": [],
        "sdb": [],
        "proxymodules": [],
        "output": [],
        "pillar": [],
        "matchers": [],
        "serializers": [],
    }
    state_id = "somename"
    state_result = {
        "changes": {},
        "comment": "saltutil.sync_all would have been run",
        "name": "somename",
        "result": None,
    }

    mock_moduleout = MagicMock(return_value=sync_output)
    with patch.dict(saltutil_state.__salt__, {"saltutil.sync_all": mock_moduleout}):
        with patch.dict(saltutil_state.__opts__, {"test": True}):
            result = saltutil_state.sync_all(state_id, refresh=True)
            assert result == state_result


def test_saltutil_sync_all_change():
    sync_output = {
        "clouds": [],
        "engines": [],
        "executors": [],
        "grains": [],
        "beacons": [],
        "utils": [],
        "returners": [],
        "modules": ["modules.file"],
        "renderers": [],
        "log_handlers": [],
        "thorium": [],
        "states": ["states.saltutil", "states.ssh_auth"],
        "sdb": [],
        "proxymodules": [],
        "output": [],
        "pillar": [],
        "matchers": [],
        "serializers": [],
    }
    state_id = "somename"
    state_result = {
        "changes": {
            "modules": ["modules.file"],
            "states": ["states.saltutil", "states.ssh_auth"],
        },
        "comment": "Sync performed",
        "name": "somename",
        "result": True,
    }

    mock_moduleout = MagicMock(return_value=sync_output)
    with patch.dict(saltutil_state.__salt__, {"saltutil.sync_all": mock_moduleout}):
        result = saltutil_state.sync_all(state_id, refresh=True)
        assert result == state_result


def test_saltutil_sync_states_should_match_saltutil_module():
    module_functions = [
        f[0]
        for f in inspect.getmembers(saltutil_module, inspect.isfunction)
        if f[0].startswith("sync_")
    ]
    state_functions = [
        f[0]
        for f in inspect.getmembers(saltutil_state, inspect.isfunction)
        if f[0].startswith("sync_")
    ]
    for fn in module_functions:
        assert (
            fn in state_functions
        ), "modules.saltutil.{} has no matching state in states.saltutil".format(fn)

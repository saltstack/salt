import logging

import pytest

import salt.config
import salt.state

log = logging.getLogger(__name__)


@pytest.fixture
def minion_config(minion_opts):
    minion_opts["file_client"] = "local"
    minion_opts["id"] = "foo01"
    return minion_opts


def test_global_state_conditions_unconfigured(minion_config):
    state_obj = salt.state.State(minion_config)
    ret = state_obj._match_global_state_conditions(
        "test.succeed_with_changes", "test", "mytest"
    )
    assert ret is None


@pytest.mark.parametrize("condition", [["foo01"], "foo01"])
def test_global_state_conditions_match(minion_config, condition):
    minion_config["global_state_conditions"] = {
        "test": condition,
    }
    state_obj = salt.state.State(minion_config)
    ret = state_obj._match_global_state_conditions(
        "test.succeed_with_changes", "test", "mytest"
    )
    assert ret is None


def test_global_state_conditions_no_match(minion_config):
    minion_config["global_state_conditions"] = {
        "test.succeed_with_changes": ["bar01"],
    }
    state_obj = salt.state.State(minion_config)
    ret = state_obj._match_global_state_conditions(
        "test.succeed_with_changes", "test", "mytest"
    )
    assert ret == {
        "changes": {},
        "comment": "Failed to meet global state conditions. State not called.",
        "name": "mytest",
        "result": None,
    }


def test_global_state_conditions_match_one_of_many(minion_config):
    minion_config["global_state_conditions"] = {
        "test.succeed_with_changes": ["bar01"],
        "test": ["baz01"],
        "*": ["foo01"],
    }
    state_obj = salt.state.State(minion_config)
    ret = state_obj._match_global_state_conditions(
        "test.succeed_with_changes", "test", "mytest"
    )
    assert ret is None

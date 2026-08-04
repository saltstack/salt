"""
Test cases for salt.states.zenoss
"""

import pytest

import salt.states.zenoss as zenoss
from salt.utils.decorators.state import OutputUnifier
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        zenoss: {
            "__opts__": {"test": False},
            "__salt__": {},
        }
    }


def _content_check(ret):
    """
    Run ``ret`` through the exact policy stack the state compiler applies to
    every state return: ``OutputUnifier("content_check", "unify")`` (see
    salt.state.State.call). content_check raises "'Changes' should be a
    dictionary." when ``changes`` is not a dict; the unifier traps that and
    rewrites the return to result=False with an "An exception occurred"
    comment. Returning the post-policy dict lets the tests assert on the
    production-visible symptom.
    """
    return OutputUnifier("content_check", "unify")(lambda: ret)()


def test_already_monitored_no_prod_state_53966():
    """
    Device already known to Zenoss and no prod_state requested. This is the
    reproducer from issue #53966: the early-return path used to set
    changes=None, which fails content_check with "'Changes' should be a
    dictionary." It must now be an empty dict and survive the policy stack.
    """
    salt_mock = {
        "zenoss.find_device": MagicMock(return_value={"productionState": 1000}),
        "zenoss.set_prod_state": MagicMock(),
    }
    with patch.dict(zenoss.__salt__, salt_mock):
        # prod_state defaults to None, matching the reported state (no prod_state key)
        ret = zenoss.monitored("centos7-5.local", device_class="/Server/SSH/Linux")

    assert ret["changes"] == {}
    assert ret["result"] is True

    checked = _content_check(ret)
    assert "'Changes' should be a dictionary." not in checked["comment"]
    assert checked["result"] is True


def test_failed_add_53966():
    """
    Device is not in Zenoss and add_device fails. The failure path used to set
    changes=None, tripping the same content_check exception. It must now be an
    empty dict while still reporting result=False.
    """
    salt_mock = {
        "zenoss.find_device": MagicMock(return_value=None),
        "zenoss.add_device": MagicMock(return_value=False),
    }
    with patch.dict(zenoss.__salt__, salt_mock):
        ret = zenoss.monitored("centos7-5.local", device_class="/Server/SSH/Linux")

    assert ret["result"] is False
    assert ret["changes"] == {}

    checked = _content_check(ret)
    assert "'Changes' should be a dictionary." not in checked["comment"]
    assert checked["result"] is False


def test_already_monitored_prod_state_update():
    """
    Inverse / must-not-regress: already monitored but the requested prod_state
    differs from the current one. This branch always populated a proper changes
    dict, so it passes with and without the fix. Guards that the None -> {}
    change did not disturb the real-change path.
    """
    set_prod_state = MagicMock()
    salt_mock = {
        "zenoss.find_device": MagicMock(return_value={"productionState": 500}),
        "zenoss.set_prod_state": set_prod_state,
    }
    with patch.dict(zenoss.__salt__, salt_mock):
        ret = zenoss.monitored("centos7-5.local", prod_state=1000)

    assert ret["result"] is True
    assert ret["changes"] == {
        "old": "prodState == 500",
        "new": "prodState == 1000",
    }
    set_prod_state.assert_called_once_with(1000, "centos7-5.local")
    assert _content_check(ret)["result"] is True


def test_add_device_success():
    """
    Inverse / must-not-regress: device absent and add_device succeeds. This
    branch always populated a proper changes dict, so it passes with and
    without the fix.
    """
    salt_mock = {
        "zenoss.find_device": MagicMock(return_value=None),
        "zenoss.add_device": MagicMock(return_value=True),
    }
    with patch.dict(zenoss.__salt__, salt_mock):
        ret = zenoss.monitored("centos7-5.local", device_class="/Server/SSH/Linux")

    assert ret["result"] is True
    assert ret["changes"] == {
        "old": "monitored == False",
        "new": "monitored == True",
    }
    assert _content_check(ret)["result"] is True


def test_add_device_test_mode():
    """
    Peripheral coverage: device absent under test=True reports a pending change
    with result=None and a proper changes dict.
    """
    salt_mock = {
        "zenoss.find_device": MagicMock(return_value=None),
        "zenoss.add_device": MagicMock(return_value=True),
    }
    with patch.dict(zenoss.__opts__, {"test": True}), patch.dict(
        zenoss.__salt__, salt_mock
    ):
        ret = zenoss.monitored("centos7-5.local", device_class="/Server/SSH/Linux")

    assert ret["result"] is None
    assert ret["changes"] == {
        "old": "monitored == False",
        "new": "monitored == True",
    }

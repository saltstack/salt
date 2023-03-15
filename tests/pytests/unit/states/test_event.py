"""
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
"""

import pytest

import salt.states.event as event
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {event: {}}


def test_send():
    """
    Test to send an event to the Salt Master
    """
    with patch.dict(event.__opts__, {"test": True}):
        assert event.send("salt") == {
            "changes": {"data": None, "tag": "salt"},
            "comment": "Event would have been fired",
            "name": "salt",
            "result": None,
        }

    with patch.dict(event.__opts__, {"test": False}):
        mock = MagicMock(return_value=True)
        with patch.dict(event.__salt__, {"event.send": mock}):
            assert event.send("salt") == {
                "changes": {"data": None, "tag": "salt"},
                "comment": "Event fired",
                "name": "salt",
                "result": True,
            }


def test_wait():
    """
    Test to fire an event on the Salt master
    """
    assert event.wait("salt") == {
        "changes": {},
        "comment": "",
        "name": "salt",
        "result": True,
    }

    assert event.wait("salt", sfun="some_function") == {
        "changes": {},
        "comment": "",
        "name": "salt",
        "result": True,
    }

    assert event.wait("salt", data={"random": "data"}) == {
        "changes": {},
        "comment": "",
        "name": "salt",
        "result": True,
    }

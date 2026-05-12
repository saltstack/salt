import copy

import pytest

import salt.states.saltmod as saltmod
import salt.utils.state
from tests.support.mock import MagicMock, patch


class MockedEvent:
    """
    Mocked event class
    """

    def __init__(self, data):
        self.full = None
        self.flag = None
        self._data = data

    def get_event(self, full):
        """
        Mock get_event method
        """
        self.full = full
        if self.flag:
            return self._data
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        saltmod: {
            "__opts__": minion_opts,
        },
    }


def test_test_mode():
    name = "presence"
    event_id = "lost"
    tgt = ["minion_1", "minion_2", "minion_3"]

    expected = {
        "name": name,
        "changes": {},
        "result": None,
        "comment": f"Orchestration would wait for event '{name}'",
    }

    with patch.dict(saltmod.__opts__, {"test": True}):
        ret = saltmod.wait_for_event(name, tgt, event_id=event_id, timeout=-1.0)
        assert ret == expected


def test_wait_for_event():
    """
    Test to watch Salt's event bus and block until a condition is met
    """
    name = "state"
    tgt = "minion1"

    ret = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Timeout value reached.",
    }

    mocked_event = MockedEvent({"tag": name, "data": {}})
    with patch.object(
        salt.utils.event, "get_event", MagicMock(return_value=mocked_event)
    ):
        with patch.dict(saltmod.__opts__, {"sock_dir": True, "transport": True}):
            with patch("salt.states.saltmod.time.time", MagicMock(return_value=1.0)):
                assert saltmod.wait_for_event(name, "salt", timeout=-1.0) == ret

                mocked_event.flag = True
                ret.update(
                    {"comment": "All events seen in 0.0 seconds.", "result": True}
                )
                assert saltmod.wait_for_event(name, "") == ret

                ret.update({"comment": "Timeout value reached.", "result": False})
                assert saltmod.wait_for_event(name, tgt, timeout=-1.0) == ret


def test_list_single_event():
    """
    Test to watch Salt's event bus and block until a condition is met
    """
    name = "presence"
    event_id = "lost"
    tgt = ["minion_1", "minion_2", "minion_3"]

    expected = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Timeout value reached.",
    }

    mocked_event = MockedEvent({"tag": name, "data": {"lost": tgt}})
    with patch.object(
        salt.utils.event, "get_event", MagicMock(return_value=mocked_event)
    ):
        with patch.dict(saltmod.__opts__, {"sock_dir": True, "transport": True}):
            with patch("salt.states.saltmod.time.time", MagicMock(return_value=1.0)):
                expected.update({"comment": "Timeout value reached.", "result": False})
                ret = saltmod.wait_for_event(name, tgt, event_id=event_id, timeout=-1.0)
                assert ret == expected

                mocked_event.flag = True
                expected.update(
                    {
                        "name": name,
                        "changes": {"minions_seen": tgt},
                        "result": True,
                        "comment": "All events seen in 0.0 seconds.",
                    }
                )
                ret = saltmod.wait_for_event(
                    name, copy.deepcopy(tgt), event_id="lost", timeout=1.0
                )
                assert ret == expected

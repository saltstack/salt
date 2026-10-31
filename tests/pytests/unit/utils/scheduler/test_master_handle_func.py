"""
Regression tests for ``Schedule.handle_func`` when running with the master role.

See https://github.com/saltstack/salt/issues/67710

A master-role scheduler only loads runners.  When a scheduled job fails before
the ``NamespacedEvent`` is created (for example, an execution module function
such as ``test.ping`` configured in the master schedule), the ``finally``
cleanup used to raise ``UnboundLocalError`` for ``namespaced_event`` which
skipped the remaining cleanup.
"""

import logging
import os

import pytest

import salt.minion
import salt.utils.event
from tests.support.mock import MagicMock, patch

try:
    import dateutil.parser  # pylint: disable=unused-import

    HAS_DATEUTIL_PARSER = True
except ImportError:
    HAS_DATEUTIL_PARSER = False

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(
        HAS_DATEUTIL_PARSER is False,
        reason="The 'dateutil.parser' library is not available",
    ),
]


def _runner_ping():
    return True


class _FakeRunners(dict):
    """
    Minimal stand-in for the runner LazyLoader.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pack = {"__context__": {}}

    def missing_fun_string(self, func):
        return f"'{func}' is not available."


@pytest.fixture
def master_schedule(schedule):
    schedule.opts["__role"] = "master"
    schedule.opts["id"] = "master"
    return schedule


@pytest.fixture
def mocks(master_schedule):
    """
    Patch the loaders and event machinery which ``handle_func`` re-creates
    in the child process.
    """
    runners = _FakeRunners({"test.ping_runner": _runner_ping})
    namespaced_event = MagicMock(name="namespaced_event")
    return_event = MagicMock(name="return_event")

    def _get_event(*args, **kwargs):
        return MagicMock(name="event")

    with patch("salt.loader.utils", MagicMock(return_value={})), patch(
        "salt.loader.runner", MagicMock(return_value=runners)
    ), patch("salt.loader.returners", MagicMock(return_value={})), patch(
        "salt.utils.event.get_event", MagicMock(side_effect=_get_event)
    ), patch(
        "salt.utils.event.get_master_event", MagicMock(return_value=return_event)
    ), patch(
        "salt.utils.event.NamespacedEvent", MagicMock(return_value=namespaced_event)
    ), patch(
        "weakref.proxy", MagicMock(side_effect=lambda obj: obj)
    ):
        yield runners, namespaced_event, return_event


def _proc_dir(schedule):
    return salt.minion.get_proc_dir(schedule.opts["cachedir"])


def test_master_handle_func_missing_function_does_not_raise(master_schedule, mocks):
    """
    A master schedule referencing a function that is not a runner (such as an
    execution module function) must be handled as a normal job failure and
    must not raise ``UnboundLocalError`` from the ``finally`` cleanup.
    """
    _, namespaced_event, return_event = mocks
    jid = "20250204204041060564"
    data = {"name": "hello_world", "function": "test.ping", "jid_include": True}

    # Must not raise
    master_schedule.handle_func(False, "test.ping", data, jid=jid)

    # The namespaced event was never created, so there is nothing to destroy
    namespaced_event.destroy.assert_not_called()

    # The failure is still reported back via the __schedule_return event
    return_event.fire_event.assert_called_once()
    load, tag = return_event.fire_event.call_args.args
    assert tag == "__schedule_return"
    assert load["fun"] == "test.ping"
    assert load["success"] is False
    assert load["retcode"] == 254
    assert "'test.ping' is not available." in load["return"]
    return_event.destroy.assert_called_once_with()

    # The remaining cleanup still happened: no leaked proc file
    assert not os.path.exists(os.path.join(_proc_dir(master_schedule), jid))


def test_master_handle_func_runner_destroys_namespaced_event(master_schedule, mocks):
    """
    When the job runs (a runner function), the namespaced event is created and
    destroyed, and the proc file is cleaned up.
    """
    runners, namespaced_event, return_event = mocks
    runners["test.ping_runner"] = _runner_ping
    jid = "20250204204041060565"
    data = {"name": "hello_runner", "function": "test.ping_runner", "jid_include": True}

    master_schedule.handle_func(False, "test.ping_runner", data, jid=jid)

    namespaced_event.destroy.assert_called_once_with()
    return_event.fire_event.assert_called_once()
    load, tag = return_event.fire_event.call_args.args
    assert tag == "__schedule_return"
    assert load["success"] is True
    assert load["return"] is True
    assert not os.path.exists(os.path.join(_proc_dir(master_schedule), jid))


def test_master_handle_func_namespaced_event_destroy_failure_is_contained(
    master_schedule, mocks
):
    """
    A failure destroying the namespaced event must not skip the proc file
    cleanup.
    """
    _, namespaced_event, _ = mocks
    namespaced_event.destroy.side_effect = RuntimeError("boom")
    jid = "20250204204041060566"
    data = {"name": "hello_runner", "function": "test.ping_runner", "jid_include": True}

    master_schedule.handle_func(False, "test.ping_runner", data, jid=jid)

    namespaced_event.destroy.assert_called_once_with()
    assert not os.path.exists(os.path.join(_proc_dir(master_schedule), jid))

"""
unit tests for the script engine
"""

import contextlib
import logging
import signal
import sys

import pytest

import salt.engines.script as script
from salt.exceptions import CommandExecutionError
from tests.support.mock import Mock, patch

log = logging.getLogger(__name__)


def _check_skip(grains):
    if grains["os"] == "MacOS":
        return True
    return False


pytestmark = [
    pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip),
]


@pytest.fixture
def configure_loader_modules(master_opts):
    return {script: {"__opts__": master_opts}}


def test__get_serializer():
    """
    Test known serializer is returned or exception is raised
    if unknown serializer
    """
    for serializers in ("json", "yaml", "msgpack"):
        assert script._get_serializer(serializers)

    with pytest.raises(CommandExecutionError):
        script._get_serializer("bad")


def test__read_stdout():
    """
    Test we can yield stdout
    """
    with patch("subprocess.Popen") as popen_mock:
        popen_mock.stdout.readline.return_value = "test"
        assert next(script._read_stdout(popen_mock)) == "test"


def test__read_stdout_terminates_properly():
    """
    Test that _read_stdout terminates with the sentinel
    """
    with patch("subprocess.Popen") as popen_mock:
        popen_mock.stdout.readline.return_value = b""
        with pytest.raises(StopIteration):
            next(script._read_stdout(popen_mock))


@pytest.fixture()
def serializer():
    with patch("salt.engines.script._get_serializer", autospec=True) as get_serializer:
        serializer = Mock()
        get_serializer.return_value = serializer
        serializer.deserialize.side_effect = lambda x: x
        yield serializer


@pytest.fixture()
def event_send():
    event = Mock()
    with patch("salt.utils.event.get_master_event", autospec=True) as get_master:
        get_master.return_value.fire_event = event
        with patch.dict(script.__salt__, {"event.send": event}):
            yield event


@pytest.fixture()
def raw_event():
    with patch("salt.engines.script._read_stdout", autospec=True) as stdout:
        yield stdout


@pytest.fixture()
def proc():
    with patch("subprocess.Popen", autospec=True) as popen:
        proc = Mock()
        proc.wait.return_value = False
        proc.pid = 1337
        popen.return_value = proc
        yield


@pytest.fixture()
def event():
    return {"tag": "test", "data": {"foo": "bar", "id": "test"}}


@pytest.fixture()
def new_tag():
    return {"tag": "testnew", "data": {"foo": "bar", "id": "test"}}


@pytest.fixture()
def new_event():
    return {"tag": "test", "data": {"foo": "baz", "id": "test"}}


@pytest.fixture
def timeout():
    """
    This fixture was proposed by waynew to allow testing
    an otherwise infinite loop.
    Once https://github.com/saltstack/salt/pull/62910 is merged,
    this can be migrated.
    """
    if sys.platform.startswith("win"):
        pytest.skip("SIGALRM is not available on Windows.")

    def handler(num, frame):
        raise TimeoutError()

    @contextlib.contextmanager
    def _timeout(t=1):
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(t)

        try:
            yield _timeout
        except TimeoutError:
            pass
        finally:
            signal.alarm(0)

    return _timeout


@pytest.mark.usefixtures("proc", "serializer", "event_send", "raw_event", "timeout")
class TestStart:
    def test_start(self, event, raw_event, event_send, timeout):
        raw_event.side_effect = ([event],)
        try:
            with timeout():
                script.start("cmd", interval=1.5)
        except StopIteration:
            log.warning("Timeout failure")
        event_send.assert_called_once_with(tag=event["tag"], data=event["data"])

    def test_multiple(self, event, new_event, raw_event, event_send, timeout):
        raw_event.side_effect = ([event, new_event],)
        try:
            with timeout():
                script.start("cmd", interval=1.5)
        except StopIteration:
            log.warning("Timeout failure")
        assert event_send.call_count == 2
        event_send.assert_any_call(tag=event["tag"], data=event["data"])
        event_send.assert_any_call(tag=new_event["tag"], data=new_event["data"])

    def test_onchange_no_change_no_output(self, event, raw_event, event_send, timeout):
        raw_event.side_effect = 110 * ([event],)
        try:
            with timeout():
                script.start("cmd", onchange=True, interval=0.01)
        except StopIteration:
            log.warning("Timeout failure")
        event_send.assert_called_once_with(tag=event["tag"], data=event["data"])

    def test_start_onchange_no_change_multiple(
        self, event, new_tag, raw_event, event_send, timeout
    ):
        raw_event.side_effect = 110 * ([event, new_tag],)
        try:
            with timeout():
                script.start("cmd", onchange=True, interval=0.01)
        except StopIteration:
            log.warning("Timeout failure")
        assert event_send.call_count == 2
        event_send.assert_any_call(tag=event["tag"], data=event["data"])
        event_send.assert_any_call(tag=new_tag["tag"], data=new_tag["data"])

    def test_start_onchange_with_change(
        self, event, new_event, raw_event, event_send, timeout
    ):
        raw_event.side_effect = 50 * [[event]] + 60 * [[new_event]]
        try:
            with timeout():
                script.start("cmd", onchange=True, interval=0.01)
        except StopIteration:
            log.warning("Timeout failure")
        assert event_send.call_count == 2
        event_send.assert_any_call(tag=event["tag"], data=event["data"])
        event_send.assert_called_with(tag=new_event["tag"], data=new_event["data"])

    def test_start_onchange_new_tag(
        self, event, new_tag, raw_event, event_send, timeout
    ):
        raw_event.side_effect = 50 * [[event]] + 60 * [[new_tag]]
        try:
            with timeout():
                script.start("cmd", onchange=True, interval=0.01)
        except StopIteration:
            log.warning("Timeout failure")
        event_send.assert_any_call(tag=event["tag"], data=event["data"])
        event_send.assert_called_with(tag=new_tag["tag"], data=new_tag["data"])

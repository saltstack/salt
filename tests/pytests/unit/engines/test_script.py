"""
unit tests for the script engine
"""

import copy

import pytest

import salt.config
import salt.engines.script as script
from salt.exceptions import CommandExecutionError
from tests.support.mock import Mock, patch


@pytest.fixture
def configure_loader_modules():
    opts = copy.deepcopy(salt.config.DEFAULT_MASTER_OPTS)
    opts["id"] = "test"
    return {script: {"__opts__": opts}}


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


@pytest.fixture(params=[1])
def runs(request):
    runs = Mock()
    runs.side_effect = request.param * [True] + [False]
    with patch("salt.engines.script._running", runs):
        yield


@pytest.fixture()
def event_send():
    event = Mock()
    with patch("salt.utils.event.get_master_event") as get_master:
        get_master.fire_event = event
        with patch.dict(script.__salt__, {"event.send": event}):
            yield event


@pytest.fixture()
def raw_event():
    with patch("salt.engines.script._read_stdout") as stdout:
        yield stdout


@pytest.fixture()
def proc():
    with patch("salt.engines.script.subprocess.Popen") as popen:
        proc = Mock()
        proc.wait.return_value = False
        proc.pid = 1337
        popen.return_value = proc
        yield


@pytest.fixture()
def sleep():
    with patch("time.sleep"):
        yield


@pytest.fixture()
def event():
    return {"tag": "test", "data": {"foo": "bar", "id": "test"}}


@pytest.fixture()
def new_event():
    return {"tag": "test", "data": {"foo": "baz", "id": "test"}}


@pytest.mark.usefixtures(
    "proc", "serializer", "runs", "sleep", "event_send", "raw_event"
)
class TestStart:
    def test_start(self, event, raw_event, event_send):
        raw_event.return_value = [event]
        script.start("cmd")
        event_send.assert_called_once_with(tag=event["tag"], data=event["data"])

    @pytest.mark.parametrize("runs", [10], indirect=True)
    def test_start_onchange_no_change(self, event, raw_event, event_send):
        raw_event.side_effect = 10 * [[event]]
        script.start("cmd", onchange=True)
        event_send.assert_called_once_with(tag=event["tag"], data=event["data"])

    @pytest.mark.parametrize("runs", [8], indirect=True)
    def test_start_onchange_with_change(self, event, new_event, raw_event, event_send):
        raw_event.side_effect = 3 * [[event]] + 5 * [[new_event]]
        script.start("cmd", onchange=True)
        assert event_send.call_count == 2
        event_send.assert_any_call(tag=event["tag"], data=event["data"])
        event_send.assert_called_with(tag=new_event["tag"], data=new_event["data"])

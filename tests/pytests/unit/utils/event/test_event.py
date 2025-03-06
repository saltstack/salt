import os
import stat
import time
from pathlib import Path

import pytest
import tornado.iostream
import zmq

import salt.config
import salt.utils.event
import salt.utils.stringutils
from salt.exceptions import SaltDeserializationError
from salt.utils.event import SaltEvent
from tests.support.events import eventpublisher_process, eventsender_process
from tests.support.mock import patch

NO_LONG_IPC = False
if getattr(zmq, "IPC_PATH_MAX_LEN", 103) <= 103:
    NO_LONG_IPC = True

pytestmark = [
    pytest.mark.skipif(
        NO_LONG_IPC,
        reason="This system does not support long IPC paths. Skipping event tests!",
    ),
]


@pytest.fixture(autouse=True)
def sock_dir(tmp_path):
    sock_dir_path = tmp_path / "test-socks"
    sock_dir_path.mkdir(parents=True, exist_ok=True)
    yield sock_dir_path


def _assert_got_event(evt, data, msg=None, expected_failure=False):
    assert evt is not None, msg
    for key in data:
        assert key in evt, f"{msg}: Key {key} missing"
        assertMsg = "{0}: Key {1} value mismatch, {2} != {3}"
        assertMsg = assertMsg.format(msg, key, data[key], evt[key])
        if not expected_failure:
            assert data[key] == evt[key], assertMsg
        else:
            assert data[key] != evt[key]


@pytest.mark.slow_test
def test_event_single(sock_dir):
    """Test a single event is received"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            evt1 = me.get_event(tag="evt1")
            _assert_got_event(evt1, {"data": "foo1"})


@pytest.mark.slow_test
def test_event_single_no_block(sock_dir):
    """Test a single event is received, no block"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            start = time.time()
            finish = start + 5
            evt1 = me.get_event(wait=0, tag="evt1", no_block=True)
            # We should get None and way before the 5 seconds wait since it's
            # non-blocking, otherwise it would wait for an event which we
            # didn't even send
            assert evt1 is None, None
            assert start < finish
            me.fire_event({"data": "foo1"}, "evt1")
            evt1 = me.get_event(wait=0, tag="evt1")
            _assert_got_event(evt1, {"data": "foo1"})


@pytest.mark.slow_test
def test_event_single_wait_0_no_block_False(sock_dir):
    """Test a single event is received with wait=0 and no_block=False and doesn't spin the while loop"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            # This is too fast and will be None but assures we're not blocking
            evt1 = me.get_event(wait=0, tag="evt1", no_block=False)
            _assert_got_event(evt1, {"data": "foo1"})


@pytest.mark.slow_test
def test_event_timeout(sock_dir):
    """Test no event is received if the timeout is reached"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            evt1 = me.get_event(tag="evt1")
            _assert_got_event(evt1, {"data": "foo1"})
            evt2 = me.get_event(tag="evt1")
            assert evt2 is None


@pytest.mark.slow_test
def test_event_no_timeout(sock_dir):
    """Test no wait timeout, we should block forever, until we get one"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            with eventsender_process({"data": "foo2"}, "evt2", str(sock_dir), 5):
                evt = me.get_event(tag="evt2", wait=0, no_block=False)
            _assert_got_event(evt, {"data": "foo2"})


@pytest.mark.slow_test
def test_event_matching(sock_dir):
    """Test a startswith match"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            evt1 = me.get_event(tag="ev")
            _assert_got_event(evt1, {"data": "foo1"})


@pytest.mark.slow_test
def test_event_matching_regex(sock_dir):
    """Test a regex match"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            evt1 = me.get_event(tag="^ev", match_type="regex")
            _assert_got_event(evt1, {"data": "foo1"})


@pytest.mark.slow_test
def test_event_matching_all(sock_dir):
    """Test an all match"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            evt1 = me.get_event(tag="")
            _assert_got_event(evt1, {"data": "foo1"})


@pytest.mark.slow_test
def test_event_matching_all_when_tag_is_None(sock_dir):
    """Test event matching all when not passing a tag"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            evt1 = me.get_event()
            _assert_got_event(evt1, {"data": "foo1"})


@pytest.mark.slow_test
def test_event_not_subscribed(sock_dir):
    """Test get_event drops non-subscribed events"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            me.fire_event({"data": "foo2"}, "evt2")
            evt2 = me.get_event(tag="evt2")
            evt1 = me.get_event(tag="evt1")
            _assert_got_event(evt2, {"data": "foo2"})
            assert evt1 is None


@pytest.mark.slow_test
def test_event_subscription_cache(sock_dir):
    """Test subscriptions cache a message until requested"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.subscribe("evt1")
            me.fire_event({"data": "foo1"}, "evt1")
            me.fire_event({"data": "foo2"}, "evt2")
            evt2 = me.get_event(tag="evt2")
            evt1 = me.get_event(tag="evt1")
            _assert_got_event(evt2, {"data": "foo2"})
            _assert_got_event(evt1, {"data": "foo1"})


@pytest.mark.slow_test
def test_event_subscriptions_cache_regex(sock_dir):
    """Test regex subscriptions cache a message until requested"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.subscribe("e..1$", "regex")
            me.fire_event({"data": "foo1"}, "evt1")
            me.fire_event({"data": "foo2"}, "evt2")
            evt2 = me.get_event(tag="evt2")
            evt1 = me.get_event(tag="evt1")
            _assert_got_event(evt2, {"data": "foo2"})
            _assert_got_event(evt1, {"data": "foo1"})


@pytest.mark.slow_test
def test_event_multiple_clients(sock_dir):
    """Test event is received by multiple clients"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(
            str(sock_dir), listen=True
        ) as me1, salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me2:
            # We need to sleep here to avoid a race condition wherein
            # the second socket may not be connected by the time the first socket
            # sends the event.
            time.sleep(0.5)
            me1.fire_event({"data": "foo1"}, "evt1")
            evt1 = me1.get_event(tag="evt1")
            _assert_got_event(evt1, {"data": "foo1"})
            evt2 = me2.get_event(tag="evt1")
            _assert_got_event(evt2, {"data": "foo1"})


def test_event_nested_sub_all(sock_dir):
    """Test nested event subscriptions do not drop events, get event for all tags"""
    # Show why not to call get_event(tag='')
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            me.fire_event({"data": "foo2"}, "evt2")
            evt2 = me.get_event(tag="")
            evt1 = me.get_event(tag="")
            _assert_got_event(evt2, {"data": "foo2"}, expected_failure=True)
            _assert_got_event(evt1, {"data": "foo1"}, expected_failure=True)


@pytest.mark.slow_test
def test_event_many(sock_dir):
    """Test a large number of events, one at a time"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            for i in range(500):
                me.fire_event({"data": f"{i}"}, "testevents")
                evt = me.get_event(tag="testevents")
                _assert_got_event(evt, {"data": f"{i}"}, f"Event {i}")


@pytest.mark.slow_test
def test_event_many_backlog(sock_dir):
    """Test a large number of events, send all then recv all"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            # Must not exceed zmq HWM
            for i in range(500):
                me.fire_event({"data": f"{i}"}, "testevents")
            for i in range(500):
                evt = me.get_event(tag="testevents")
                _assert_got_event(evt, {"data": f"{i}"}, f"Event {i}")


# Test the fire_master function. As it wraps the underlying fire_event,
# we don't need to perform extensive testing.
@pytest.mark.slow_test
def test_send_master_event(sock_dir):
    """Tests that sending an event through fire_master generates expected event"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            data = {"data": "foo1"}
            me.fire_master(data, "test_master")

            evt = me.get_event(tag="fire_master")
            _assert_got_event(
                evt,
                {
                    "data": data,
                    "tag": "test_master",
                    "events": None,
                    "pretag": None,
                },
            )


def test_connect_pull_should_debug_log_on_StreamClosedError():
    event = SaltEvent(node=None)
    with patch.object(event, "pusher") as mock_pusher:
        with patch.object(
            salt.utils.event.log, "debug", autospec=True
        ) as mock_log_debug:
            mock_pusher.connect.side_effect = tornado.iostream.StreamClosedError
            event.connect_pull()
            call = mock_log_debug.mock_calls[0]
            assert call.args[0] == "Unable to connect pusher: %s"
            assert isinstance(call.args[1], tornado.iostream.StreamClosedError)
            assert call.args[1].args[0] == "Stream is closed"


@pytest.mark.parametrize("error", [Exception, KeyError, IOError])
def test_connect_pull_should_error_log_on_other_errors(error):
    event = SaltEvent(node=None)
    with patch.object(event, "pusher") as mock_pusher:
        with patch.object(
            salt.utils.event.log, "debug", autospec=True
        ) as mock_log_debug:
            with patch.object(
                salt.utils.event.log, "error", autospec=True
            ) as mock_log_error:
                mock_pusher.connect.side_effect = error
                event.connect_pull()
                mock_log_debug.assert_not_called()
                call = mock_log_error.mock_calls[0]
                assert call.args[0] == "Unable to connect pusher: %s"
                assert not isinstance(call.args[1], tornado.iostream.StreamClosedError)


@pytest.mark.slow_test
def test_master_pub_permissions(sock_dir):
    with eventpublisher_process(str(sock_dir)):
        p = Path(str(sock_dir)) / "master_event_pub.ipc"
        mode = os.lstat(p).st_mode
        assert bool(os.lstat(p).st_mode & stat.S_IRUSR)
        assert not bool(os.lstat(p).st_mode & stat.S_IRGRP)
        assert not bool(os.lstat(p).st_mode & stat.S_IROTH)


def test_event_unpack_with_SaltDeserializationError(sock_dir):
    with eventpublisher_process(str(sock_dir)), salt.utils.event.MasterEvent(
        str(sock_dir), listen=True
    ) as me, patch.object(
        salt.utils.event.log, "warning", autospec=True
    ) as mock_log_warning, patch.object(
        salt.utils.event.log, "error", autospec=True
    ) as mock_log_error:
        me.fire_event({"data": "foo1"}, "evt1")
        me.fire_event({"data": "foo2"}, "evt2")
        evt2 = me.get_event(tag="")
        with patch("salt.payload.loads", side_effect=SaltDeserializationError):
            evt1 = me.get_event(tag="")
        _assert_got_event(evt2, {"data": "foo2"}, expected_failure=True)
        assert evt1 is None
        assert (
            mock_log_warning.mock_calls[0].args[0]
            == "SaltDeserializationError on unpacking data, the payload could be incomplete"
        )
        assert (
            mock_log_error.mock_calls[0].args[0]
            == "Unable to deserialize received event"
        )


def test_event_fire_ret_load():
    event = SaltEvent(node=None)
    test_load = {
        "id": "minion_id.example.org",
        "jid": "20240212095247760376",
        "fun": "state.highstate",
        "retcode": 254,
        "return": {
            "saltutil_|-sync_states_|-sync_states_|-sync_states": {
                "result": True,
            },
            "saltutil_|-sync_modules_|-sync_modules_|-sync_modules": {
                "result": False,
            },
        },
    }
    test_fire_event_data = {
        "result": False,
        "retcode": 254,
        "jid": "20240212095247760376",
        "id": "minion_id.example.org",
        "success": False,
        "return": "Error: saltutil.sync_modules",
        "fun": "state.highstate",
    }
    test_unhandled_exc = "Unhandled exception running state.highstate"
    test_traceback = [
        "Traceback (most recent call last):\n",
        "    Just an example of possible return as a list\n",
    ]
    with patch.object(
        event, "fire_event", side_effect=[None, None, Exception]
    ) as mock_fire_event, patch.object(
        salt.utils.event.log, "error", autospec=True
    ) as mock_log_error:
        event.fire_ret_load(test_load)
        assert len(mock_fire_event.mock_calls) == 2
        assert mock_fire_event.mock_calls[0].args[0] == test_fire_event_data
        assert mock_fire_event.mock_calls[0].args[1] == "saltutil.sync_modules"
        assert mock_fire_event.mock_calls[1].args[0] == test_fire_event_data
        assert (
            mock_fire_event.mock_calls[1].args[1]
            == "salt/job/20240212095247760376/sub/minion_id.example.org/error/state.highstate"
        )
        assert not mock_log_error.mock_calls

        mock_log_error.reset_mock()

        event.fire_ret_load(test_load)
        assert (
            mock_log_error.mock_calls[0].args[0]
            == "Event from '%s' iteration failed with exception: %s"
        )
        assert mock_log_error.mock_calls[0].args[1] == "minion_id.example.org"

        mock_log_error.reset_mock()
        test_load["return"] = test_unhandled_exc

        event.fire_ret_load(test_load)
        assert (
            mock_log_error.mock_calls[0].args[0]
            == "Event with bad payload received from '%s': %s"
        )
        assert mock_log_error.mock_calls[0].args[1] == "minion_id.example.org"
        assert (
            mock_log_error.mock_calls[0].args[2]
            == "Unhandled exception running state.highstate"
        )

        mock_log_error.reset_mock()
        test_load["return"] = test_traceback

        event.fire_ret_load(test_load)
        assert (
            mock_log_error.mock_calls[0].args[0]
            == "Event with bad payload received from '%s': %s"
        )
        assert mock_log_error.mock_calls[0].args[1] == "minion_id.example.org"
        assert mock_log_error.mock_calls[0].args[2] == "".join(test_traceback)

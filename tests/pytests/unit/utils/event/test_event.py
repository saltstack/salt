import hashlib
import time

import pytest
import zmq.eventloop.ioloop

import salt.config
import salt.ext.tornado.ioloop
import salt.ext.tornado.iostream
import salt.utils.event
import salt.utils.stringutils
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
        assert key in evt, "{}: Key {} missing".format(msg, key)
        assertMsg = "{0}: Key {1} value mismatch, {2} != {3}"
        assertMsg = assertMsg.format(msg, key, data[key], evt[key])
        if not expected_failure:
            assert data[key] == evt[key], assertMsg
        else:
            assert data[key] != evt[key]


def test_master_event(sock_dir):
    with salt.utils.event.MasterEvent(str(sock_dir), listen=False) as me:
        assert me.puburi == str(sock_dir / "master_event_pub.ipc")
        assert me.pulluri == str(sock_dir / "master_event_pull.ipc")


def test_minion_event(sock_dir):
    opts = dict(id="foo", sock_dir=str(sock_dir))
    id_hash = hashlib.sha256(salt.utils.stringutils.to_bytes(opts["id"])).hexdigest()[
        :10
    ]
    with salt.utils.event.MinionEvent(opts, listen=False) as me:
        assert me.puburi == str(sock_dir / "minion_event_{}_pub.ipc".format(id_hash))
        assert me.pulluri == str(sock_dir / "minion_event_{}_pull.ipc".format(id_hash))


def test_minion_event_tcp_ipc_mode():
    opts = dict(id="foo", ipc_mode="tcp")
    with salt.utils.event.MinionEvent(opts, listen=False) as me:
        assert me.puburi == 4510
        assert me.pulluri == 4511


def test_minion_event_no_id(sock_dir):
    with salt.utils.event.MinionEvent(dict(sock_dir=str(sock_dir)), listen=False) as me:
        id_hash = hashlib.sha256(salt.utils.stringutils.to_bytes("")).hexdigest()[:10]
        assert me.puburi == str(sock_dir / "minion_event_{}_pub.ipc".format(id_hash))
        assert me.pulluri == str(sock_dir / "minion_event_{}_pull.ipc".format(id_hash))


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
                me.fire_event({"data": "{}".format(i)}, "testevents")
                evt = me.get_event(tag="testevents")
                _assert_got_event(evt, {"data": "{}".format(i)}, "Event {}".format(i))


@pytest.mark.slow_test
def test_event_many_backlog(sock_dir):
    """Test a large number of events, send all then recv all"""
    with eventpublisher_process(str(sock_dir)):
        with salt.utils.event.MasterEvent(str(sock_dir), listen=True) as me:
            # Must not exceed zmq HWM
            for i in range(500):
                me.fire_event({"data": "{}".format(i)}, "testevents")
            for i in range(500):
                evt = me.get_event(tag="testevents")
                _assert_got_event(evt, {"data": "{}".format(i)}, "Event {}".format(i))


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
            salt.utils.event.log, "debug", auto_spec=True
        ) as mock_log_debug:
            mock_pusher.connect.side_effect = (
                salt.ext.tornado.iostream.StreamClosedError
            )
            event.connect_pull()
            call = mock_log_debug.mock_calls[0]
            assert call.args[0] == "Unable to connect pusher: %s"
            assert isinstance(call.args[1], salt.ext.tornado.iostream.StreamClosedError)
            assert call.args[1].args[0] == "Stream is closed"


@pytest.mark.parametrize("error", [Exception, KeyError, IOError])
def test_connect_pull_should_error_log_on_other_errors(error):
    event = SaltEvent(node=None)
    with patch.object(event, "pusher") as mock_pusher:
        with patch.object(
            salt.utils.event.log, "debug", auto_spec=True
        ) as mock_log_debug:
            with patch.object(
                salt.utils.event.log, "error", auto_spec=True
            ) as mock_log_error:
                mock_pusher.connect.side_effect = error
                event.connect_pull()
                mock_log_debug.assert_not_called()
                call = mock_log_error.mock_calls[0]
                assert call.args[0] == "Unable to connect pusher: %s"
                assert not isinstance(
                    call.args[1], salt.ext.tornado.iostream.StreamClosedError
                )

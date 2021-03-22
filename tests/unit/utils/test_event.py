"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.utils.event_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import hashlib
import os
import shutil
import time

import pytest
import salt.config
import salt.ext.tornado.ioloop
import salt.utils.event
import salt.utils.stringutils
import zmq
import zmq.eventloop.ioloop
from salt.ext.tornado.testing import AsyncTestCase
from saltfactories.utils.processes import terminate_process
from tests.support.events import eventpublisher_process, eventsender_process
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, expectedFailure, skipIf

NO_LONG_IPC = False
if getattr(zmq, "IPC_PATH_MAX_LEN", 103) <= 103:
    NO_LONG_IPC = True


@skipIf(
    NO_LONG_IPC, "This system does not support long IPC paths. Skipping event tests!"
)
class TestSaltEvent(TestCase):
    def setUp(self):
        self.sock_dir = os.path.join(RUNTIME_VARS.TMP, "test-socks")
        if not os.path.exists(self.sock_dir):
            os.makedirs(self.sock_dir)
        self.addCleanup(shutil.rmtree, self.sock_dir, ignore_errors=True)

    def assertGotEvent(self, evt, data, msg=None):
        self.assertIsNotNone(evt, msg)
        for key in data:
            self.assertIn(key, evt, "{}: Key {} missing".format(msg, key))
            assertMsg = "{0}: Key {1} value mismatch, {2} != {3}"
            assertMsg = assertMsg.format(msg, key, data[key], evt[key])
            self.assertEqual(data[key], evt[key], assertMsg)

    def test_master_event(self):
        with salt.utils.event.MasterEvent(self.sock_dir, listen=False) as me:
            self.assertEqual(
                me.puburi,
                "{}".format(os.path.join(self.sock_dir, "master_event_pub.ipc")),
            )
            self.assertEqual(
                me.pulluri,
                "{}".format(os.path.join(self.sock_dir, "master_event_pull.ipc")),
            )

    def test_minion_event(self):
        opts = dict(id="foo", sock_dir=self.sock_dir)
        id_hash = hashlib.sha256(
            salt.utils.stringutils.to_bytes(opts["id"])
        ).hexdigest()[:10]
        with salt.utils.event.MinionEvent(opts, listen=False) as me:
            self.assertEqual(
                me.puburi,
                "{}".format(
                    os.path.join(
                        self.sock_dir, "minion_event_{}_pub.ipc".format(id_hash)
                    )
                ),
            )
            self.assertEqual(
                me.pulluri,
                "{}".format(
                    os.path.join(
                        self.sock_dir, "minion_event_{}_pull.ipc".format(id_hash)
                    )
                ),
            )

    def test_minion_event_tcp_ipc_mode(self):
        opts = dict(id="foo", ipc_mode="tcp")
        with salt.utils.event.MinionEvent(opts, listen=False) as me:
            self.assertEqual(me.puburi, 4510)
            self.assertEqual(me.pulluri, 4511)

    def test_minion_event_no_id(self):
        with salt.utils.event.MinionEvent(
            dict(sock_dir=self.sock_dir), listen=False
        ) as me:
            id_hash = hashlib.sha256(salt.utils.stringutils.to_bytes("")).hexdigest()[
                :10
            ]
            self.assertEqual(
                me.puburi,
                "{}".format(
                    os.path.join(
                        self.sock_dir, "minion_event_{}_pub.ipc".format(id_hash)
                    )
                ),
            )
            self.assertEqual(
                me.pulluri,
                "{}".format(
                    os.path.join(
                        self.sock_dir, "minion_event_{}_pull.ipc".format(id_hash)
                    )
                ),
            )

    @pytest.mark.slow_test
    def test_event_single(self):
        """Test a single event is received"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.fire_event({"data": "foo1"}, "evt1")
                evt1 = me.get_event(tag="evt1")
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_single_no_block(self):
        """Test a single event is received, no block"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                start = time.time()
                finish = start + 5
                evt1 = me.get_event(wait=0, tag="evt1", no_block=True)
                # We should get None and way before the 5 seconds wait since it's
                # non-blocking, otherwise it would wait for an event which we
                # didn't even send
                self.assertIsNone(evt1, None)
                self.assertLess(start, finish)
                me.fire_event({"data": "foo1"}, "evt1")
                evt1 = me.get_event(wait=0, tag="evt1")
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_single_wait_0_no_block_False(self):
        """Test a single event is received with wait=0 and no_block=False and doesn't spin the while loop"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.fire_event({"data": "foo1"}, "evt1")
                # This is too fast and will be None but assures we're not blocking
                evt1 = me.get_event(wait=0, tag="evt1", no_block=False)
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_timeout(self):
        """Test no event is received if the timeout is reached"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.fire_event({"data": "foo1"}, "evt1")
                evt1 = me.get_event(tag="evt1")
                self.assertGotEvent(evt1, {"data": "foo1"})
                evt2 = me.get_event(tag="evt1")
                self.assertIsNone(evt2)

    @pytest.mark.slow_test
    def test_event_no_timeout(self):
        """Test no wait timeout, we should block forever, until we get one """
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                with eventsender_process({"data": "foo2"}, "evt2", self.sock_dir, 5):
                    evt = me.get_event(tag="evt2", wait=0, no_block=False)
                self.assertGotEvent(evt, {"data": "foo2"})

    @pytest.mark.slow_test
    def test_event_matching(self):
        """Test a startswith match"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.fire_event({"data": "foo1"}, "evt1")
                evt1 = me.get_event(tag="ev")
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_matching_regex(self):
        """Test a regex match"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.fire_event({"data": "foo1"}, "evt1")
                evt1 = me.get_event(tag="^ev", match_type="regex")
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_matching_all(self):
        """Test an all match"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.fire_event({"data": "foo1"}, "evt1")
                evt1 = me.get_event(tag="")
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_matching_all_when_tag_is_None(self):
        """Test event matching all when not passing a tag"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.fire_event({"data": "foo1"}, "evt1")
                evt1 = me.get_event()
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_not_subscribed(self):
        """Test get_event drops non-subscribed events"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.fire_event({"data": "foo1"}, "evt1")
                me.fire_event({"data": "foo2"}, "evt2")
                evt2 = me.get_event(tag="evt2")
                evt1 = me.get_event(tag="evt1")
                self.assertGotEvent(evt2, {"data": "foo2"})
                self.assertIsNone(evt1)

    @pytest.mark.slow_test
    def test_event_subscription_cache(self):
        """Test subscriptions cache a message until requested"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.subscribe("evt1")
                me.fire_event({"data": "foo1"}, "evt1")
                me.fire_event({"data": "foo2"}, "evt2")
                evt2 = me.get_event(tag="evt2")
                evt1 = me.get_event(tag="evt1")
                self.assertGotEvent(evt2, {"data": "foo2"})
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_subscriptions_cache_regex(self):
        """Test regex subscriptions cache a message until requested"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.subscribe("e..1$", "regex")
                me.fire_event({"data": "foo1"}, "evt1")
                me.fire_event({"data": "foo2"}, "evt2")
                evt2 = me.get_event(tag="evt2")
                evt1 = me.get_event(tag="evt1")
                self.assertGotEvent(evt2, {"data": "foo2"})
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_multiple_clients(self):
        """Test event is received by multiple clients"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(
                self.sock_dir, listen=True
            ) as me1, salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me2:
                # We need to sleep here to avoid a race condition wherein
                # the second socket may not be connected by the time the first socket
                # sends the event.
                time.sleep(0.5)
                me1.fire_event({"data": "foo1"}, "evt1")
                evt1 = me1.get_event(tag="evt1")
                self.assertGotEvent(evt1, {"data": "foo1"})
                evt2 = me2.get_event(tag="evt1")
                self.assertGotEvent(evt2, {"data": "foo1"})

    @expectedFailure
    def test_event_nested_sub_all(self):
        """Test nested event subscriptions do not drop events, get event for all tags"""
        # Show why not to call get_event(tag='')
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                me.fire_event({"data": "foo1"}, "evt1")
                me.fire_event({"data": "foo2"}, "evt2")
                evt2 = me.get_event(tag="")
                evt1 = me.get_event(tag="")
                self.assertGotEvent(evt2, {"data": "foo2"})
                self.assertGotEvent(evt1, {"data": "foo1"})

    @pytest.mark.slow_test
    def test_event_many(self):
        """Test a large number of events, one at a time"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                for i in range(500):
                    me.fire_event({"data": "{}".format(i)}, "testevents")
                    evt = me.get_event(tag="testevents")
                    self.assertGotEvent(
                        evt, {"data": "{}".format(i)}, "Event {}".format(i)
                    )

    @pytest.mark.slow_test
    def test_event_many_backlog(self):
        """Test a large number of events, send all then recv all"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                # Must not exceed zmq HWM
                for i in range(500):
                    me.fire_event({"data": "{}".format(i)}, "testevents")
                for i in range(500):
                    evt = me.get_event(tag="testevents")
                    self.assertGotEvent(
                        evt, {"data": "{}".format(i)}, "Event {}".format(i)
                    )

    # Test the fire_master function. As it wraps the underlying fire_event,
    # we don't need to perform extensive testing.
    @pytest.mark.slow_test
    def test_send_master_event(self):
        """Tests that sending an event through fire_master generates expected event"""
        with eventpublisher_process(self.sock_dir):
            with salt.utils.event.MasterEvent(self.sock_dir, listen=True) as me:
                data = {"data": "foo1"}
                me.fire_master(data, "test_master")

                evt = me.get_event(tag="fire_master")
                self.assertGotEvent(
                    evt,
                    {
                        "data": data,
                        "tag": "test_master",
                        "events": None,
                        "pretag": None,
                    },
                )


class TestAsyncEventPublisher(AsyncTestCase):
    def get_new_ioloop(self):
        return salt.ext.tornado.ioloop.IOLoop()

    def setUp(self):
        super().setUp()
        self.sock_dir = os.path.join(RUNTIME_VARS.TMP, "test-socks")
        if not os.path.exists(self.sock_dir):
            os.makedirs(self.sock_dir)
        self.addCleanup(shutil.rmtree, self.sock_dir, ignore_errors=True)
        self.opts = {"sock_dir": self.sock_dir}
        self.publisher = salt.utils.event.AsyncEventPublisher(self.opts, self.io_loop,)
        self.event = salt.utils.event.get_event(
            "minion", opts=self.opts, io_loop=self.io_loop
        )
        self.event.subscribe("")
        self.event.set_event_handler(self._handle_publish)

    def stop(self, _arg=None, **kwargs):
        self.publisher.close()
        self.event.destroy()
        super().stop(_arg=_arg, **kwargs)

    def _handle_publish(self, raw):
        self.tag, self.data = salt.utils.event.SaltEvent.unpack(raw)
        self.stop()

    def test_event_subscription(self):
        """Test a single event is received"""
        with salt.utils.event.MinionEvent(self.opts, listen=True) as me:
            me.fire_event({"data": "foo1"}, "evt1")
            self.wait()
            evt1 = me.get_event(tag="evt1")
            self.assertEqual(self.tag, "evt1")
            self.data.pop("_stamp")  # drop the stamp
            self.assertEqual(self.data, {"data": "foo1"})

    def test_event_unsubscribe_remove_error(self):
        with salt.utils.event.MinionEvent(self.opts, listen=True) as me:
            tag = "evt1"
            me.fire_event({"data": "foo1"}, tag)

            # Make sure no remove error is raised when tag is not found
            for _ in range(2):
                me.unsubscribe(tag)

            me.unsubscribe("tag_does_not_exist")


class TestEventReturn(TestCase):
    @pytest.mark.slow_test
    def test_event_return(self):
        evt = None
        try:
            evt = salt.utils.event.EventReturn(salt.config.DEFAULT_MASTER_OPTS.copy())
            evt.start()
        except TypeError as exc:
            if "object" in str(exc):
                self.fail("'{}' TypeError should have not been raised".format(exc))
        finally:
            if evt is not None:
                terminate_process(evt.pid, kill_children=True)

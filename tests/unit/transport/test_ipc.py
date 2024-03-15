"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

import errno
import logging
import os
import threading

import pytest
import tornado.gen
import tornado.ioloop
import tornado.testing
from tornado.iostream import StreamClosedError

import salt.config
import salt.exceptions
import salt.transport.ipc
import salt.utils.platform
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.skip_on_darwin,
    pytest.mark.skip_on_freebsd,
    pytest.mark.skip_on_windows,
]

log = logging.getLogger(__name__)


@pytest.mark.skip_on_windows(reason="Windows does not support Posix IPC")
class IPCMessagePubSubCase(tornado.testing.AsyncTestCase):
    """
    Test all of the clear msg stuff
    """

    def setUp(self):
        super().setUp()
        self.opts = {"ipc_write_buffer": 0}
        if not os.path.exists(RUNTIME_VARS.TMP):
            os.mkdir(RUNTIME_VARS.TMP)
        self.socket_path = os.path.join(RUNTIME_VARS.TMP, "ipc_test.ipc")
        self.pub_channel = self._get_pub_channel()
        self.sub_channel = self._get_sub_channel()

    def _get_pub_channel(self):
        pub_channel = salt.transport.ipc.IPCMessagePublisher(
            self.opts,
            self.socket_path,
        )
        pub_channel.start()
        return pub_channel

    def _get_sub_channel(self):
        sub_channel = salt.transport.ipc.IPCMessageSubscriber(
            socket_path=self.socket_path,
            io_loop=self.io_loop,
        )
        sub_channel.connect(callback=self.stop)
        self.wait()
        return sub_channel

    def tearDown(self):
        super().tearDown()
        try:
            self.pub_channel.close()
        except RuntimeError as exc:
            pass
        except OSError as exc:
            if exc.errno != errno.EBADF:
                # If its not a bad file descriptor error, raise
                raise
        try:
            self.sub_channel.close()
        except RuntimeError as exc:
            pass
        except OSError as exc:
            if exc.errno != errno.EBADF:
                # If its not a bad file descriptor error, raise
                raise
        os.unlink(self.socket_path)
        del self.pub_channel
        del self.sub_channel

    def test_multi_client_reading(self):
        # To be completely fair let's create 2 clients.
        client1 = self.sub_channel
        client2 = self._get_sub_channel()
        call_cnt = []

        # Create a watchdog to be safe from hanging in sync loops (what old code did)
        evt = threading.Event()

        def close_server():
            if evt.wait(1):
                return
            client2.close()
            self.stop()

        watchdog = threading.Thread(target=close_server)
        watchdog.start()

        # Runs in ioloop thread so we're safe from race conditions here
        def handler(raw):
            call_cnt.append(raw)
            if len(call_cnt) >= 2:
                evt.set()
                self.stop()

        # Now let both waiting data at once
        client1.read_async(handler)
        client2.read_async(handler)
        self.pub_channel.publish("TEST")
        self.wait()
        self.assertEqual(len(call_cnt), 2)
        self.assertEqual(call_cnt[0], "TEST")
        self.assertEqual(call_cnt[1], "TEST")

    def test_sync_reading(self):
        # To be completely fair let's create 2 clients.
        client1 = self.sub_channel
        client2 = self._get_sub_channel()
        call_cnt = []

        # Now let both waiting data at once
        self.pub_channel.publish("TEST")
        ret1 = client1.read_sync()
        ret2 = client2.read_sync()
        self.assertEqual(ret1, "TEST")
        self.assertEqual(ret2, "TEST")

    @tornado.testing.gen_test
    def test_async_reading_streamclosederror(self):
        client1 = self.sub_channel
        call_cnt = []

        # Create a watchdog to be safe from hanging in sync loops (what old code did)
        evt = threading.Event()

        def close_server():
            if evt.wait(0.001):
                return
            client1.close()
            self.stop()

        watchdog = threading.Thread(target=close_server)
        watchdog.start()

        # Runs in ioloop thread so we're safe from race conditions here
        def handler(raw):
            pass

        try:
            ret1 = yield client1.read_async(handler)
            self.wait()
        except StreamClosedError as ex:
            assert False, "StreamClosedError was raised inside the Future"

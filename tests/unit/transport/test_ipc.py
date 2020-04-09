# -*- coding: utf-8 -*-
"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import errno
import logging
import os
import socket
import threading

import salt.config
import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.ext.tornado.testing
import salt.transport.client
import salt.transport.ipc
import salt.transport.server
import salt.utils.platform
from salt.ext import six
from salt.ext.six.moves import range
from tests.support.mock import MagicMock

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@skipIf(salt.utils.platform.is_windows(), "Windows does not support Posix IPC")
class BaseIPCReqCase(salt.ext.tornado.testing.AsyncTestCase):
    """
    Test the req server/client pair
    """

    def setUp(self):
        super(BaseIPCReqCase, self).setUp()
        # self._start_handlers = dict(self.io_loop._handlers)
        self.socket_path = os.path.join(RUNTIME_VARS.TMP, "ipc_test.ipc")

        self.server_channel = salt.transport.ipc.IPCMessageServer(
            self.socket_path,
            io_loop=self.io_loop,
            payload_handler=self._handle_payload,
        )
        self.server_channel.start()

        self.payloads = []

    def tearDown(self):
        super(BaseIPCReqCase, self).tearDown()
        # failures = []
        try:
            self.server_channel.close()
        except socket.error as exc:
            if exc.errno != errno.EBADF:
                # If its not a bad file descriptor error, raise
                raise
        os.unlink(self.socket_path)
        # for k, v in six.iteritems(self.io_loop._handlers):
        #    if self._start_handlers.get(k) != v:
        #        failures.append((k, v))
        # if len(failures) > 0:
        #    raise Exception('FDs still attached to the IOLoop: {0}'.format(failures))
        del self.payloads
        del self.socket_path
        del self.server_channel
        # del self._start_handlers

    @salt.ext.tornado.gen.coroutine
    def _handle_payload(self, payload, reply_func):
        self.payloads.append(payload)
        yield reply_func(payload)
        if isinstance(payload, dict) and payload.get("stop"):
            self.stop()


class IPCMessageClient(BaseIPCReqCase):
    """
    Test all of the clear msg stuff
    """

    def _get_channel(self):
        if not hasattr(self, "channel") or self.channel is None:
            self.channel = salt.transport.ipc.IPCMessageClient(
                socket_path=self.socket_path, io_loop=self.io_loop,
            )
            self.channel.connect(callback=self.stop)
            self.wait()
        return self.channel

    def setUp(self):
        super(IPCMessageClient, self).setUp()
        self.channel = self._get_channel()

    def tearDown(self):
        super(IPCMessageClient, self).tearDown()
        try:
            # Make sure we close no matter what we've done in the tests
            del self.channel
        except socket.error as exc:
            if exc.errno != errno.EBADF:
                # If its not a bad file descriptor error, raise
                raise
        finally:
            self.channel = None

    def test_singleton(self):
        channel = self._get_channel()
        assert self.channel is channel
        # Delete the local channel. Since there's still one more refefence
        # __del__ wasn't called
        del channel
        assert self.channel
        msg = {"foo": "bar", "stop": True}
        self.channel.send(msg)
        self.wait()
        self.assertEqual(self.payloads[0], msg)

    def test_basic_send(self):
        msg = {"foo": "bar", "stop": True}
        self.channel.send(msg)
        self.wait()
        self.assertEqual(self.payloads[0], msg)

    def test_many_send(self):
        msgs = []
        self.server_channel.stream_handler = MagicMock()

        for i in range(0, 1000):
            msgs.append("test_many_send_{0}".format(i))

        for i in msgs:
            self.channel.send(i)
        self.channel.send({"stop": True})
        self.wait()
        self.assertEqual(self.payloads[:-1], msgs)

    def test_very_big_message(self):
        long_str = "".join([six.text_type(num) for num in range(10 ** 5)])
        msg = {"long_str": long_str, "stop": True}
        self.channel.send(msg)
        self.wait()
        self.assertEqual(msg, self.payloads[0])

    def test_multistream_sends(self):
        local_channel = self._get_channel()

        for c in (self.channel, local_channel):
            c.send("foo")

        self.channel.send({"stop": True})
        self.wait()
        self.assertEqual(self.payloads[:-1], ["foo", "foo"])

    def test_multistream_errors(self):
        local_channel = self._get_channel()

        for c in (self.channel, local_channel):
            c.send(None)

        for c in (self.channel, local_channel):
            c.send("foo")

        self.channel.send({"stop": True})
        self.wait()
        self.assertEqual(self.payloads[:-1], [None, None, "foo", "foo"])


@skipIf(salt.utils.platform.is_windows(), "Windows does not support Posix IPC")
class IPCMessagePubSubCase(salt.ext.tornado.testing.AsyncTestCase):
    """
    Test all of the clear msg stuff
    """

    def setUp(self):
        super(IPCMessagePubSubCase, self).setUp()
        self.opts = {"ipc_write_buffer": 0}
        self.socket_path = os.path.join(RUNTIME_VARS.TMP, "ipc_test.ipc")
        self.pub_channel = self._get_pub_channel()
        self.sub_channel = self._get_sub_channel()

    def _get_pub_channel(self):
        pub_channel = salt.transport.ipc.IPCMessagePublisher(
            self.opts, self.socket_path,
        )
        pub_channel.start()
        return pub_channel

    def _get_sub_channel(self):
        sub_channel = salt.transport.ipc.IPCMessageSubscriber(
            socket_path=self.socket_path, io_loop=self.io_loop,
        )
        sub_channel.connect(callback=self.stop)
        self.wait()
        return sub_channel

    def tearDown(self):
        super(IPCMessagePubSubCase, self).tearDown()
        try:
            self.pub_channel.close()
        except socket.error as exc:
            if exc.errno != errno.EBADF:
                # If its not a bad file descriptor error, raise
                raise
        try:
            self.sub_channel.close()
        except socket.error as exc:
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

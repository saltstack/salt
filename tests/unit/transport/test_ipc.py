# -*- coding: utf-8 -*-
'''
    :codeauthor: Mike Place <mp@saltstack.com>
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import errno
import socket
import logging

import tornado.gen
import tornado.ioloop
import tornado.testing

import salt.config
import salt.exceptions
import salt.transport.ipc
import salt.transport.server
import salt.transport.client
import salt.utils.platform

from salt.ext import six
from salt.ext.six.moves import range

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.mock import MagicMock
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@skipIf(salt.utils.platform.is_windows(), 'Windows does not support Posix IPC')
class BaseIPCReqCase(tornado.testing.AsyncTestCase):
    '''
    Test the req server/client pair
    '''
    def setUp(self):
        super(BaseIPCReqCase, self).setUp()
        #self._start_handlers = dict(self.io_loop._handlers)
        self.socket_path = os.path.join(RUNTIME_VARS.TMP, 'ipc_test.ipc')

        self.server_channel = salt.transport.ipc.IPCMessageServer(
            salt.config.master_config(None),
            self.socket_path,
            io_loop=self.io_loop,
            payload_handler=self._handle_payload,
        )
        self.server_channel.start()

        self.payloads = []

    def tearDown(self):
        super(BaseIPCReqCase, self).tearDown()
        #failures = []
        try:
            self.server_channel.close()
        except socket.error as exc:
            if exc.errno != errno.EBADF:
                # If its not a bad file descriptor error, raise
                raise
        os.unlink(self.socket_path)
        #for k, v in six.iteritems(self.io_loop._handlers):
        #    if self._start_handlers.get(k) != v:
        #        failures.append((k, v))
        #if len(failures) > 0:
        #    raise Exception('FDs still attached to the IOLoop: {0}'.format(failures))
        del self.payloads
        del self.socket_path
        del self.server_channel
        #del self._start_handlers

    @tornado.gen.coroutine
    def _handle_payload(self, payload, reply_func):
        self.payloads.append(payload)
        yield reply_func(payload)
        if isinstance(payload, dict) and payload.get('stop'):
            self.stop()


class IPCMessageClient(BaseIPCReqCase):
    '''
    Test all of the clear msg stuff
    '''

    def _get_channel(self):
        channel = salt.transport.ipc.IPCMessageClient(
            socket_path=self.socket_path,
            io_loop=self.io_loop,
        )
        channel.connect(callback=self.stop)
        self.wait()
        return channel

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

    def test_singleton(self):
        channel = self._get_channel()
        assert self.channel is channel
        # Delete the local channel. Since there's still one more refefence
        # __del__ wasn't called
        del channel
        assert self.channel
        msg = {'foo': 'bar', 'stop': True}
        self.channel.send(msg)
        self.wait()
        self.assertEqual(self.payloads[0], msg)

    def test_last_singleton_instance_closes(self):
        channel = self._get_channel()
        msg = {'foo': 'bar', 'stop': True}
        log.debug('Sending msg1')
        self.channel.send(msg)
        self.wait()
        self.assertEqual(self.payloads[0], msg)
        channel.close()
        # Since this is a singleton, and only the last singleton instance
        # should actually close the connection, the next code should still
        # work and not timeout
        msg = {'bar': 'foo', 'stop': True}
        log.debug('Sending msg2')
        self.channel.send(msg)
        self.wait()
        self.assertEqual(self.payloads[1], msg)

    def test_basic_send(self):
        msg = {'foo': 'bar', 'stop': True}
        self.channel.send(msg)
        self.wait()
        self.assertEqual(self.payloads[0], msg)

    def test_many_send(self):
        msgs = []
        self.server_channel.stream_handler = MagicMock()

        for i in range(0, 1000):
            msgs.append('test_many_send_{0}'.format(i))

        for i in msgs:
            self.channel.send(i)
        self.channel.send({'stop': True})
        self.wait()
        self.assertEqual(self.payloads[:-1], msgs)

    def test_very_big_message(self):
        long_str = ''.join([six.text_type(num) for num in range(10**5)])
        msg = {'long_str': long_str, 'stop': True}
        self.channel.send(msg)
        self.wait()
        self.assertEqual(msg, self.payloads[0])

    def test_multistream_sends(self):
        local_channel = self._get_channel()

        for c in (self.channel, local_channel):
            c.send('foo')

        self.channel.send({'stop': True})
        self.wait()
        self.assertEqual(self.payloads[:-1], ['foo', 'foo'])

    def test_multistream_errors(self):
        local_channel = self._get_channel()

        for c in (self.channel, local_channel):
            c.send(None)

        for c in (self.channel, local_channel):
            c.send('foo')

        self.channel.send({'stop': True})
        self.wait()
        self.assertEqual(self.payloads[:-1], [None, None, 'foo', 'foo'])

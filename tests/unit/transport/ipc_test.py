# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import os
import logging

import tornado.gen
import tornado.ioloop
import tornado.testing

import salt.utils
import salt.config
import salt.exceptions
import salt.transport.ipc
import salt.transport.server
import salt.transport.client

from salt.ext.six.moves import range

# Import Salt Testing libs
import integration

from salttesting.mock import MagicMock
from salttesting.helpers import ensure_in_syspath

log = logging.getLogger(__name__)

ensure_in_syspath('../')


class BaseIPCReqCase(tornado.testing.AsyncTestCase):
    '''
    Test the req server/client pair
    '''
    def setUp(self):
        super(BaseIPCReqCase, self).setUp()
        self._start_handlers = dict(self.io_loop._handlers)
        self.socket_path = os.path.join(integration.TMP, 'ipc_test.ipc')

        self.server_channel = salt.transport.ipc.IPCMessageServer(
            self.socket_path,
            io_loop=self.io_loop,
            payload_handler=self._handle_payload,
        )
        self.server_channel.start()

        self.payloads = []

    def tearDown(self):
        super(BaseIPCReqCase, self).tearDown()
        failures = []
        self.server_channel.close()
        os.unlink(self.socket_path)
        for k, v in self.io_loop._handlers.iteritems():
            if self._start_handlers.get(k) != v:
                failures.append((k, v))
        if len(failures) > 0:
            raise Exception('FDs still attached to the IOLoop: {0}'.format(failures))

    @tornado.gen.coroutine
    def _handle_payload(self, payload, reply_func):
        self.payloads.append(payload)
        yield reply_func(payload)
        if isinstance(payload, dict) and payload.get('stop'):
            self.stop()

class IPCMessageClientTests(BaseIPCReqCase):
    '''
    Test for the IPCMessageClient
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
        super(IPCMessageClientTests, self).setUp()
        self.channel = self._get_channel()

    def tearDown(self):
        super(IPCMessageClientTests, self).setUp()
        self.channel.close()

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
        long_str = ''.join([str(num) for num in range(10**5)])
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


class IPCSubscribeClientTests(BaseIPCReqCase):
    '''
    Tests for IPCSubscribeClient
    '''
    def _get_channel(self):
        channel = salt.transport.ipc.IPCSubscribeClient(
            socket_path=self.socket_path,
            io_loop=self.io_loop,
        )
        channel.connect(callback=self.stop)
        self.wait()
        return channel

    def setUp(self):
        super(IPCSubscribeClientTests, self).setUp()
        self.channel = self._get_channel()
        self.channel.subscribe(self._get_handler(self.payloads))

    def tearDown(self):
        super(IPCSubscribeClientTests, self).setUp()
        self.channel.close()

    def _get_handler(self, payloads):
        def handler(body):
            payloads.append(body)
            if isinstance(body, dict) and body.get('stop', False):
                self.stop()
        return handler

    def test_basic(self):
        self.server_channel.publish({'stop': True})
        self.wait()
        self.assertEqual({'stop': True}, self.payloads[0])

    def test_many_send(self):
        msgs = []
        for i in range(0, 1000):
            msgs.append('test_many_send_{0}'.format(i))

        for i in msgs:
            self.server_channel.publish(i)
        self.server_channel.publish({'stop': True})
        self.wait()
        self.assertEqual(self.payloads[:-1], msgs)

    def test_very_big_message(self):
        long_str = ''.join([str(num) for num in range(10**5)])
        msg = {'long_str': long_str, 'stop': True}
        self.server_channel.publish(msg)
        self.wait()
        self.assertEqual(msg, self.payloads[0])

    def test_multi_subscriber(self):
        local_client = self._get_channel()
        local_payloads = []
        local_client.subscribe(self._get_handler(local_payloads))

        msgs = []
        for i in range(0, 1000):
            msgs.append('test_many_send_{0}'.format(i))

        for i in msgs:
            self.server_channel.publish(i)
        self.server_channel.publish({'stop': True})
        self.wait()
        self.assertEqual(self.payloads[:-1], msgs)
        self.assertEqual(local_payloads[:-1], msgs)

    def test_multi_subscriber_unsubscribe(self):
        local_client = self._get_channel()
        local_payloads = []
        local_handler = self._get_handler(local_payloads)
        local_client.subscribe(local_handler)

        msg = {'stop': True}

        self.server_channel.publish(msg)
        self.wait()
        self.assertEqual(self.payloads, [msg])
        self.assertEqual(local_payloads, [msg])
        local_client.unsubscribe(local_handler)
        self.server_channel.publish(msg)
        self.wait()
        self.assertEqual(self.payloads, [msg, msg])
        self.assertEqual(local_payloads, [msg])

    def test_multi_subscriber_close(self):
        local_client = self._get_channel()
        local_payloads = []
        local_handler = self._get_handler(local_payloads)
        local_client.subscribe(local_handler)

        msg = {'stop': True}

        self.server_channel.publish(msg)
        self.wait()
        self.assertEqual(self.payloads, [msg])
        self.assertEqual(local_payloads, [msg])
        local_client.close()
        self.server_channel.publish(msg)
        # make sure the callbacks aren't called
        with self.assertRaises(AssertionError):
            self.wait()
        # ensure no new messages arrived
        self.assertEqual(self.payloads, [msg])
        self.assertEqual(local_payloads, [msg])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(IPCMessageClient, needs_daemon=False)

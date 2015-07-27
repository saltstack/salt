# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import os
import time
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

from salttesting.helpers import ensure_in_syspath

log = logging.getLogger(__name__)

ensure_in_syspath('../')


class BaseIPCCase(tornado.testing.AsyncTestCase):
    '''
    Test the req server/client pair
    '''
    def setUp(self):
        super(BaseIPCCase, self).setUp()
        self._start_handlers = dict(self.io_loop._handlers)
        self.socket_path = os.path.join(integration.TMP, 'ipc_test.ipc')
        self.ipc_url = 'ipc://{0}'.format(self.socket_path)

        self.server_channel = salt.transport.ipc.IPCMessageServer(
            self.ipc_url,
            io_loop=self.io_loop,
            payload_handler=self._handle_payload,
        )
        self.server_channel.start()

        self.payloads = []

    def tearDown(self):
        super(BaseIPCCase, self).tearDown()
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
        if isinstance(payload, dict) and payload.get('sleep'):
            yield tornado.gen.sleep(payload['sleep'])
        yield reply_func(payload)
        if isinstance(payload, dict) and payload.get('stop'):
            self.stop()


class IPCClientSendTests(BaseIPCCase):
    '''
    Test for the IPCClient
    '''
    def _get_channel(self):
        channel = salt.transport.ipc.IPCClient(
            ipc_url=self.ipc_url,
            io_loop=self.io_loop,
        )
        channel.connect(callback=self.stop)
        self.wait()
        return channel

    def setUp(self):
        super(IPCClientSendTests, self).setUp()
        self.channel = self._get_channel()

    def tearDown(self):
        super(IPCClientSendTests, self).setUp()
        self.channel.close()

    @tornado.testing.gen_test
    def test_basic_send(self):
        msg = {'foo': 'bar'}
        ret = yield self.channel.send(msg)
        self.assertEqual(self.payloads[0], msg)
        self.assertEqual(ret, msg)

    @tornado.testing.gen_test
    def test_send_maxflight(self):
        '''
        Send more messages than maxflight, and then ensure that we actually rate
        limit requests
        '''
        sleep_interval = 0.2
        total_messages = self.channel.maxflight * 4
        expected_total_time = sleep_interval * (total_messages / self.channel.maxflight)

        msg = {'foo': 'bar', 'sleep': sleep_interval}
        start = time.time()
        futures = []
        for x in xrange(0, total_messages):
            futures.append(self.channel.send(msg))

        rets = yield futures
        duration = time.time()

        self.assertGreaterEqual(duration, expected_total_time)
        self.assertEqual(self.payloads, rets)

    @tornado.testing.gen_test
    def test_many_send(self):
        msgs = []
        for i in range(0, 1000):
            msgs.append('test_many_send_{0}'.format(i))

        futures = []
        for i in msgs:
            futures.append(self.channel.send(i))
        # wait until the last one is finished
        yield futures[-1:]
        self.assertEqual(self.payloads, msgs)
        for i, f in enumerate(futures):
            r = yield f
            self.assertEqual(r, msgs[i])

    @tornado.testing.gen_test
    def test_very_big_message(self):
        long_str = ''.join([str(num) for num in range(10**5)])
        msg = {'long_str': long_str}
        ret = yield self.channel.send(msg)
        self.assertEqual(msg, self.payloads[0])
        self.assertEqual(msg, ret)

    def test_multistream_sends(self):
        local_channel = self._get_channel()

        for c in (self.channel, local_channel):
            c.send('foo')

        self.channel.send({'stop': True})
        self.wait()
        local_channel.send({'stop': True})
        self.wait()

        self.assertEqual(self.payloads.count('foo'), 2)

    def test_multistream_errors(self):
        local_channel = self._get_channel()

        for c in (self.channel, local_channel):
            c.send(None)

        for c in (self.channel, local_channel):
            c.send('foo')

        self.channel.send({'stop': True})
        self.wait()
        local_channel.send({'stop': True})
        self.wait()
        self.assertEqual(self.payloads.count('foo'), 2)
        self.assertEqual(self.payloads.count(None), 2)


class IPCClientSubscribeTests(BaseIPCCase):
    '''
    Test for the IPCClient
    '''
    def _get_channel(self):
        channel = salt.transport.ipc.IPCClient(
            ipc_url=self.ipc_url,
            io_loop=self.io_loop,
        )
        channel.connect(callback=self.stop)
        self.wait()
        return channel

    def setUp(self):
        super(IPCClientSubscribeTests, self).setUp()
        self.channel = self._get_channel()
        self.channel.subscribe()

    def tearDown(self):
        super(IPCClientSubscribeTests, self).setUp()
        self.channel.close()

    @tornado.testing.gen_test
    def test_basic(self):
        self.server_channel.publish('foo')
        msg = yield self.channel.recv()
        self.assertEqual('foo', msg)

    @tornado.testing.gen_test
    def test_many_send(self):
        msgs = []
        for i in range(0, 1000):
            msgs.append('test_many_send_{0}'.format(i))

        for i in msgs:
            self.server_channel.publish(i)

        for i in msgs:
            m = yield self.channel.recv()
            self.assertEqual(m, i)

    @tornado.testing.gen_test
    def test_very_big_message(self):
        long_str = ''.join([str(num) for num in range(10**5)])
        msg = {'long_str': long_str}
        self.server_channel.publish(msg)
        recv_msg = yield self.channel.recv()
        self.assertEqual(msg, recv_msg)

    def test_multi_subscriber(self):
        '''
        '''
        local_client = self._get_channel()
        local_payloads = []
        local_client.subscribe()

        msgs = []
        for i in range(0, 1000):
            msgs.append('test_many_send_{0}'.format(i))

        for i in msgs:
            self.server_channel.publish(i)

        recvd_msgs = set()
        for i in range(0, 500):
            one = self.channel.recv()
            two = self.channel.recv()
            one.add_done_callback(self.stop)
            self.wait()
            recvd_msgs.add(one.result())
            two.add_done_callback(self.stop)
            self.wait()
            recvd_msgs.add(two.result())

        self.assertEqual(set(msgs), recvd_msgs)


class IPCClientPublishTests(BaseIPCCase):
    '''
    Test for the IPCClient
    '''
    def _get_channel(self):
        channel = salt.transport.ipc.IPCClient(
            ipc_url=self.ipc_url,
            io_loop=self.io_loop,
        )
        channel.connect(callback=self.stop)
        self.wait()
        return channel

    def setUp(self):
        super(IPCClientPublishTests, self).setUp()
        self.channel = self._get_channel()

    def tearDown(self):
        super(IPCClientPublishTests, self).setUp()
        self.channel.close()

    def test_basic(self):
        self.channel.publish({'stop': True})
        self.wait()
        self.assertEqual({'stop': True}, self.payloads[0])

    def test_many_publish(self):
        msgs = []
        for i in range(0, 1000):
            msgs.append('test_many_send_{0}'.format(i))

        for i in msgs:
            self.channel.publish(i)
        self.channel.publish({'stop': True})
        self.wait()
        self.assertEqual(self.payloads[:-1], msgs)

    def test_very_big_message(self):
        long_str = ''.join([str(num) for num in range(10**5)])
        msg = {'long_str': long_str, 'stop': True}
        self.channel.publish(msg)
        self.wait()
        self.assertEqual(msg, self.payloads[0])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(IPCClientSendTests, needs_daemon=False)
    run_tests(IPCClientSubscribeTests, needs_daemon=False)

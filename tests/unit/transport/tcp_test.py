# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Thomas Jackson <jacksontj.89@gmail.com>`
'''

# Import python libs
from __future__ import absolute_import
import os
import threading

import tornado.gen
import tornado.ioloop
import tornado.concurrent
from tornado.testing import AsyncTestCase, gen_test

import salt.config
import salt.ext.six as six
import salt.utils
import salt.transport.server
import salt.transport.client
import salt.exceptions
from salt.ext.six.moves import range
from salt.transport.tcp import SaltMessageClientPool

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../')
import integration

# Import Salt libs
from unit.transport.req_test import ReqChannelMixin
from unit.transport.pub_test import PubChannelMixin


# TODO: move to a library?
def get_config_file_path(filename):
    return os.path.join(integration.TMP, 'config', filename)


class BaseTCPReqCase(TestCase):
    '''
    Test the req server/client pair
    '''
    @classmethod
    def setUpClass(cls):
        if not hasattr(cls, '_handle_payload'):
            return
        cls.master_opts = salt.config.master_config(get_config_file_path('master'))
        cls.master_opts.update({
            'transport': 'tcp',
            'auto_accept': True,
        })

        cls.minion_opts = salt.config.minion_config(get_config_file_path('minion'))
        cls.minion_opts.update({
            'transport': 'tcp',
            'master_uri': 'tcp://127.0.0.1:{0}'.format(cls.minion_opts['master_port']),
        })

        cls.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        cls.server_channel = salt.transport.server.ReqServerChannel.factory(cls.master_opts)
        cls.server_channel.pre_fork(cls.process_manager)

        cls.io_loop = tornado.ioloop.IOLoop()
        cls.io_loop.make_current()
        cls.server_channel.post_fork(cls._handle_payload, io_loop=cls.io_loop)

        cls.server_thread = threading.Thread(target=cls.io_loop.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, '_handle_payload'):
            return
        cls.io_loop.stop()
        cls.server_thread.join()
        cls.process_manager.kill_children()
        cls.server_channel.close()
        del cls.server_channel

    @classmethod
    @tornado.gen.coroutine
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        raise tornado.gen.Return((payload, {'fun': 'send_clear'}))


@skipIf(salt.utils.is_darwin(), 'hanging test suite on MacOS')
class ClearReqTestCases(BaseTCPReqCase, ReqChannelMixin):
    '''
    Test all of the clear msg stuff
    '''
    def setUp(self):
        self.channel = salt.transport.client.ReqChannel.factory(self.minion_opts, crypt='clear')

    def tearDown(self):
        del self.channel

    @classmethod
    @tornado.gen.coroutine
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        raise tornado.gen.Return((payload, {'fun': 'send_clear'}))


@skipIf(salt.utils.is_darwin(), 'hanging test suite on MacOS')
class AESReqTestCases(BaseTCPReqCase, ReqChannelMixin):
    def setUp(self):
        self.channel = salt.transport.client.ReqChannel.factory(self.minion_opts)

    def tearDown(self):
        del self.channel

    @classmethod
    @tornado.gen.coroutine
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        raise tornado.gen.Return((payload, {'fun': 'send'}))

    # TODO: make failed returns have a specific framing so we can raise the same exception
    # on encrypted channels
    def test_badload(self):
        '''
        Test a variety of bad requests, make sure that we get some sort of error
        '''
        msgs = ['', [], tuple()]
        for msg in msgs:
            with self.assertRaises(salt.exceptions.AuthenticationError):
                ret = self.channel.send(msg)


class BaseTCPPubCase(AsyncTestCase):
    '''
    Test the req server/client pair
    '''
    @classmethod
    def setUpClass(cls):
        cls.master_opts = salt.config.master_config(get_config_file_path('master'))
        cls.master_opts.update({
            'transport': 'tcp',
            'auto_accept': True,
        })

        cls.minion_opts = salt.config.minion_config(get_config_file_path('minion'))
        cls.minion_opts.update({
            'transport': 'tcp',
            'master_ip': '127.0.0.1',
            'auth_timeout': 1,
            'master_uri': 'tcp://127.0.0.1:{0}'.format(cls.minion_opts['master_port']),
        })

        cls.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        cls.server_channel = salt.transport.server.PubServerChannel.factory(cls.master_opts)
        cls.server_channel.pre_fork(cls.process_manager)

        # we also require req server for auth
        cls.req_server_channel = salt.transport.server.ReqServerChannel.factory(cls.master_opts)
        cls.req_server_channel.pre_fork(cls.process_manager)

        cls._server_io_loop = tornado.ioloop.IOLoop()
        cls.req_server_channel.post_fork(cls._handle_payload, io_loop=cls._server_io_loop)

        cls.server_thread = threading.Thread(target=cls._server_io_loop.start)
        cls.server_thread.start()

    @classmethod
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        return payload, {'fun': 'send_clear'}

    @classmethod
    def tearDownClass(cls):
        cls._server_io_loop.stop()
        cls.server_thread.join()
        cls.process_manager.kill_children()
        cls.req_server_channel.close()
        del cls.req_server_channel

    def setUp(self):
        super(BaseTCPPubCase, self).setUp()
        self._start_handlers = dict(self.io_loop._handlers)

    def tearDown(self):
        super(BaseTCPPubCase, self).tearDown()
        failures = []
        for k, v in six.iteritems(self.io_loop._handlers):
            if self._start_handlers.get(k) != v:
                failures.append((k, v))
        if len(failures) > 0:
            raise Exception('FDs still attached to the IOLoop: {0}'.format(failures))


@skipIf(True, 'Skip until we can devote time to fix this test')
class AsyncPubChannelTest(BaseTCPPubCase, PubChannelMixin):
    '''
    Tests around the publish system
    '''


class SaltMessageClientPoolTest(AsyncTestCase):
    def setUp(self):
        super(SaltMessageClientPoolTest, self).setUp()
        sock_pool_size = 5
        with patch('salt.transport.tcp.SaltMessageClient.__init__', MagicMock(return_value=None)):
            self.message_client_pool = SaltMessageClientPool({'sock_pool_size': sock_pool_size},
                                                             args=({}, '', 0))
        self.original_message_clients = self.message_client_pool.message_clients
        self.message_client_pool.message_clients = [MagicMock() for _ in range(sock_pool_size)]

    def tearDown(self):
        with patch('salt.transport.tcp.SaltMessageClient.close', MagicMock(return_value=None)):
            del self.original_message_clients
        super(SaltMessageClientPoolTest, self).tearDown()

    def test_send(self):
        for message_client_mock in self.message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock.send.return_value = []
        self.assertEqual([], self.message_client_pool.send())
        self.message_client_pool.message_clients[2].send_queue = [0]
        self.message_client_pool.message_clients[2].send.return_value = [1]
        self.assertEqual([1], self.message_client_pool.send())

    def test_write_to_stream(self):
        for message_client_mock in self.message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock._stream.write.return_value = []
        self.assertEqual([], self.message_client_pool.write_to_stream(''))
        self.message_client_pool.message_clients[2].send_queue = [0]
        self.message_client_pool.message_clients[2]._stream.write.return_value = [1]
        self.assertEqual([1], self.message_client_pool.write_to_stream(''))

    def test_close(self):
        self.message_client_pool.close()
        self.assertEqual([], self.message_client_pool.message_clients)

    def test_on_recv(self):
        for message_client_mock in self.message_client_pool.message_clients:
            message_client_mock.on_recv.return_value = None
        self.message_client_pool.on_recv()
        for message_client_mock in self.message_client_pool.message_clients:
            self.assertTrue(message_client_mock.on_recv.called)

    def test_connect_all(self):
        @gen_test
        def test_connect(self):
            yield self.message_client_pool.connect()

        for message_client_mock in self.message_client_pool.message_clients:
            future = tornado.concurrent.Future()
            future.set_result('foo')
            message_client_mock.connect.return_value = future

        self.assertIsNone(test_connect(self))

    def test_connect_partial(self):
        @gen_test(timeout=0.1)
        def test_connect(self):
            yield self.message_client_pool.connect()

        for idx, message_client_mock in enumerate(self.message_client_pool.message_clients):
            future = tornado.concurrent.Future()
            if idx % 2 == 0:
                future.set_result('foo')
            message_client_mock.connect.return_value = future

        with self.assertRaises(tornado.ioloop.TimeoutError):
            test_connect(self)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ClearReqTestCases, needs_daemon=False)
    run_tests(AESReqTestCases, needs_daemon=False)

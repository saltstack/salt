# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Thomas Jackson <jacksontj.89@gmail.com>`
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import time
import threading

# linux_distribution deprecated in py3.7
try:
    from platform import linux_distribution
except ImportError:
    from distro import linux_distribution

# Import 3rd-party libs
import zmq.eventloop.ioloop
# support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
    zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
from tornado.testing import AsyncTestCase
import tornado.gen

# Import Salt libs
import salt.config
from salt.ext import six
import salt.utils.process
import salt.transport.server
import salt.transport.client
import salt.exceptions
from salt.ext.six.moves import range
from salt.transport.zeromq import AsyncReqMessageClientPool

# Import test support libs
from tests.support.paths import TMP_CONF_DIR
from tests.support.unit import TestCase, skipIf
from tests.support.helpers import flaky, get_unused_localhost_port
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, patch
from tests.unit.transport.mixins import PubChannelMixin, ReqChannelMixin

ON_SUSE = False
if 'SuSE' in linux_distribution(full_distribution_name=False):
    ON_SUSE = True


class BaseZMQReqCase(TestCase, AdaptedConfigurationTestCaseMixin):
    '''
    Test the req server/client pair
    '''
    @classmethod
    def setUpClass(cls):
        if not hasattr(cls, '_handle_payload'):
            return
        ret_port = get_unused_localhost_port()
        publish_port = get_unused_localhost_port()
        tcp_master_pub_port = get_unused_localhost_port()
        tcp_master_pull_port = get_unused_localhost_port()
        tcp_master_publish_pull = get_unused_localhost_port()
        tcp_master_workers = get_unused_localhost_port()
        cls.master_config = cls.get_temp_config(
            'master',
            **{'transport': 'zeromq',
               'auto_accept': True,
               'ret_port': ret_port,
               'publish_port': publish_port,
               'tcp_master_pub_port': tcp_master_pub_port,
               'tcp_master_pull_port': tcp_master_pull_port,
               'tcp_master_publish_pull': tcp_master_publish_pull,
               'tcp_master_workers': tcp_master_workers}
        )

        cls.minion_config = cls.get_temp_config(
            'minion',
            **{'transport': 'zeromq',
               'master_ip': '127.0.0.1',
               'master_port': ret_port,
               'auth_timeout': 5,
               'auth_tries': 1,
               'master_uri': 'tcp://127.0.0.1:{0}'.format(ret_port)}
        )

        cls.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        cls.server_channel = salt.transport.server.ReqServerChannel.factory(cls.master_config)
        cls.server_channel.pre_fork(cls.process_manager)

        cls.io_loop = zmq.eventloop.ioloop.ZMQIOLoop()
        cls.io_loop.make_current()
        cls.server_channel.post_fork(cls._handle_payload, io_loop=cls.io_loop)

        cls.server_thread = threading.Thread(target=cls.io_loop.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, '_handle_payload'):
            return
        # Attempting to kill the children hangs the test suite.
        # Let the test suite handle this instead.
        cls.process_manager.stop_restarting()
        cls.process_manager.kill_children()
        cls.io_loop.add_callback(cls.io_loop.stop)
        cls.server_thread.join()
        time.sleep(2)  # Give the procs a chance to fully close before we stop the io_loop
        cls.server_channel.close()
        del cls.server_channel
        del cls.io_loop
        del cls.process_manager
        del cls.server_thread
        del cls.master_config
        del cls.minion_config

    @classmethod
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        return payload, {'fun': 'send_clear'}


class ClearReqTestCases(BaseZMQReqCase, ReqChannelMixin):
    '''
    Test all of the clear msg stuff
    '''
    def setUp(self):
        self.channel = salt.transport.client.ReqChannel.factory(self.minion_config, crypt='clear')

    def tearDown(self):
        del self.channel

    @classmethod
    @tornado.gen.coroutine
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        raise tornado.gen.Return((payload, {'fun': 'send_clear'}))


@flaky
@skipIf(ON_SUSE, 'Skipping until https://github.com/saltstack/salt/issues/32902 gets fixed')
class AESReqTestCases(BaseZMQReqCase, ReqChannelMixin):
    def setUp(self):
        self.channel = salt.transport.client.ReqChannel.factory(self.minion_config)

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
    #
    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    #
    # WARNING: This test will fail randomly on any system with > 1 CPU core!!!
    #
    #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    def test_badload(self):
        '''
        Test a variety of bad requests, make sure that we get some sort of error
        '''
        # TODO: This test should be re-enabled when Jenkins moves to C7.
        # Once the version of salt-testing is increased to something newer than the September
        # release of salt-testing, the @flaky decorator should be applied to this test.
        msgs = ['', [], tuple()]
        for msg in msgs:
            with self.assertRaises(salt.exceptions.AuthenticationError):
                ret = self.channel.send(msg, timeout=5)


class BaseZMQPubCase(AsyncTestCase, AdaptedConfigurationTestCaseMixin):
    '''
    Test the req server/client pair
    '''
    @classmethod
    def setUpClass(cls):
        ret_port = get_unused_localhost_port()
        publish_port = get_unused_localhost_port()
        tcp_master_pub_port = get_unused_localhost_port()
        tcp_master_pull_port = get_unused_localhost_port()
        tcp_master_publish_pull = get_unused_localhost_port()
        tcp_master_workers = get_unused_localhost_port()
        cls.master_config = cls.get_temp_config(
            'master',
            **{'transport': 'zeromq',
               'auto_accept': True,
               'ret_port': ret_port,
               'publish_port': publish_port,
               'tcp_master_pub_port': tcp_master_pub_port,
               'tcp_master_pull_port': tcp_master_pull_port,
               'tcp_master_publish_pull': tcp_master_publish_pull,
               'tcp_master_workers': tcp_master_workers}
        )

        cls.minion_config = salt.config.minion_config(os.path.join(TMP_CONF_DIR, 'minion'))
        cls.minion_config = cls.get_temp_config(
            'minion',
            **{'transport': 'zeromq',
               'master_ip': '127.0.0.1',
               'master_port': ret_port,
               'master_uri': 'tcp://127.0.0.1:{0}'.format(ret_port)}
        )

        cls.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        cls.server_channel = salt.transport.server.PubServerChannel.factory(cls.master_config)
        cls.server_channel.pre_fork(cls.process_manager)

        # we also require req server for auth
        cls.req_server_channel = salt.transport.server.ReqServerChannel.factory(cls.master_config)
        cls.req_server_channel.pre_fork(cls.process_manager)

        cls._server_io_loop = zmq.eventloop.ioloop.ZMQIOLoop()
        cls.req_server_channel.post_fork(cls._handle_payload, io_loop=cls._server_io_loop)

        cls.server_thread = threading.Thread(target=cls._server_io_loop.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.process_manager.kill_children()
        cls.process_manager.stop_restarting()
        time.sleep(2)  # Give the procs a chance to fully close before we stop the io_loop
        cls.io_loop.add_callback(cls.io_loop.stop)
        cls.server_thread.join()
        cls.req_server_channel.close()
        cls.server_channel.close()
        cls._server_io_loop.stop()
        del cls.server_channel
        del cls._server_io_loop
        del cls.process_manager
        del cls.server_thread
        del cls.master_config
        del cls.minion_config

    @classmethod
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        return payload, {'fun': 'send_clear'}

    def setUp(self):
        super(BaseZMQPubCase, self).setUp()
        self._start_handlers = dict(self.io_loop._handlers)

    def tearDown(self):
        super(BaseZMQPubCase, self).tearDown()
        failures = []
        for k, v in six.iteritems(self.io_loop._handlers):
            if self._start_handlers.get(k) != v:
                failures.append((k, v))
        del self._start_handlers
        if len(failures) > 0:
            raise Exception('FDs still attached to the IOLoop: {0}'.format(failures))


@skipIf(True, 'Skip until we can devote time to fix this test')
class AsyncPubChannelTest(BaseZMQPubCase, PubChannelMixin):
    '''
    Tests around the publish system
    '''
    def get_new_ioloop(self):
        return zmq.eventloop.ioloop.ZMQIOLoop()


class AsyncReqMessageClientPoolTest(TestCase):
    def setUp(self):
        super(AsyncReqMessageClientPoolTest, self).setUp()
        sock_pool_size = 5
        with patch('salt.transport.zeromq.AsyncReqMessageClient.__init__', MagicMock(return_value=None)):
            self.message_client_pool = AsyncReqMessageClientPool({'sock_pool_size': sock_pool_size},
                                                                 args=({}, ''))
        self.original_message_clients = self.message_client_pool.message_clients
        self.message_client_pool.message_clients = [MagicMock() for _ in range(sock_pool_size)]

    def tearDown(self):
        with patch('salt.transport.zeromq.AsyncReqMessageClient.destroy', MagicMock(return_value=None)):
            del self.original_message_clients
        super(AsyncReqMessageClientPoolTest, self).tearDown()

    def test_send(self):
        for message_client_mock in self.message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock.send.return_value = []

        self.assertEqual([], self.message_client_pool.send())

        self.message_client_pool.message_clients[2].send_queue = [0]
        self.message_client_pool.message_clients[2].send.return_value = [1]
        self.assertEqual([1], self.message_client_pool.send())

    def test_destroy(self):
        self.message_client_pool.destroy()
        self.assertEqual([], self.message_client_pool.message_clients)

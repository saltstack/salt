# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Thomas Jackson <jacksontj.89@gmail.com>`
'''

# Import python libs
from __future__ import absolute_import
import os
import time
import threading
import platform

# Import 3rd-party libs
import zmq.eventloop.ioloop
# support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
    zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
from tornado.testing import AsyncTestCase
import tornado.gen

# Import Salt libs
import salt.config
import salt.ext.six as six
import salt.utils
import salt.transport.server
import salt.transport.client
import salt.exceptions

# Import test support libs
import tests.integration as integration
from tests.support.helpers import flaky
from tests.support.unit import TestCase, skipIf
from tests.unit.transport.test_req import ReqChannelMixin
from tests.unit.transport.test_pub import PubChannelMixin

ON_SUSE = False
if 'SuSE' in platform.dist():
    ON_SUSE = True


# TODO: move to a library?
def get_config_file_path(filename):
    return os.path.join(integration.TMP, 'config', filename)


class BaseZMQReqCase(TestCase):
    '''
    Test the req server/client pair
    '''
    @classmethod
    def setUpClass(cls):
        if not hasattr(cls, '_handle_payload'):
            return
        cls.master_opts = salt.config.master_config(get_config_file_path('master'))
        cls.master_opts.update({
            'transport': 'zeromq',
            'auto_accept': True,
        })

        cls.minion_opts = salt.config.minion_config(get_config_file_path('minion'))
        cls.minion_opts.update({
            'transport': 'zeromq',
            'auth_timeout': 5,
            'auth_tries': 1,
            'master_uri': 'tcp://127.0.0.1:{0}'.format(cls.minion_opts['master_port']),
        })

        cls.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        cls.server_channel = salt.transport.server.ReqServerChannel.factory(cls.master_opts)
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
        time.sleep(2)  # Give the procs a chance to fully close before we stop the io_loop
        cls.io_loop.stop()
        cls.server_channel.close()
        del cls.server_channel
        del cls.io_loop
        del cls.process_manager
        del cls.server_thread
        del cls.master_opts
        del cls.minion_opts

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


@flaky
@skipIf(ON_SUSE, 'Skipping until https://github.com/saltstack/salt/issues/32902 gets fixed')
class AESReqTestCases(BaseZMQReqCase, ReqChannelMixin):
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


class BaseZMQPubCase(AsyncTestCase):
    '''
    Test the req server/client pair
    '''
    @classmethod
    def setUpClass(cls):
        cls.master_opts = salt.config.master_config(get_config_file_path('master'))
        cls.master_opts.update({
            'transport': 'zeromq',
            'auto_accept': True,
        })

        cls.minion_opts = salt.config.minion_config(get_config_file_path('minion'))
        cls.minion_opts.update({
            'transport': 'zeromq',
            'master_ip': '127.0.0.1',
            'master_uri': 'tcp://127.0.0.1:{0}'.format(cls.minion_opts['master_port']),
        })

        cls.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        cls.server_channel = salt.transport.server.PubServerChannel.factory(cls.master_opts)
        cls.server_channel.pre_fork(cls.process_manager)

        # we also require req server for auth
        cls.req_server_channel = salt.transport.server.ReqServerChannel.factory(cls.master_opts)
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
        cls.req_server_channel.close()
        cls.server_channel.close()
        cls._server_io_loop.stop()
        del cls.server_channel
        del cls._server_io_loop
        del cls.process_manager
        del cls.server_thread
        del cls.master_opts
        del cls.minion_opts

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

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
from tornado.testing import AsyncTestCase

import salt.config
import salt.utils
import salt.transport.server
import salt.transport.client
import salt.exceptions

# Import Salt Testing libs
from salttesting import TestCase
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
        cls.server_channel.post_fork(cls._handle_payload, io_loop=cls.io_loop)

        cls.server_thread = threading.Thread(target=cls.io_loop.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.io_loop.stop()
        cls.server_thread.join()
        cls.process_manager.kill_children()
        cls.server_channel.close()
        del cls.server_channel


class ClearReqTestCases(BaseTCPReqCase, ReqChannelMixin):
    '''
    Test all of the clear msg stuff
    '''
    def setUp(self):
        self.channel = salt.transport.client.ReqChannel.factory(self.minion_opts, crypt='clear')

    @classmethod
    @tornado.gen.coroutine
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        raise tornado.gen.Return((payload, {'fun': 'send_clear'}))


class AESReqTestCases(BaseTCPReqCase, ReqChannelMixin):
    def setUp(self):
        self.channel = salt.transport.client.ReqChannel.factory(self.minion_opts)

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
        for k, v in self.io_loop._handlers.iteritems():
            if self._start_handlers.get(k) != v:
                failures.append((k, v))
        if len(failures) > 0:
            raise Exception('FDs still attached to the IOLoop: {0}'.format(failures))


class AsyncPubChannelTest(BaseTCPPubCase, PubChannelMixin):
    '''
    Tests around the publish system
    '''

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ClearReqTestCases, needs_daemon=False)
    run_tests(AESReqTestCases, needs_daemon=False)

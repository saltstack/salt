# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Thomas Jackson <jacksontj.89@gmail.com>`
'''

# Import python libs
from __future__ import absolute_import
import os
import threading

import tornado.ioloop
from tornado.testing import AsyncTestCase

import salt.config
import salt.utils
import salt.transport.server
import salt.transport.client
import salt.exceptions

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.runtests import RUNTIME_VARS
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../')

# Import Salt libs
from salt import client
from salt.exceptions import EauthAuthenticationError, SaltInvocationError

from unit.transport.req_test import ReqChannelMixin

# TODO: move to a library?
def get_config_file_path(filename):
    return os.path.join(RUNTIME_VARS.TMP_CONF_DIR, filename)

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
        cls.minion_opts.update(salt.config.client_config(get_config_file_path('minion')))
        cls.minion_opts['transport'] = 'tcp'

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
        cls.process_manager.kill_children()
        cls.io_loop.stop()
        cls.server_channel.close()


class ClearReqTestCases(BaseTCPReqCase, ReqChannelMixin):
    '''
    Test all of the clear msg stuff
    '''
    def setUp(self):
        self.channel = channel = salt.transport.client.ReqChannel.factory(self.minion_opts, crypt='clear')

    @classmethod
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        return payload, {'fun': 'send_clear'}


class AESReqTestCases(BaseTCPReqCase, ReqChannelMixin):
    def setUp(self):
        self.channel = channel = salt.transport.client.ReqChannel.factory(self.minion_opts)

    @classmethod
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        return payload, {'fun': 'send'}

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
        cls.minion_opts.update(salt.config.client_config(get_config_file_path('minion')))
        cls.minion_opts.update({
            'transport': 'tcp',
            'master_ip': '127.0.0.1',
            'auth_timeout': 1,
        })

        cls.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        cls.server_channel = salt.transport.server.PubServerChannel.factory(cls.master_opts)
        cls.server_channel.pre_fork(cls.process_manager)

        # we also require req server for auth
        cls.req_server_channel = salt.transport.server.ReqServerChannel.factory(cls.master_opts)
        cls.req_server_channel.pre_fork(cls.process_manager)

        cls.io_loop = tornado.ioloop.IOLoop()
        cls.req_server_channel.post_fork(cls._handle_payload, io_loop=cls.io_loop)

        cls.server_thread = threading.Thread(target=cls.io_loop.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def _handle_payload(cls, payload):
        '''
        TODO: something besides echo
        '''
        return payload, {'fun': 'send_clear'}

    @classmethod
    def tearDownClass(cls):
        cls.process_manager.kill_children()
        cls.io_loop.stop()
        #cls.server_channel.close()


class PubChannelTest(BaseTCPPubCase):
    '''
    Tests around the publish system
    '''
    def test_basic(self):
        self.pub = None
        def handle_pub(ret):
            self.pub = ret
            self.stop()
        self.pub_channel = salt.transport.client.PubChannel.factory(self.minion_opts, io_loop=self.io_loop)
        connect_future = self.pub_channel.connect()
        connect_future.add_done_callback(lambda f: self.stop())
        self.wait()
        connect_future.result()
        self.pub_channel.on_recv(handle_pub)
        load = {
                    'fun': 'f',
                    'arg': 'a',
                    'tgt': 't',
                    'jid': 'j',
                    'ret': 'r',
                    'tgt_type': 'glob',
                }
        self.server_channel.publish(load)
        self.wait()
        self.assertEqual(self.pub['load'], load)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ClearReqTestCases, needs_daemon=False)
    run_tests(AESReqTestCases, needs_daemon=False)



##

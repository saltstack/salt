# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Thomas Jackson <jacksontj.89@gmail.com>`
'''

# Import python libs
from __future__ import absolute_import
import os
import threading

import zmq.eventloop.ioloop
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
from unit.transport.pub_test import PubChannelMixin

# TODO: move to a library?
def get_config_file_path(filename):
    return os.path.join(RUNTIME_VARS.TMP_CONF_DIR, filename)

class BaseZMQReqCase(TestCase):
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
        cls.minion_opts.update(salt.config.client_config(get_config_file_path('minion')))
        cls.minion_opts.update({
            'transport': 'zeromq',
            'auth_timeout': 5,
            'auth_tries': 1,
        })

        cls.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        cls.server_channel = salt.transport.server.ReqServerChannel.factory(cls.master_opts)
        cls.server_channel.pre_fork(cls.process_manager)

        cls.io_loop = zmq.eventloop.ioloop.ZMQIOLoop()
        cls.server_channel.post_fork(cls._handle_payload, io_loop=cls.io_loop)

        cls.server_thread = threading.Thread(target=cls.io_loop.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.process_manager.kill_children()
        cls.io_loop.stop()
        cls.server_channel.close()


class ClearReqTestCases(BaseZMQReqCase, ReqChannelMixin):
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


class AESReqTestCases(BaseZMQReqCase, ReqChannelMixin):
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
        cls.minion_opts.update(salt.config.client_config(get_config_file_path('minion')))
        cls.minion_opts.update({
            'transport': 'zeromq',
            'master_ip': '127.0.0.1',
        })

        cls.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        cls.server_channel = salt.transport.server.PubServerChannel.factory(cls.master_opts)
        cls.server_channel.pre_fork(cls.process_manager)

        # we also require req server for auth
        cls.req_server_channel = salt.transport.server.ReqServerChannel.factory(cls.master_opts)
        cls.req_server_channel.pre_fork(cls.process_manager)

        cls.io_loop = zmq.eventloop.ioloop.ZMQIOLoop()
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
        cls.req_server_channel.close()


class AsyncPubChannelTest(BaseZMQPubCase, PubChannelMixin, TestCase):
    '''
    Tests around the publish system
    '''
    def get_new_ioloop(self):
        return  zmq.eventloop.ioloop.ZMQIOLoop()


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ClearReqTestCases, needs_daemon=False)
    run_tests(AESReqTestCases, needs_daemon=False)



##

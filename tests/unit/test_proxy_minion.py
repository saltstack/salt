# -*- coding: utf-8 -*-
'''
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
'''

# Import python libs
from __future__ import absolute_import
import copy

import logging
import salt.ext.tornado
import salt.ext.tornado.testing

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import patch, MagicMock

# Import salt libs
import salt.minion
import salt.syspaths
import salt.metaproxy.proxy


log = logging.getLogger(__name__)
__opts__ = {}


class ProxyMinionTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    def test_post_master_init_metaproxy_called(self):
        '''
        Tests that when the _post_master_ini function is called, _metaproxy_call is also called.
        '''
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_jid_queue = [123]
        proxy_minion = salt.minion.ProxyMinion(mock_opts, jid_queue=copy.copy(mock_jid_queue), io_loop=salt.ext.tornado.ioloop.IOLoop())
        try:
            ret = proxy_minion._post_master_init('dummy_master')
            self.assert_called_once(salt.minion._metaproxy_call)
        finally:
            proxy_minion.destroy()

    def test_handle_decoded_payload_metaproxy_called(self):
        '''
        Tests that when the _handle_decoded_payload function is called, _metaproxy_call is also called.
        '''
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_data = {'fun': 'foo.bar',
                     'jid': 123}
        mock_jid_queue = [123]
        proxy_minion = salt.minion.ProxyMinion(mock_opts, jid_queue=copy.copy(mock_jid_queue), io_loop=salt.ext.tornado.ioloop.IOLoop())
        try:
            ret = proxy_minion._handle_decoded_payload(mock_data).result()
            self.assertEqual(proxy_minion.jid_queue, mock_jid_queue)
            self.assertIsNone(ret)
            self.assert_called_once(salt.minion._metaproxy_call)
        finally:
            proxy_minion.destroy()

    def test_handle_payload_metaproxy_called(self):
        '''
        Tests that when the _handle_payload function is called, _metaproxy_call is also called.
        '''
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_data = {'fun': 'foo.bar',
                     'jid': 123}
        mock_jid_queue = [123]
        proxy_minion = salt.minion.ProxyMinion(mock_opts, jid_queue=copy.copy(mock_jid_queue), io_loop=salt.ext.tornado.ioloop.IOLoop())
        try:
            ret = proxy_minion._handle_decoded_payload(mock_data).result()
            self.assertEqual(proxy_minion.jid_queue, mock_jid_queue)
            self.assertIsNone(ret)
            self.assert_called_once(salt.minion._metaproxy_call)
        finally:
            proxy_minion.destroy()

    def test_metaproxy_ack_event_single(self):
        mock_opts = self.get_config('minion', from_scratch=True)
        mock_opts["acknowledge_jobs"] = True
        mock_opts["return"] = None

        minion = MagicMock()
        minion.opts = mock_opts
        minion.connected = False

        with patch('os.path.join'), patch('salt.utils.files.fopen'), patch('salt.utils.process.appendproctitle'):
            salt.metaproxy.proxy.thread_return(salt.minion.ProxyMinion, minion, mock_opts, {"jid": "test-jid", "fun": "test.ping", "arg": [], "ret": None})
            minion._fire_master.assert_called_with(tag="salt/job/test-jid/ack/{0}".format(mock_opts["id"]))

    def test_metaproxy_ack_event_single_disabled(self):
        mock_opts = self.get_config('minion', from_scratch=True)
        mock_opts["acknowledge_jobs"] = False
        mock_opts["return"] = None

        minion = MagicMock()
        minion.opts = mock_opts
        minion.connected = False

        with patch('os.path.join'), patch('salt.utils.files.fopen'), patch('salt.utils.process.appendproctitle'):
            salt.metaproxy.proxy.thread_return(salt.minion.ProxyMinion, minion, mock_opts, {"jid": "test-jid", "fun": "test.ping", "arg": [], "ret": None})
            with self.assertRaises(AssertionError):
                minion._fire_master.assert_called_with(tag="salt/job/test-jid/ack/{0}".format(mock_opts["id"]))

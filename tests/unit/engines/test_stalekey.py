# -*- coding: utf-8 -*-
'''
unit tests for the stalekey engine
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import tempfile
import msgpack

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    mock_open,
    patch)

# Import Salt Libs
import salt.engines.stalekey as stalekey
import salt.config

log = logging.getLogger(__name__)


class MockKey(object):
    def __init__(self, opts):
        pass

    def delete_key(self, key):
        pass


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EngineStalekeyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.engine.sqs_events
    '''

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MASTER_OPTS
        self.opts['id'] = 'master'

        return {stalekey: {'__opts__': self.opts}}

    def test_start(self):
        '''
        Test to ensure start works
        '''
        presence_file = {'foo': '', 'bar': ''}
        connected_ids = {'foo': '', 'bar': '', 'baz': ''}
        stale_key = ['foo']

        with patch('salt.engines.stalekey._running', side_effect=[True, False]):
            with patch('salt.engines.stalekey._read_presence', return_value=presence_file):
                with patch('salt.utils.minions.CkMinions.connected_ids', return_value=connected_ids):
                    with patch('salt.engines.stalekey._delete_keys', return_value=connected_ids):
                        with patch('salt.engines.stalekey._write_presence', return_value=False):
                            with patch('time.sleep', return_value=None):
                                ret = stalekey.start()
        self.assertTrue(True)

    def test_delete_keysTrue(self):
        '''
        Test to ensure single stale key is deleted
        '''
        _minions = {'foo': '', 'bar': '', 'baz': ''}
        stale_key = ['foo']

        with patch('salt.key.get_key', return_value=MockKey(self.opts)):
            ret = stalekey._delete_keys(stale_key, _minions)
        expected = {'bar': '', 'baz': ''}
        self.assertEqual(ret, expected)

    def test_delete_keys_multiple_stale_keys(self):
        '''
        Test to ensure multiple stale keys are deleted
        '''
        _minions = {'foo': '', 'bar': '', 'baz': ''}
        stale_keys = ['foo', 'bar']

        with patch('salt.key.get_key', return_value=MockKey(self.opts)):
            ret = stalekey._delete_keys(stale_keys, _minions)
        expected = {'baz': ''}
        self.assertEqual(ret, expected)

    def test_read_presence(self):
        '''
        Test to ensure we can read from a presence file
        '''
        data = {'minion': 1572049887.15425}
        msgpack_data = msgpack.dumps(data)
        with patch('os.path.exists', return_value=True):
            with patch('salt.utils.files.fopen',
                       mock_open(read_data=msgpack_data)) as dummy_file:
                ret = stalekey._read_presence('presence.p')
        expected = (False, {'minion': 1572049887.15425})
        self.assertEqual(ret, expected)

    def test_write_presence(self):
        '''
        Test to ensure we can read from a presence file
        '''
        minions = {'minion': 1572049887.15425}
        with patch('salt.utils.files.fopen',
                   mock_open()) as dummy_file:
            ret = stalekey._write_presence('presence.p', minions)
        expected = False
        self.assertEqual(ret, expected)

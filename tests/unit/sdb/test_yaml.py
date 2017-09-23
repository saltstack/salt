# -*- coding: utf-8 -*-
'''
Test case for the YAML SDB module
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt libs
import salt.sdb.yaml as sdb
from salt.exceptions import SaltRenderError


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestYamlRenderer(TestCase):
    '''
    Test case for the YAML SDB module
    '''

    def test_simple(self):
        '''
        Retrieve a value from the top level of the dictionary
        '''
        plain = {'foo': 'bar'}
        crypt = {'foo': 'secretbar'}
        with patch('salt.renderers.gpg.render', MagicMock(return_value=plain)):
            with patch('salt.sdb.yaml._get_values', MagicMock(return_value=crypt)):
                self.assertEqual(sdb.get('foo'), 'bar')

    def test_nested(self):
        '''
        Retrieve a value from a nested level of the dictionary
        '''
        plain = {'foo': {'bar': 'baz'}}
        crypt = {'foo': {'bar': 'secretbaz'}}
        with patch('salt.renderers.gpg.render', MagicMock(return_value=plain)):
            with patch('salt.sdb.yaml._get_values', MagicMock(return_value=crypt)):
                self.assertEqual(sdb.get('foo:bar'), 'baz')

    def test_gpg_error(self):
        '''
        Assume the content is plaintext if GPG is not configured
        '''
        plain = {'foo': 'bar'}
        with patch('salt.renderers.gpg.render', MagicMock(side_effect=SaltRenderError('failed'))):
            with patch('salt.sdb.yaml._get_values', MagicMock(return_value=plain)):
                self.assertEqual(sdb.get('foo'), 'bar')

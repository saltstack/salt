# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.varnish as varnish


@skipIf(NO_MOCK, NO_MOCK_REASON)
class VarnishTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.varnish
    '''
    def setup_loader_modules(self):
        return {varnish: {}}

    def test_version(self):
        '''
        Test to return server version from varnishd -V
        '''
        with patch.dict(varnish.__salt__,
                        {'cmd.run': MagicMock(return_value='(varnish-2.0)')}):
            self.assertEqual(varnish.version(), '2.0')

    def test_ban(self):
        '''
        Test to add ban to the varnish cache
        '''
        with patch.object(varnish, '_run_varnishadm',
                          return_value={'retcode': 0}):
            self.assertTrue(varnish.ban('ban_expression'))

    def test_ban_list(self):
        '''
        Test to list varnish cache current bans
        '''
        with patch.object(varnish, '_run_varnishadm',
                          return_value={'retcode': True}):
            self.assertFalse(varnish.ban_list())

        with patch.object(varnish, '_run_varnishadm',
                          return_value={'retcode': False,
                                        'stdout': 'A\nB\nC'}):
            self.assertEqual(varnish.ban_list(), ['B', 'C'])

    def test_purge(self):
        '''
        Test to purge the varnish cache
        '''
        with patch.object(varnish, 'ban', return_value=True):
            self.assertTrue(varnish.purge())

    def test_param_set(self):
        '''
        Test to set a param in varnish cache
        '''
        with patch.object(varnish, '_run_varnishadm',
                          return_value={'retcode': 0}):
            self.assertTrue(varnish.param_set('param', 'value'))

    def test_param_show(self):
        '''
        Test to show params of varnish cache
        '''
        with patch.object(varnish, '_run_varnishadm',
                          return_value={'retcode': True,
                                        'stdout': 'A\nB\nC'}):
            self.assertFalse(varnish.param_show('param'))

        with patch.object(varnish, '_run_varnishadm',
                          return_value={'retcode': False,
                                        'stdout': 'A .1\nB .2\n'}):
            self.assertEqual(varnish.param_show('param'), {'A': '.1'})

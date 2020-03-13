# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import (
    patch,
)

# Import Salt Libs
import salt.modules.pecl as pecl


class PeclTestCase(TestCase):
    '''
    Test cases for salt.modules.pecl
    '''
    def test_install(self):
        '''
        Test to installs one or several pecl extensions.
        '''
        with patch.object(pecl, '_pecl', return_value='A'):
            assert pecl.install('fuse', force=True) == 'A'

            assert not pecl.install('fuse')

            with patch.object(pecl, 'list_', return_value={'A': ['A', 'B']}):
                assert pecl.install(['A', 'B'])

    def test_uninstall(self):
        '''
        Test to uninstall one or several pecl extensions.
        '''
        with patch.object(pecl, '_pecl', return_value='A'):
            assert pecl.uninstall('fuse') == 'A'

    def test_update(self):
        '''
        Test to update one or several pecl extensions.
        '''
        with patch.object(pecl, '_pecl', return_value='A'):
            assert pecl.update('fuse') == 'A'

    def test_list_(self):
        '''
        Test to list installed pecl extensions.
        '''
        with patch.object(pecl, '_pecl', return_value='A\nB'):
            assert pecl.list_('channel') == {}

# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import pecl


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PeclTestCase(TestCase):
    '''
    Test cases for salt.modules.pecl
    '''
    def test_install(self):
        '''
        Test to installs one or several pecl extensions.
        '''
        with patch.object(pecl, '_pecl', return_value='A'):
            self.assertEqual(pecl.install('fuse', force=True), 'A')

            self.assertFalse(pecl.install('fuse'))

            with patch.object(pecl, 'list_', return_value={'A': ['A', 'B']}):
                self.assertTrue(pecl.install(['A', 'B']))

    def test_uninstall(self):
        '''
        Test to uninstall one or several pecl extensions.
        '''
        with patch.object(pecl, '_pecl', return_value='A'):
            self.assertEqual(pecl.uninstall('fuse'), 'A')

    def test_update(self):
        '''
        Test to update one or several pecl extensions.
        '''
        with patch.object(pecl, '_pecl', return_value='A'):
            self.assertEqual(pecl.update('fuse'), 'A')

    def test_list_(self):
        '''
        Test to list installed pecl extensions.
        '''
        with patch.object(pecl, '_pecl', return_value='A\nB'):
            self.assertDictEqual(pecl.list_('channel'), {})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PeclTestCase, needs_daemon=False)

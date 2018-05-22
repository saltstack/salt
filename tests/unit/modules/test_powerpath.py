# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.powerpath as powerpath


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PowerpathTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.powerpath
    '''
    def setup_loader_modules(self):
        return {powerpath: {}}

    def test_has_powerpath(self):
        '''
        Test for powerpath
        '''
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            self.assertTrue(powerpath.has_powerpath())

            mock_exists.return_value = False
            self.assertFalse(powerpath.has_powerpath())

    def test_list_licenses(self):
        '''
        Test to returns a list of applied powerpath license keys
        '''
        with patch.dict(powerpath.__salt__,
                        {'cmd.run': MagicMock(return_value='A\nB')}):
            self.assertListEqual(powerpath.list_licenses(), [])

    def test_add_license(self):
        '''
        Test to add a license
        '''
        with patch.object(powerpath, 'has_powerpath', return_value=False):
            self.assertDictEqual(powerpath.add_license('key'),
                                 {'output': 'PowerPath is not installed',
                                  'result': False, 'retcode': -1})

        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'stderr'})
        with patch.object(powerpath, 'has_powerpath', return_value=True):
            with patch.dict(powerpath.__salt__, {'cmd.run_all': mock}):
                self.assertDictEqual(powerpath.add_license('key'),
                                     {'output': 'stderr', 'result': False,
                                      'retcode': 1})

    def test_remove_license(self):
        '''
        Test to remove a license
        '''
        with patch.object(powerpath, 'has_powerpath', return_value=False):
            self.assertDictEqual(powerpath.remove_license('key'),
                                 {'output': 'PowerPath is not installed',
                                  'result': False, 'retcode': -1})

        mock = MagicMock(return_value={'retcode': 1, 'stderr': 'stderr'})
        with patch.object(powerpath, 'has_powerpath', return_value=True):
            with patch.dict(powerpath.__salt__, {'cmd.run_all': mock}):
                self.assertDictEqual(powerpath.remove_license('key'),
                                     {'output': 'stderr', 'result': False,
                                      'retcode': 1})

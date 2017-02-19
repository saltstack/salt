# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import powerpath

# Globals
powerpath.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PowerpathTestCase(TestCase):
    '''
    Test cases for salt.modules.powerpath
    '''
    @patch('os.path.exists')
    def test_has_powerpath(self, mock_exists):
        '''
        Test for powerpath
        '''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PowerpathTestCase, needs_daemon=False)

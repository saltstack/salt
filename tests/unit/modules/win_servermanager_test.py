# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import win_servermanager

# Globals
win_servermanager.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinServermanagerTestCase(TestCase):
    '''
    Test cases for salt.modules.win_servermanager
    '''
    @staticmethod
    def _m_run():
        '''
        Mock return value for cmd.run
        '''
        return MagicMock(return_value='')

    # 'list_available' function tests: 1

    def test_list_available(self):
        '''
        Test if it list available features to install.
        '''
        with patch.dict(win_servermanager.__salt__, {'cmd.run': self._m_run()}):
            self.assertEqual(win_servermanager.list_available(), '')

    # 'list_installed' function tests: 1

    def test_list_installed(self):
        '''
        Test if it list installed features.
        '''
        with patch.dict(win_servermanager.__salt__, {'cmd.run': self._m_run()}):
            self.assertDictEqual(win_servermanager.list_installed(), {})

    # 'install' function tests: 1

    def test_install(self):
        '''
        Test if it install a feature.
        '''
        with patch.dict(win_servermanager.__salt__, {'cmd.run': self._m_run()}):
            self.assertDictEqual(win_servermanager.install('Telnet-Client'), {
                'message': ''
            })

    # 'remove' function tests: 1

    def test_remove(self):
        '''
        Test if it remove an installed feature.
        '''
        with patch.dict(win_servermanager.__salt__, {'cmd.run': self._m_run()}):
            self.assertDictEqual(win_servermanager.remove('Telnet-Client'), {
                'message': ''
            })


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinServermanagerTestCase, needs_daemon=False)

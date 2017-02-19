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
from salt.modules import znc

znc.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZncTestCase(TestCase):
    '''
    TestCase for salt.modules.znc
    '''
    # 'buildmod' function tests: 1

    @patch('os.path.exists', MagicMock(return_value=False))
    def test_buildmod(self):
        '''
        Tests build module using znc-buildmod
        '''
        self.assertEqual(znc.buildmod('modules.cpp'),
                         'Error: The file (modules.cpp) does not exist.')

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_buildmod_module(self):
        '''
        Tests build module using znc-buildmod
        '''
        mock = MagicMock(return_value='SALT')
        with patch.dict(znc.__salt__, {'cmd.run': mock}):
            self.assertEqual(znc.buildmod('modules.cpp'), 'SALT')

    # 'dumpconf' function tests: 1

    def test_dumpconf(self):
        '''
        Tests write the active configuration state to config file
        '''
        mock = MagicMock(return_value='SALT')
        with patch.dict(znc.__salt__, {'ps.pkill': mock}):
            self.assertEqual(znc.dumpconf(), 'SALT')

    # 'rehashconf' function tests: 1

    def test_rehashconf(self):
        '''
        Tests rehash the active configuration state from config file
        '''
        mock = MagicMock(return_value='SALT')
        with patch.dict(znc.__salt__, {'ps.pkill': mock}):
            self.assertEqual(znc.rehashconf(), 'SALT')

    # 'version' function tests: 1

    def test_version(self):
        '''
        Tests return server version from znc --version
        '''
        mock = MagicMock(return_value='ZNC 1.2 - http://znc.in')
        with patch.dict(znc.__salt__, {'cmd.run': mock}):
            self.assertEqual(znc.version(), 'ZNC 1.2')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ZncTestCase, needs_daemon=False)

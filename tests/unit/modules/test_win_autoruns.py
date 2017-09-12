# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)

# Import Salt Libs
import salt.modules.win_autoruns as win_autoruns

KEY = ['HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',
       'HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /reg:64',
       'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run']


class WinAutorunsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.win_autoruns
    '''
    def setup_loader_modules(self):
        return {win_autoruns: {}}

    # 'list_' function tests: 1

    def test_list(self):
        '''
        Test if it enables win_autoruns the service on the server
        '''
        with patch('os.listdir', MagicMock(return_value=[])):
            ret = {KEY[0]: ['SALT'], KEY[1]: ['SALT'], KEY[2]: ['SALT']}
            mock = MagicMock(return_value='Windows 7')
            with patch.dict(win_autoruns.__grains__, {'osfullname': mock}):
                mock = MagicMock(return_value='SALT')
                with patch.dict(win_autoruns.__salt__, {'cmd.run': mock}):
                    self.assertDictEqual(win_autoruns.list_(), ret)

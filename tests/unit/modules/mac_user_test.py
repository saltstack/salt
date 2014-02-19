# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.mock import MagicMock, patch

# Import Salt Libs
from salt.modules import mac_user


class MacUserTestCase(TestCase):

    mac_user.__context__ = {}
    mac_user.__grains__ = {}
    mac_user.__salt__ = {}

    def test_osmajor(self):
        with patch.dict(mac_user.__grains__, {'kernel': 'Darwin', 'osrelease': '10.9.1'}):
            self.assertEqual(mac_user._osmajor(), 10.9)

    def test_dscl(self):
        mac_mock = MagicMock(return_value={'pid': 4948,
                                           'retcode': 0,
                                           'stderr': '',
                                           'stdout': ''})
        with patch.dict(mac_user.__salt__, {'cmd.run_all': mac_mock}):
            with patch.dict(mac_user.__grains__, {'kernel': 'Darwin', 'osrelease': '10.9.1'}):
                self.assertEqual(mac_user._dscl('username'), {'pid': 4948,
                                                              'retcode': 0,
                                                              'stderr': '',
                                                              'stdout': ''})

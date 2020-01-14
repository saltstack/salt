# -*- coding: utf-8 -*-
'''
:codeauthor: Shane Lee <slee@saltstack.com>
'''
# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import sys

# Import 3rd Party Libs
from salt.ext import six

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.utils.win_osinfo as win_osinfo
import salt.utils.platform


@skipIf(not salt.utils.platform.is_windows(), 'Requires Windows')
class WinOsInfo(TestCase):
    '''
    Test cases for salt/utils/win_osinfo.py
    '''
    def test_get_os_version_info(self):
        sys_info = sys.getwindowsversion()
        get_info = win_osinfo.get_os_version_info()
        assert sys_info.major == int(get_info['MajorVersion'])
        assert sys_info.minor == int(get_info['MinorVersion'])
        assert sys_info.platform == int(get_info['PlatformID'])
        assert sys_info.build == int(get_info['BuildNumber'])
        # Platform ID is the reason for this function
        # Since we can't get the actual value another way, we will just check
        # that it exists and is a number
        assert 'PlatformID' in get_info
        assert isinstance(get_info['BuildNumber'], six.integer_types)

    def test_get_join_info(self):
        join_info = win_osinfo.get_join_info()
        assert 'Domain' in join_info
        assert 'DomainType' in join_info
        valid_types = ['Unknown', 'Unjoined', 'Workgroup', 'Domain']
        assert join_info['DomainType'] in valid_types

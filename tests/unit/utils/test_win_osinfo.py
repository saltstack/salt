"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""

import sys

import salt.utils.platform
import salt.utils.win_osinfo as win_osinfo
from tests.support.unit import TestCase, skipIf


@skipIf(not salt.utils.platform.is_windows(), "Requires Windows")
class WinOsInfo(TestCase):
    """
    Test cases for salt/utils/win_osinfo.py
    """

    def test_get_os_version_info(self):
        sys_info = sys.getwindowsversion()
        get_info = win_osinfo.get_os_version_info()
        self.assertEqual(sys_info.major, int(get_info["MajorVersion"]))
        self.assertEqual(sys_info.minor, int(get_info["MinorVersion"]))
        self.assertEqual(sys_info.platform, int(get_info["PlatformID"]))
        self.assertEqual(sys_info.build, int(get_info["BuildNumber"]))
        # Platform ID is the reason for this function
        # Since we can't get the actual value another way, we will just check
        # that it exists and is a number
        self.assertIn("PlatformID", get_info)
        self.assertTrue(isinstance(get_info["BuildNumber"], int))

    def test_get_join_info(self):
        join_info = win_osinfo.get_join_info()
        self.assertIn("Domain", join_info)
        self.assertIn("DomainType", join_info)
        valid_types = ["Unknown", "Unjoined", "Workgroup", "Domain"]
        self.assertIn(join_info["DomainType"], valid_types)

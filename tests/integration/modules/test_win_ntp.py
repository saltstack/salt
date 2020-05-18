# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pytest
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, flaky, slowTest
from tests.support.unit import skipIf


@flaky
@skipIf(not salt.utils.platform.is_windows(), "Tests for only Windows")
@pytest.mark.windows_whitelisted
class NTPTest(ModuleCase):
    """
    Validate windows ntp module
    """

    @destructiveTest
    @slowTest
    def test_ntp_set_servers(self):
        """
        test ntp get and set servers
        """
        ntp_srv = "pool.ntp.org"
        set_srv = self.run_function("ntp.set_servers", [ntp_srv])
        self.assertTrue(set_srv)

        get_srv = self.run_function("ntp.get_servers")
        self.assertEqual(ntp_srv, get_srv[0])

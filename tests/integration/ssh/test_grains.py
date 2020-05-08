# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.platform
from tests.support.case import SSHCase
from tests.support.helpers import slowTest
from tests.support.unit import skipIf


@skipIf(salt.utils.platform.is_windows(), "salt-ssh not available on Windows")
class SSHGrainsTest(SSHCase):
    """
    testing grains with salt-ssh
    """

    @slowTest
    def test_grains_items(self):
        """
        test grains.items with salt-ssh
        """
        ret = self.run_function("grains.items")
        grain = "Linux"
        if salt.utils.platform.is_darwin():
            grain = "Darwin"
        if salt.utils.platform.is_aix():
            grain = "AIX"
        self.assertEqual(ret["kernel"], grain)
        self.assertTrue(isinstance(ret, dict))

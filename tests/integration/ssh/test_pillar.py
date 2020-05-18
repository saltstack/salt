# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.platform
from tests.support.case import SSHCase
from tests.support.helpers import slowTest
from tests.support.unit import skipIf


@skipIf(salt.utils.platform.is_windows(), "salt-ssh not available on Windows")
class SSHPillarTest(SSHCase):
    """
    testing pillar with salt-ssh
    """

    @slowTest
    def test_pillar_items(self):
        """
        test pillar.items with salt-ssh
        """
        ret = self.run_function("pillar.items")
        self.assertDictContainsSubset({"monty": "python"}, ret)
        self.assertDictContainsSubset(
            {"knights": ["Lancelot", "Galahad", "Bedevere", "Robin"]}, ret
        )

    @slowTest
    def test_pillar_get(self):
        """
        test pillar.get with salt-ssh
        """
        ret = self.run_function("pillar.get", ["monty"])
        self.assertEqual(ret, "python")

    @slowTest
    def test_pillar_get_doesnotexist(self):
        """
        test pillar.get when pillar does not exist with salt-ssh
        """
        ret = self.run_function("pillar.get", ["doesnotexist"])
        self.assertEqual(ret, "")

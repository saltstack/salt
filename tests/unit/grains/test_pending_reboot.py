"""
    :codeauthor: :email:`Shane Lee <slee@saltstack.com>`
"""

import salt.grains.pending_reboot as pending_reboot
from tests.support.mock import patch
from tests.support.unit import TestCase


class PendingRebootGrainTestCase(TestCase):
    """
    Test cases for pending_reboot grain
    """

    def test_pending_reboot_false(self):
        with patch("salt.utils.win_system.get_pending_reboot", return_value=False):
            result = pending_reboot.pending_reboot()
            self.assertFalse(result["pending_reboot"])

    def test_pending_reboot_true(self):
        with patch("salt.utils.win_system.get_pending_reboot", return_value=True):
            result = pending_reboot.pending_reboot()
            self.assertTrue(result["pending_reboot"])

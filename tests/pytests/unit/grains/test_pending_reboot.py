"""
    :codeauthor: :email:`Shane Lee <slee@saltstack.com>`
"""

import salt.grains.pending_reboot as pending_reboot
from tests.support.mock import patch


def test_pending_reboot_false():
    with patch("salt.utils.win_system.get_pending_reboot", return_value=False):
        result = pending_reboot.pending_reboot()
        assert result["pending_reboot"] is False


def test_pending_reboot_true():
    with patch("salt.utils.win_system.get_pending_reboot", return_value=True):
        result = pending_reboot.pending_reboot()
        assert result["pending_reboot"] is True

import re

import pytest

from tests.support.case import ModuleCase


@pytest.mark.skip_unless_on_windows
class WinIPTest(ModuleCase):
    """
    Tests for salt.modules.win_ip
    """

    def test_get_default_gateway(self):
        """
        Test getting default gateway
        """
        ip = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
        ret = self.run_function("ip.get_default_gateway")
        assert ip.match(ret)

    def test_ip_is_enabled(self):
        """
        Test ip.is_enabled
        """
        assert self.run_function("ip.is_enabled", ["Ethernet"])
        assert "not found" in self.run_function("ip.is_enabled", ["doesnotexist"])

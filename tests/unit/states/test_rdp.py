# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.rdp as rdp

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class RdpTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.rdp
    """

    def setup_loader_modules(self):
        return {rdp: {}}

    # 'enabled' function tests: 1

    def test_enabled(self):
        """
        Test to enable the RDP service and make sure access
        to the RDP port is allowed in the firewall configuration.
        """
        name = "my_service"

        ret = {"name": name, "changes": {}, "result": True, "comment": ""}

        mock_t = MagicMock(side_effect=[False, False, True])
        mock_f = MagicMock(return_value=False)
        with patch.dict(rdp.__salt__, {"rdp.status": mock_t, "rdp.enable": mock_f}):
            with patch.dict(rdp.__opts__, {"test": True}):
                comt = "RDP will be enabled"
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(rdp.enabled(name), ret)

            with patch.dict(rdp.__opts__, {"test": False}):
                ret.update(
                    {
                        "comment": "",
                        "result": False,
                        "changes": {"RDP was enabled": True},
                    }
                )
                self.assertDictEqual(rdp.enabled(name), ret)

                comt = "RDP is enabled"
                ret.update({"comment": comt, "result": True, "changes": {}})
                self.assertDictEqual(rdp.enabled(name), ret)

    # 'disabled' function tests: 1

    def test_disabled(self):
        """
        Test to disable the RDP service.
        """
        name = "my_service"

        ret = {"name": name, "changes": {}, "result": True, "comment": ""}

        mock = MagicMock(side_effect=[True, True, False])
        mock_t = MagicMock(return_value=True)
        with patch.dict(rdp.__salt__, {"rdp.status": mock, "rdp.disable": mock_t}):
            with patch.dict(rdp.__opts__, {"test": True}):
                comt = "RDP will be disabled"
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(rdp.disabled(name), ret)

            with patch.dict(rdp.__opts__, {"test": False}):
                ret.update(
                    {
                        "comment": "",
                        "result": True,
                        "changes": {"RDP was disabled": True},
                    }
                )
                self.assertDictEqual(rdp.disabled(name), ret)

                comt = "RDP is disabled"
                ret.update({"comment": comt, "result": True, "changes": {}})
                self.assertDictEqual(rdp.disabled(name), ret)

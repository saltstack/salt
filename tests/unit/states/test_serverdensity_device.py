# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.serverdensity_device as serverdensity_device

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ServerdensityDeviceTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.serverdensity_device
    """

    def setup_loader_modules(self):
        return {serverdensity_device: {}}

    # 'monitored' function tests: 1

    def test_monitored(self):
        """
        Test to device is monitored with Server Density.
        """
        name = "my_special_server"

        ret = {"name": name, "changes": {}, "result": True, "comment": ""}

        mock_dict = MagicMock(return_value={"id": name})
        mock_t = MagicMock(side_effect=[True, {"agentKey": True}, [{"agentKey": True}]])
        mock_sd = MagicMock(side_effect=[["sd-agent"], [], True])
        with patch.multiple(
            serverdensity_device,
            __salt__={
                "status.all_status": mock_dict,
                "grains.items": mock_dict,
                "serverdensity_device.ls": mock_t,
                "pkg.list_pkgs": mock_sd,
                "serverdensity_device.install_agent": mock_sd,
            },
            __opts__={"test": False},
        ):
            comt = (
                "Such server name already exists in this"
                " Server Density account. And sd-agent is installed"
            )
            ret.update({"comment": comt})
            self.assertDictEqual(serverdensity_device.monitored(name), ret)

            comt = (
                "Successfully installed agent and created"
                " device in Server Density db."
            )
            ret.update(
                {
                    "comment": comt,
                    "changes": {
                        "created_device": {"agentKey": True},
                        "installed_agent": True,
                    },
                }
            )
            self.assertDictEqual(serverdensity_device.monitored(name), ret)

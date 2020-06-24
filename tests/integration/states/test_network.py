# -*- encoding: utf-8 -*-
"""
    :codeauthor: :email: `Justin Anderson <janderson@saltstack.com>`

    tests.integration.states.network
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
# Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, slowTest
from tests.support.mixins import SaltReturnAssertsMixin


@destructiveTest
class NetworkTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate network state module
    """

    def setUp(self):
        os_family = self.run_function("grains.get", ["os_family"])
        if os_family not in ("RedHat", "Debian"):
            self.skipTest(
                "Network state only supported on RedHat and Debian based systems"
            )

    @slowTest
    def test_managed(self):
        """
        network.managed
        """
        state_key = "network_|-dummy0_|-dummy0_|-managed"

        ret = self.run_function("state.sls", mods="network.managed", test=True)
        self.assertEqual(
            "Interface dummy0 is set to be added.", ret[state_key]["comment"]
        )

    @slowTest
    def test_routes(self):
        """
        network.routes
        """
        state_key = "network_|-routes_|-dummy0_|-routes"
        expected_changes = "Interface dummy0 routes are set to be added."

        ret = self.run_function("state.sls", mods="network.routes", test=True)

        self.assertEqual(
            ret[state_key]["comment"], "Interface dummy0 routes are set to be added."
        )

    @slowTest
    def test_system(self):
        """
        network.system
        """
        state_key = "network_|-system_|-system_|-system"

        global_settings = self.run_function("ip.get_network_settings")
        ret = self.run_function("state.sls", mods="network.system", test=True)
        self.assertIn(
            "Global network settings are set to be {0}".format(
                "added" if not global_settings else "updated"
            ),
            ret[state_key]["comment"],
        )

# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.powerpath as powerpath

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PowerpathTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.powerpath
    """

    def setup_loader_modules(self):
        return {powerpath: {}}

    # 'license_present' function tests: 1

    def test_license_present(self):
        """
        Test to ensures that the specified PowerPath license key is present
        on the host.
        """
        name = "mylic"

        ret = {"name": name, "changes": {}, "result": True, "comment": ""}

        mock_t = MagicMock(
            side_effect=[
                {"result": True, "output": name},
                {"result": False, "output": name},
            ]
        )
        mock = MagicMock(side_effect=[False, True, True, True, True])
        mock_l = MagicMock(return_value=[{"key": name}])
        with patch.dict(
            powerpath.__salt__,
            {
                "powerpath.has_powerpath": mock,
                "powerpath.list_licenses": mock_l,
                "powerpath.add_license": mock_t,
            },
        ):
            comt = "PowerPath is not installed."
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(powerpath.license_present(name), ret)

            comt = "License key {0} already present".format(name)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(powerpath.license_present(name), ret)

            with patch.dict(powerpath.__opts__, {"test": True}):
                comt = "License key Mylic is set to be added"
                ret.update({"comment": comt, "result": None, "name": "Mylic"})
                self.assertDictEqual(powerpath.license_present("Mylic"), ret)

            with patch.dict(powerpath.__opts__, {"test": False}):
                ret.update(
                    {"comment": name, "result": True, "changes": {"Mylic": "added"}}
                )
                self.assertDictEqual(powerpath.license_present("Mylic"), ret)

                ret.update({"result": False, "changes": {}})
                self.assertDictEqual(powerpath.license_present("Mylic"), ret)

    # 'license_absent' function tests: 1

    def test_license_absent(self):
        """
        Test to ensures that the specified PowerPath license key is absent
        on the host.
        """
        name = "mylic"

        ret = {"name": name, "changes": {}, "result": True, "comment": ""}

        mock_t = MagicMock(
            side_effect=[
                {"result": True, "output": name},
                {"result": False, "output": name},
            ]
        )
        mock = MagicMock(side_effect=[False, True, True, True, True])
        mock_l = MagicMock(return_value=[{"key": "salt"}])
        with patch.dict(
            powerpath.__salt__,
            {
                "powerpath.has_powerpath": mock,
                "powerpath.list_licenses": mock_l,
                "powerpath.remove_license": mock_t,
            },
        ):
            comt = "PowerPath is not installed."
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(powerpath.license_absent(name), ret)

            comt = "License key {0} not present".format(name)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(powerpath.license_absent(name), ret)

            with patch.dict(powerpath.__opts__, {"test": True}):
                comt = "License key salt is set to be removed"
                ret.update({"comment": comt, "result": None, "name": "salt"})
                self.assertDictEqual(powerpath.license_absent("salt"), ret)

            with patch.dict(powerpath.__opts__, {"test": False}):
                ret.update(
                    {"comment": name, "result": True, "changes": {"salt": "removed"}}
                )
                self.assertDictEqual(powerpath.license_absent("salt"), ret)

                ret.update({"result": False, "changes": {}})
                self.assertDictEqual(powerpath.license_absent("salt"), ret)

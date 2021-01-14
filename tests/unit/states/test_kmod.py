# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.kmod as kmod

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class KmodTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.kmod
    """

    def setup_loader_modules(self):
        return {kmod: {}}

    # 'present' function tests: 2

    def test_present(self):
        """
        Test to ensure that the specified kernel module is loaded.
        """
        name = "cheese"
        ret = {"name": name, "result": True, "comment": "", "changes": {}}

        mock_mod_list = MagicMock(return_value=[name])
        with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
            comment = "Kernel module {0} is already present".format(name)
            ret.update({"comment": comment})
            self.assertDictEqual(kmod.present(name), ret)

        mock_mod_list = MagicMock(return_value=[])
        with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
            with patch.dict(kmod.__opts__, {"test": True}):
                comment = "Kernel module {0} is set to be loaded".format(name)
                ret.update({"comment": comment, "result": None})
                self.assertDictEqual(kmod.present(name), ret)

        mock_mod_list = MagicMock(return_value=[])
        mock_available = MagicMock(return_value=[name])
        mock_load = MagicMock(return_value=[name])
        with patch.dict(
            kmod.__salt__,
            {
                "kmod.mod_list": mock_mod_list,
                "kmod.available": mock_available,
                "kmod.load": mock_load,
            },
        ):
            with patch.dict(kmod.__opts__, {"test": False}):
                comment = "Loaded kernel module {0}".format(name)
                ret.update(
                    {"comment": comment, "result": True, "changes": {name: "loaded"}}
                )
                self.assertDictEqual(kmod.present(name), ret)

    def test_present_multi(self):
        """
        Test to ensure that multiple kernel modules are loaded.
        """
        name = "salted kernel"
        mods = ["cheese", "crackers"]
        ret = {"name": name, "result": True, "changes": {}}

        mock_mod_list = MagicMock(return_value=mods)
        with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
            call_ret = kmod.present(name, mods=mods)

            # Check comment independently: makes test more stable on PY3
            comment = call_ret.pop("comment")
            self.assertIn("cheese", comment)
            self.assertIn("crackers", comment)
            self.assertIn("are already present", comment)

            # Assert against all other dictionary key/values
            self.assertDictEqual(ret, call_ret)

        mock_mod_list = MagicMock(return_value=[])
        with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
            with patch.dict(kmod.__opts__, {"test": True}):
                call_ret = kmod.present(name, mods=mods)
                ret.update({"result": None})

                # Check comment independently: makes test more stable on PY3
                comment = call_ret.pop("comment")
                self.assertIn("cheese", comment)
                self.assertIn("crackers", comment)
                self.assertIn("are set to be loaded", comment)

                # Assert against all other dictionary key/values
                self.assertDictEqual(ret, call_ret)

        mock_mod_list = MagicMock(return_value=[])
        mock_available = MagicMock(return_value=mods)
        mock_load = MagicMock(return_value=mods)
        with patch.dict(
            kmod.__salt__,
            {
                "kmod.mod_list": mock_mod_list,
                "kmod.available": mock_available,
                "kmod.load": mock_load,
            },
        ):
            with patch.dict(kmod.__opts__, {"test": False}):
                call_ret = kmod.present(name, mods=mods)
                ret.update(
                    {"result": True, "changes": {mods[0]: "loaded", mods[1]: "loaded"}}
                )

                # Check comment independently: makes test more stable on PY3
                comment = call_ret.pop("comment")
                self.assertIn("cheese", comment)
                self.assertIn("crackers", comment)
                self.assertIn("Loaded kernel modules", comment)

                # Assert against all other dictionary key/values
                self.assertDictEqual(ret, call_ret)

    # 'absent' function tests: 2

    def test_absent(self):
        """
        Test to verify that the named kernel module is not loaded.
        """
        name = "cheese"
        ret = {"name": name, "result": True, "comment": "", "changes": {}}

        mock_mod_list = MagicMock(return_value=[name])
        with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
            with patch.dict(kmod.__opts__, {"test": True}):
                comment = "Kernel module {0} is set to be removed".format(name)
                ret.update({"comment": comment, "result": None})
                self.assertDictEqual(kmod.absent(name), ret)

        mock_mod_list = MagicMock(return_value=[name])
        mock_remove = MagicMock(return_value=[name])
        with patch.dict(
            kmod.__salt__, {"kmod.mod_list": mock_mod_list, "kmod.remove": mock_remove}
        ):
            with patch.dict(kmod.__opts__, {"test": False}):
                comment = "Removed kernel module {0}".format(name)
                ret.update(
                    {"comment": comment, "result": True, "changes": {name: "removed"}}
                )
                self.assertDictEqual(kmod.absent(name), ret)

        mock_mod_list = MagicMock(return_value=[])
        with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
            with patch.dict(kmod.__opts__, {"test": True}):
                comment = "Kernel module {0} is already removed".format(name)
                ret.update({"comment": comment, "result": True, "changes": {}})
                self.assertDictEqual(kmod.absent(name), ret)

    def test_absent_multi(self):
        """
        Test to verify that multiple kernel modules are not loaded.
        """
        name = "salted kernel"
        mods = ["cheese", "crackers"]
        ret = {"name": name, "result": True, "changes": {}}

        mock_mod_list = MagicMock(return_value=mods)
        with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
            with patch.dict(kmod.__opts__, {"test": True}):
                ret.update({"result": None})
                call_ret = kmod.absent(name, mods=mods)

                # Check comment independently: makes test more stable on PY3
                comment = call_ret.pop("comment")
                self.assertIn("cheese", comment)
                self.assertIn("crackers", comment)
                self.assertIn("are set to be removed", comment)

                # Assert against all other dictionary key/values
                self.assertDictEqual(ret, call_ret)

        mock_mod_list = MagicMock(return_value=mods)
        mock_remove = MagicMock(return_value=mods)
        with patch.dict(
            kmod.__salt__, {"kmod.mod_list": mock_mod_list, "kmod.remove": mock_remove}
        ):
            with patch.dict(kmod.__opts__, {"test": False}):
                call_ret = kmod.absent(name, mods=mods)
                ret.update(
                    {
                        "result": True,
                        "changes": {mods[0]: "removed", mods[1]: "removed"},
                    }
                )

                # Check comment independently: makes test more stable on PY3
                comment = call_ret.pop("comment")
                self.assertIn("cheese", comment)
                self.assertIn("crackers", comment)
                self.assertIn("Removed kernel modules", comment)

                # Assert against all other dictionary key/values
                self.assertDictEqual(ret, call_ret)

        mock_mod_list = MagicMock(return_value=[])
        with patch.dict(kmod.__salt__, {"kmod.mod_list": mock_mod_list}):
            with patch.dict(kmod.__opts__, {"test": True}):
                comment = "Kernel modules {0} are already removed".format(
                    ", ".join(mods)
                )
                ret.update({"comment": comment, "result": True, "changes": {}})
                self.assertDictEqual(kmod.absent(name, mods=mods), ret)

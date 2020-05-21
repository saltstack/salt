# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
    :codeauthor: Andrew Colin Kissa <andrew@topdog.za.net>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt Libs
import salt.states.augeas as augeas

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class AugeasTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.augeas
    """

    def setup_loader_modules(self):
        return {augeas: {}}

    # 'change' function tests: 1
    def setUp(self):
        self.name = "zabbix"
        self.context = "/files/etc/services"
        self.changes = [
            "ins service-name after service-name[last()]",
            "set service-name[last()] zabbix-agent",
        ]
        self.fp_changes = [
            "ins service-name after /files/etc/services/service-name[last()]",
            "set /files/etc/services/service-name[last()] zabbix-agent",
        ]
        self.ret = {"name": self.name, "result": False, "changes": {}, "comment": ""}
        method_map = {
            "set": "set",
            "setm": "setm",
            "mv": "move",
            "move": "move",
            "ins": "insert",
            "insert": "insert",
            "rm": "remove",
            "remove": "remove",
        }
        self.mock_method_map = MagicMock(return_value=method_map)

    def tearDown(self):
        del self.ret
        del self.changes
        del self.fp_changes
        del self.mock_method_map

    def test_change_non_list_changes(self):
        """
        Test if none list changes handled correctly
        """
        comt = "'changes' must be specified as a list"
        self.ret.update({"comment": comt})

        self.assertDictEqual(augeas.change(self.name), self.ret)

    def test_change_non_list_load_path(self):
        """
        Test if none list load_path is handled correctly
        """
        comt = "'load_path' must be specified as a list"
        self.ret.update({"comment": comt})

        self.assertDictEqual(
            augeas.change(self.name, self.context, self.changes, load_path="x"),
            self.ret,
        )

    def test_change_in_test_mode(self):
        """
        Test test mode handling
        """
        comt = (
            'Executing commands in file "/files/etc/services":\n'
            "ins service-name after service-name[last()]"
            "\nset service-name[last()] zabbix-agent"
        )
        self.ret.update({"comment": comt, "result": True})

        with patch.dict(augeas.__opts__, {"test": True}):
            self.assertDictEqual(
                augeas.change(self.name, self.context, self.changes), self.ret
            )

    def test_change_no_context_without_full_path(self):
        """
        Test handling of no context without full path
        """
        comt = (
            "Error: Changes should be prefixed with /files if no "
            "context is provided, change: {0}".format(self.changes[0])
        )
        self.ret.update({"comment": comt, "result": False})

        with patch.dict(augeas.__opts__, {"test": False}):
            mock_dict_ = {"augeas.method_map": self.mock_method_map}
            with patch.dict(augeas.__salt__, mock_dict_):
                self.assertDictEqual(
                    augeas.change(self.name, changes=self.changes), self.ret
                )

    def test_change_no_context_with_full_path_fail(self):
        """
        Test handling of no context with full path with execute fail
        """
        self.ret.update({"comment": "Error: error", "result": False})

        with patch.dict(augeas.__opts__, {"test": False}):
            mock_execute = MagicMock(return_value=dict(retval=False, error="error"))
            mock_dict_ = {
                "augeas.execute": mock_execute,
                "augeas.method_map": self.mock_method_map,
            }
            with patch.dict(augeas.__salt__, mock_dict_):
                self.assertDictEqual(
                    augeas.change(self.name, changes=self.fp_changes), self.ret
                )

    def test_change_no_context_with_full_path_pass(self):
        """
        Test handling of no context with full path with execute pass
        """
        self.ret.update(
            dict(
                comment="Changes have been saved",
                result=True,
                changes={"diff": "+ zabbix-agent"},
            )
        )

        with patch.dict(augeas.__opts__, {"test": False}):
            mock_execute = MagicMock(return_value=dict(retval=True))
            mock_dict_ = {
                "augeas.execute": mock_execute,
                "augeas.method_map": self.mock_method_map,
            }
            with patch.dict(augeas.__salt__, mock_dict_):
                mock_filename = MagicMock(return_value="/etc/services")
                with patch.object(augeas, "_workout_filename", mock_filename), patch(
                    "os.path.isfile", MagicMock(return_value=True)
                ):
                    with patch("salt.utils.files.fopen", MagicMock(mock_open)):
                        mock_diff = MagicMock(return_value=["+ zabbix-agent"])
                        with patch("difflib.unified_diff", mock_diff):
                            self.assertDictEqual(
                                augeas.change(self.name, changes=self.fp_changes),
                                self.ret,
                            )

    def test_change_no_context_without_full_path_invalid_cmd(self):
        """
        Test handling of invalid commands when no context supplied
        """
        self.ret.update(
            dict(comment="Error: Command det is not supported (yet)", result=False)
        )

        with patch.dict(augeas.__opts__, {"test": False}):
            mock_execute = MagicMock(return_value=dict(retval=True))
            mock_dict_ = {
                "augeas.execute": mock_execute,
                "augeas.method_map": self.mock_method_map,
            }
            with patch.dict(augeas.__salt__, mock_dict_):
                changes = ["det service-name[last()] zabbix-agent"]
                self.assertDictEqual(
                    augeas.change(self.name, changes=changes), self.ret
                )

    def test_change_no_context_without_full_path_invalid_change(self):
        """
        Test handling of invalid change when no context supplied
        """
        comt = "Error: Invalid formatted command, see " "debug log for details: require"
        self.ret.update(dict(comment=comt, result=False))
        changes = ["require"]

        with patch.dict(augeas.__opts__, {"test": False}):
            mock_execute = MagicMock(return_value=dict(retval=True))
            mock_dict_ = {
                "augeas.execute": mock_execute,
                "augeas.method_map": self.mock_method_map,
            }
            with patch.dict(augeas.__salt__, mock_dict_):
                self.assertDictEqual(
                    augeas.change(self.name, changes=changes), self.ret
                )

    def test_change_no_context_with_full_path_multiple_files(self):
        """
        Test handling of different paths with no context supplied
        """
        changes = [
            "set /files/etc/hosts/service-name test",
            "set /files/etc/services/service-name test",
        ]
        filename = "/etc/hosts/service-name"
        filename_ = "/etc/services/service-name"
        comt = (
            "Error: Changes should be made to one file at a time, "
            "detected changes to {0} and {1}".format(filename, filename_)
        )
        self.ret.update(dict(comment=comt, result=False))

        with patch.dict(augeas.__opts__, {"test": False}):
            mock_execute = MagicMock(return_value=dict(retval=True))
            mock_dict_ = {
                "augeas.execute": mock_execute,
                "augeas.method_map": self.mock_method_map,
            }
            with patch.dict(augeas.__salt__, mock_dict_):
                self.assertDictEqual(
                    augeas.change(self.name, changes=changes), self.ret
                )

    def test_change_with_context_without_full_path_fail(self):
        """
        Test handling of context without full path fails
        """
        self.ret.update(dict(comment="Error: error", result=False))

        with patch.dict(augeas.__opts__, {"test": False}):
            mock_execute = MagicMock(return_value=dict(retval=False, error="error"))
            mock_dict_ = {
                "augeas.execute": mock_execute,
                "augeas.method_map": self.mock_method_map,
            }
            with patch.dict(augeas.__salt__, mock_dict_):
                with patch("salt.utils.files.fopen", MagicMock(mock_open)):
                    self.assertDictEqual(
                        augeas.change(
                            self.name, context=self.context, changes=self.changes
                        ),
                        self.ret,
                    )

    def test_change_with_context_without_old_file(self):
        """
        Test handling of context without oldfile pass
        """
        self.ret.update(
            dict(
                comment="Changes have been saved",
                result=True,
                changes={"updates": self.changes},
            )
        )

        with patch.dict(augeas.__opts__, {"test": False}):
            mock_execute = MagicMock(return_value=dict(retval=True))
            mock_dict_ = {
                "augeas.execute": mock_execute,
                "augeas.method_map": self.mock_method_map,
            }
            with patch.dict(augeas.__salt__, mock_dict_):
                mock_isfile = MagicMock(return_value=False)
                with patch.object(os.path, "isfile", mock_isfile):
                    self.assertDictEqual(
                        augeas.change(
                            self.name, context=self.context, changes=self.changes
                        ),
                        self.ret,
                    )

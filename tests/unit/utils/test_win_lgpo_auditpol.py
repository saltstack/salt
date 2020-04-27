# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import random

# Import Salt Libs
import salt.modules.cmdmod
import salt.utils.platform
import salt.utils.win_lgpo_auditpol as win_lgpo_auditpol

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

settings = ["No Auditing", "Success", "Failure", "Success and Failure"]


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinLgpoAuditpolTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            win_lgpo_auditpol: {
                "__context__": {},
                "__salt__": {"cmd.run_all": salt.modules.cmdmod.run_all},
            }
        }

    def test_get_settings(self):
        names = win_lgpo_auditpol._get_valid_names()
        ret = win_lgpo_auditpol.get_settings(category="All")
        for name in names:
            self.assertIn(name, [k.lower() for k in ret])

    def test_get_settings_invalid_category(self):
        self.assertRaises(
            KeyError, win_lgpo_auditpol.get_settings, category="Fake Category"
        )

    def test_get_setting(self):
        names = win_lgpo_auditpol._get_valid_names()
        for name in names:
            ret = win_lgpo_auditpol.get_setting(name)
            self.assertIn(ret, settings)

    def test_get_setting_invalid_name(self):
        self.assertRaises(KeyError, win_lgpo_auditpol.get_setting, name="Fake Name")

    def test_set_setting(self):
        names = ["Credential Validation", "IPsec Driver", "File System", "SAM"]
        mock_set = MagicMock(return_value={"retcode": 0, "stdout": "Success"})
        with patch.object(salt.modules.cmdmod, "run_all", mock_set):
            with patch.object(
                win_lgpo_auditpol,
                "_get_valid_names",
                return_value=[k.lower() for k in names],
            ):
                for name in names:
                    value = random.choice(settings)
                    win_lgpo_auditpol.set_setting(name=name, value=value)
                    switches = win_lgpo_auditpol.settings[value]
                    cmd = 'auditpol /set /subcategory:"{0}" {1}' "".format(
                        name, switches
                    )
                    mock_set.assert_called_once_with(cmd=cmd, python_shell=True)
                    mock_set.reset_mock()

    def test_set_setting_invalid_setting(self):
        names = ["Credential Validation", "IPsec Driver", "File System"]
        with patch.object(
            win_lgpo_auditpol,
            "_get_valid_names",
            return_value=[k.lower() for k in names],
        ):
            self.assertRaises(
                KeyError,
                win_lgpo_auditpol.set_setting,
                name="Fake Name",
                value="No Auditing",
            )

    def test_set_setting_invalid_value(self):
        names = ["Credential Validation", "IPsec Driver", "File System"]
        with patch.object(
            win_lgpo_auditpol,
            "_get_valid_names",
            return_value=[k.lower() for k in names],
        ):
            self.assertRaises(
                KeyError,
                win_lgpo_auditpol.set_setting,
                name="Credential Validation",
                value="Fake Value",
            )

    def test_get_auditpol_dump(self):
        names = win_lgpo_auditpol._get_valid_names()
        dump = win_lgpo_auditpol.get_auditpol_dump()
        for name in names:
            found = False
            for line in dump:
                if name.lower() in line.lower():
                    found = True
                    break
            self.assertTrue(found)

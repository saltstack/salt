# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.helpers import destructiveTest
from tests.support.unit import skipIf
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.case import ModuleCase

# Import Salt libs
import salt.modules.cmdmod
import salt.utils.win_lgpo_auditpol as win_lgpo_auditpol
import salt.utils.platform


@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinLgpoAuditpolTestCase(ModuleCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            win_lgpo_auditpol: {
                '__context__': {},
                '__salt__': {'cmd.run_all': salt.modules.cmdmod.run_all}}}

    def test_set_setting(self):
        settings = win_lgpo_auditpol.get_settings(category='ALL')
        if len(settings) == 0:
            return None
        setting = tuple(settings)[0]
        value = settings[setting]
        try:
            new_value = [key for key in win_lgpo_auditpol.settings if key != value][0]
            win_lgpo_auditpol.set_setting(setting, new_value)
            self.assertEqual(new_value, win_lgpo_auditpol.get_settings(category='ALL')[setting])
        finally:
            win_lgpo_auditpol.set_setting(setting, value)
            self.assertEqual(value, win_lgpo_auditpol.get_settings(category='ALL')[setting])

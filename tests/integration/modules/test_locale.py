# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import (
    requires_salt_modules,
    destructiveTest,
)

# Import salt libs
import salt.utils


def _find_new_locale(current_locale):
    for locale in ['en_US.UTF-8', 'de_DE.UTF-8', 'fr_FR.UTF-8']:
        if locale != current_locale:
            return locale


@skipIf(salt.utils.is_windows(), 'minion is windows')
@requires_salt_modules('locale')
class LocaleModuleTest(ModuleCase):
    def test_get_locale(self):
        locale = self.run_function('locale.get_locale')
        self.assertNotIn('Unsupported platform!', locale)
        self.assertNotEqual('', locale)

    @destructiveTest
    def test_gen_locale(self):
        locale = self.run_function('locale.get_locale')
        new_locale = _find_new_locale(locale)
        ret = self.run_function('locale.gen_locale', [new_locale])
        self.assertTrue(ret)

    @destructiveTest
    def test_set_locale(self):
        original_locale = self.run_function('locale.get_locale')
        locale_to_set = _find_new_locale(original_locale)
        self.run_function('locale.gen_locale', [locale_to_set])
        ret = self.run_function('locale.set_locale', [locale_to_set])
        new_locale = self.run_function('locale.get_locale')
        self.assertTrue(ret)
        self.assertEqual(locale_to_set, new_locale)
        self.run_function('locale.set_locale', [original_locale])

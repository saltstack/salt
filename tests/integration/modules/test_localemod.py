# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import pytest

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import Salt libs
import salt.utils.platform


def _find_new_locale(current_locale):
    for locale in ['en_US.UTF-8', 'de_DE.UTF-8', 'fr_FR.UTF-8']:
        if locale != current_locale:
            return locale


@skipIf(salt.utils.platform.is_windows(), 'minion is windows')
@skipIf(salt.utils.platform.is_darwin(), 'locale method is not supported on mac')
@pytest.mark.requires_salt_modules('locale')
class LocaleModuleTest(ModuleCase):
    def test_get_locale(self):
        locale = self.run_function('locale.get_locale')
        self.assertNotIn('Unsupported platform!', locale)

    @pytest.mark.destructive_test
    def test_gen_locale(self):
        # Make sure charmaps are available on test system before attempting
        # call gen_locale. We log this error to the user in the function, but
        # we don't want to fail this test if this is missing on the test system.
        char_maps = self.run_function('cmd.run_all', ['locale -m'])
        if char_maps['stdout'] == '':
            self.skipTest('locale charmaps not available. Skipping test.')

        if char_maps['retcode'] and char_maps['stderr']:
            self.skipTest('{0}. Cannot generate locale. Skipping test.'.format(
                char_maps['stderr'])
            )

        locale = self.run_function('locale.get_locale')
        new_locale = _find_new_locale(locale)
        ret = self.run_function('locale.gen_locale', [new_locale])
        self.assertTrue(ret)

    @pytest.mark.destructive_test
    def test_set_locale(self):
        original_locale = self.run_function('locale.get_locale')
        locale_to_set = _find_new_locale(original_locale)
        self.run_function('locale.gen_locale', [locale_to_set])
        ret = self.run_function('locale.set_locale', [locale_to_set])
        new_locale = self.run_function('locale.get_locale')
        self.assertTrue(ret)
        self.assertEqual(locale_to_set, new_locale)
        self.run_function('locale.set_locale', [original_locale])

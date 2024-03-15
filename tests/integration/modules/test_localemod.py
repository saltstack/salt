import pytest

from tests.support.case import ModuleCase


@pytest.mark.skip_on_windows(reason="minion is windows")
@pytest.mark.skip_on_darwin(reason="locale method is not supported on mac")
@pytest.mark.skip_on_freebsd(
    reason="locale method is supported only within login classes or environment variables"
)
@pytest.mark.requires_salt_modules("locale")
@pytest.mark.windows_whitelisted
class LocaleModuleTest(ModuleCase):
    def _find_new_locale(self, current_locale):
        test_locales = ["en_US.UTF-8", "de_DE.UTF-8", "fr_FR.UTF-8", "en_AU.UTF-8"]
        for locale in test_locales:
            if locale != current_locale and self.run_function("locale.avail", [locale]):
                return locale

        self.skipTest(
            "The test locals: {} do not exist on the host. Skipping test.".format(
                ",".join(test_locales)
            )
        )

    def test_get_locale(self):
        locale = self.run_function("locale.get_locale")
        self.assertNotIn("Unsupported platform!", locale)

    @pytest.mark.timeout(120)
    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_gen_locale(self):
        # Make sure charmaps are available on test system before attempting
        # call gen_locale. We log this error to the user in the function, but
        # we don't want to fail this test if this is missing on the test system.
        char_maps = self.run_function("cmd.run_all", ["locale -m"])
        if char_maps["stdout"] == "":
            self.skipTest("locale charmaps not available. Skipping test.")

        if char_maps["retcode"] and char_maps["stderr"]:
            self.skipTest(
                "{}. Cannot generate locale. Skipping test.".format(char_maps["stderr"])
            )

        locale = self.run_function("locale.get_locale")
        new_locale = self._find_new_locale(locale)
        ret = self.run_function("locale.gen_locale", [new_locale])
        self.assertTrue(ret)

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_locale(self):
        original_locale = self.run_function("locale.get_locale")
        locale_to_set = self._find_new_locale(original_locale)
        self.run_function("locale.gen_locale", [locale_to_set])
        ret = self.run_function("locale.set_locale", [locale_to_set])
        new_locale = self.run_function("locale.get_locale")
        self.assertTrue(ret)
        self.assertEqual(locale_to_set, new_locale)
        self.run_function("locale.set_locale", [original_locale])

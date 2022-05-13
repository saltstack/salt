import pytest
from tests.support.case import ModuleCase


@pytest.mark.windows_whitelisted
class GentoolkitModuleTest(ModuleCase):
    def setUp(self):
        """
        Set up test environment
        """
        super().setUp()
        ret_grain = self.run_function("grains.item", ["os"])
        if ret_grain["os"] not in "Gentoo":
            self.skipTest("For Gentoo only")

    def test_revdep_rebuild_true(self):
        ret = self.run_function("gentoolkit.revdep_rebuild")
        self.assertTrue(ret)

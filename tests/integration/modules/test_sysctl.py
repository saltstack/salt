import pytest

from tests.support.case import ModuleCase


class SysctlModuleTest(ModuleCase):
    def setUp(self):
        super().setUp()
        ret = self.run_function("cmd.has_exec", ["sysctl"])
        if not ret:
            self.skipTest("sysctl not found")

    def test_show(self):
        ret = self.run_function("sysctl.show")
        self.assertIsInstance(ret, dict, "sysctl.show return wrong type")
        self.assertGreater(len(ret), 10, "sysctl.show return few data")

    @pytest.mark.skip_unless_on_linux
    def test_show_linux(self):
        ret = self.run_function("sysctl.show")
        self.assertIn("kernel.ostype", ret, "kernel.ostype absent")

    @pytest.mark.skip_unless_on_freebsd
    def test_show_freebsd(self):
        ret = self.run_function("sysctl.show")
        self.assertIn("vm.vmtotal", ret, "Multiline variable absent")
        self.assertGreater(
            len(ret.get("vm.vmtotal").splitlines()),
            1,
            "Multiline value was parsed wrong",
        )

    @pytest.mark.skip_unless_on_openbsd
    def test_show_openbsd(self):
        ret = self.run_function("sysctl.show")
        self.assertIn("kern.ostype", ret, "kern.ostype absent")
        self.assertEqual(ret.get("kern.ostype"), "OpenBSD", "Incorrect kern.ostype")

    @pytest.mark.skip_unless_on_darwin
    def test_show_darwin(self):
        ret = self.run_function("sysctl.show")
        self.assertIn("kern.ostype", ret, "kern.ostype absent")
        self.assertEqual(ret.get("kern.ostype"), "Darwin", "Incorrect kern.ostype")

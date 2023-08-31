import pytest

from tests.support.case import ModuleCase

pytestmark = [
    pytest.mark.skip_unless_on_freebsd,
]


class SysrcModuleTest(ModuleCase):
    def setUp(self):
        super().setUp()
        ret = self.run_function("cmd.has_exec", ["sysrc"])
        if not ret:
            self.skipTest("sysrc not found")

    def test_show(self):
        ret = self.run_function("sysrc.get")
        self.assertIsInstance(
            ret, dict, "sysrc.get returned wrong type, expecting dictionary"
        )
        self.assertIn(
            "/etc/rc.conf", ret, "sysrc.get should have an rc.conf key in it."
        )

    @pytest.mark.destructive_test
    def test_set(self):
        ret = self.run_function("sysrc.set", ["test_var", "1"])
        self.assertIsInstance(
            ret, dict, "sysrc.get returned wrong type, expecting dictionary"
        )
        self.assertIn(
            "/etc/rc.conf", ret, "sysrc.set should have an rc.conf key in it."
        )
        self.assertIn(
            "1",
            ret["/etc/rc.conf"]["test_var"],
            "sysrc.set should return the value it set.",
        )
        ret = self.run_function("sysrc.remove", ["test_var"])
        self.assertEqual("test_var removed", ret)

    @pytest.mark.destructive_test
    def test_set_bool(self):
        ret = self.run_function("sysrc.set", ["test_var", True])
        self.assertIsInstance(
            ret, dict, "sysrc.get returned wrong type, expecting dictionary"
        )
        self.assertIn(
            "/etc/rc.conf", ret, "sysrc.set should have an rc.conf key in it."
        )
        self.assertIn(
            "YES",
            ret["/etc/rc.conf"]["test_var"],
            "sysrc.set should return the value it set.",
        )
        ret = self.run_function("sysrc.remove", ["test_var"])
        self.assertEqual("test_var removed", ret)

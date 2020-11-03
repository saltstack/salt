# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import sys

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.unit import skipIf


class SysrcModuleTest(ModuleCase):
    def setUp(self):
        super(SysrcModuleTest, self).setUp()
        ret = self.run_function("cmd.has_exec", ["sysrc"])
        if not ret:
            self.skipTest("sysrc not found")

    @skipIf(not sys.platform.startswith("freebsd"), "FreeBSD specific")
    def test_show(self):
        ret = self.run_function("sysrc.get")
        self.assertIsInstance(
            ret, dict, "sysrc.get returned wrong type, expecting dictionary"
        )
        self.assertIn(
            "/etc/rc.conf", ret, "sysrc.get should have an rc.conf key in it."
        )

    @skipIf(not sys.platform.startswith("freebsd"), "FreeBSD specific")
    @destructiveTest
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

    @skipIf(not sys.platform.startswith("freebsd"), "FreeBSD specific")
    @destructiveTest
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

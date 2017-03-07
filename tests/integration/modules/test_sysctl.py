# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import sys

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf


class SysctlModuleTest(integration.ModuleCase):
    def setUp(self):
        super(SysctlModuleTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['sysctl'])
        if not ret:
            self.skipTest('sysctl not found')

    def test_show(self):
        ret = self.run_function('sysctl.show')
        self.assertIsInstance(ret, dict, 'sysctl.show return wrong type')
        self.assertGreater(len(ret), 10, 'sysctl.show return few data')

    @skipIf(not sys.platform.startswith('linux'), 'Linux specific')
    def test_show_linux(self):
        ret = self.run_function('sysctl.show')
        self.assertIn('kernel.ostype', ret, 'kernel.ostype absent')

    @skipIf(not sys.platform.startswith('freebsd'), 'FreeBSD specific')
    def test_show_freebsd(self):
        ret = self.run_function('sysctl.show')
        self.assertIn('vm.vmtotal', ret, 'Multiline variable absent')
        self.assertGreater(ret.get('vm.vmtotal').splitlines(),
                           1,
                           'Multiline value was parsed wrong')

    @skipIf(not sys.platform.startswith('openbsd'), 'OpenBSD specific')
    def test_show_openbsd(self):
        ret = self.run_function('sysctl.show')
        self.assertIn('kern.ostype', ret, 'kern.ostype absent')
        self.assertEqual(
            ret.get('kern.ostype'), 'OpenBSD', 'Incorrect kern.ostype'
        )

    @skipIf(not sys.platform.startswith('darwin'), 'Darwin (macOS) specific')
    def test_show_darwin(self):
        ret = self.run_function('sysctl.show')
        self.assertIn('kern.ostype', ret, 'kern.ostype absent')
        self.assertEqual(
            ret.get('kern.ostype'), 'Darwin', 'Incorrect kern.ostype'
        )

# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import sys

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


class SysctlModuleTest(ModuleCase):
    def setUp(self):
        super(SysctlModuleTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['sysctl'])
        if not ret:
            self.skipTest('sysctl not found')

    def test_show(self):
        ret = self.run_function('sysctl.show')
        assert isinstance(ret, dict), 'sysctl.show return wrong type'
        assert len(ret) > 10, 'sysctl.show return few data'

    @skipIf(not sys.platform.startswith('linux'), 'Linux specific')
    def test_show_linux(self):
        ret = self.run_function('sysctl.show')
        assert 'kernel.ostype' in ret, 'kernel.ostype absent'

    @skipIf(not sys.platform.startswith('freebsd'), 'FreeBSD specific')
    def test_show_freebsd(self):
        ret = self.run_function('sysctl.show')
        assert 'vm.vmtotal' in ret, 'Multiline variable absent'
        assert len(ret.get('vm.vmtotal').splitlines()) > \
                           1, \
                           'Multiline value was parsed wrong'

    @skipIf(not sys.platform.startswith('openbsd'), 'OpenBSD specific')
    def test_show_openbsd(self):
        ret = self.run_function('sysctl.show')
        assert 'kern.ostype' in ret, 'kern.ostype absent'
        assert ret.get('kern.ostype') == 'OpenBSD', 'Incorrect kern.ostype'

    @skipIf(not sys.platform.startswith('darwin'), 'Darwin (macOS) specific')
    def test_show_darwin(self):
        ret = self.run_function('sysctl.show')
        assert 'kern.ostype' in ret, 'kern.ostype absent'
        assert ret.get('kern.ostype') == 'Darwin', 'Incorrect kern.ostype'

# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import sys

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration


class SysrcModuleTest(integration.ModuleCase):
    def setUp(self):
        super(SysrcModuleTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['sysrc'])
        if not ret:
            self.skipTest('sysrc not found')

    @skipIf(not sys.platform.startswith('freebsd'), 'FreeBSD specific')
    def test_show(self):
        ret = self.run_function('sysrc.get')
        self.assertIsInstance(ret, dict, 'sysrc.get returned wrong type, expecting dictionary')
        self.assertIn('/etc/rc.conf', ret, 'sysrc.get should have an rc.conf key in it.')

    @skipIf(not sys.platform.startswith('freebsd'), 'FreeBSD specific')
    @destructiveTest
    def test_set(self):
        ret = self.run_function('sysrc.set', ['test_var', '1'])
        self.assertIsInstance(ret, dict, 'sysrc.get returned wrong type, expecting dictionary')
        self.assertIn('/etc/rc.conf', ret, 'sysrc.set should have an rc.conf key in it.')
        self.assertIn('1', ret['/etc/rc.conf']['test_var'], 'sysrc.set should return the value it set.')
        ret = self.run_function('sysrc.remove', ['test_var'])
        self.assertEqual('test_var removed', ret)

    @skipIf(not sys.platform.startswith('freebsd'), 'FreeBSD specific')
    @destructiveTest
    def test_set_bool(self):
        ret = self.run_function('sysrc.set', ['test_var', True])
        self.assertIsInstance(ret, dict, 'sysrc.get returned wrong type, expecting dictionary')
        self.assertIn('/etc/rc.conf', ret, 'sysrc.set should have an rc.conf key in it.')
        self.assertIn('YES', ret['/etc/rc.conf']['test_var'], 'sysrc.set should return the value it set.')
        ret = self.run_function('sysrc.remove', ['test_var'])
        self.assertEqual('test_var removed', ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SysrcModuleTest)

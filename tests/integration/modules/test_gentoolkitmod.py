# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class GentoolkitModuleTest(integration.ModuleCase):
    def setUp(self):
        '''
        Set up test environment
        '''
        super(GentoolkitModuleTest, self).setUp()
        ret_grain = self.run_function('grains.item', ['os'])
        if ret_grain['os'] not in 'Gentoo':
            self.skipTest('For Gentoo only')

    def test_revdep_rebuild_true(self):
        ret = self.run_function('gentoolkit.revdep_rebuild')
        self.assertTrue(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GentoolkitModuleTest)

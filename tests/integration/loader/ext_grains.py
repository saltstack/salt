# -*- coding: utf-8 -*-
'''
    integration.loader.ext_grains
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader regarding external grains
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
from salttesting.unit import skipIf
ensure_in_syspath('../')

# Import salt libs
import integration
from salt.config import minion_config

from salt.loader import grains


class LoaderGrainsTest(integration.ModuleCase):
    '''
    Test the loader standard behavior with external grains
    '''

    def setUp(self):
        self.opts = minion_config(None)
        self.opts['disable_modules'] = ['pillar']
        self.opts['grains'] = grains(self.opts)

    def test_grains_overwrite(self):
        grains = self.run_function('grains.items')

        # Check that custom grains are overwritten
        self.assertEqual({'k2': 'v2'}, grains['a_custom'])


@skipIf(True, "needs a way to reload minion after config change")
class LoaderGrainsMergeTest(integration.ModuleCase):
    '''
    Test the loader deep merge behavior with external grains
    '''

    def setUp(self):
        self.opts = minion_config(None)
        self.opts['grains_deep_merge'] = True
        self.assertTrue(self.opts['grains_deep_merge'])
        self.opts['disable_modules'] = ['pillar']
        __grains__ = grains(self.opts)

    def test_grains_merge(self):
        __grain__ = self.run_function('grains.item', ['a_custom'])

        # Check that the grain is present
        self.assertIn('a_custom', __grain__)
        # Check that the grains are merged
        self.assertEqual({'k1': 'v1', 'k2': 'v2'}, __grain__['a_custom'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LoaderGrainsTest)
    run_tests(LoaderGrainsMergeTest)

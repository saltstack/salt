# -*- coding: utf-8 -*-
'''
    integration.loader.custom_grains
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader regarding custom grains
'''

# Import Python libs
from __future__ import absolute_import
import os
import time

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
from salttesting.unit import skipIf
ensure_in_syspath('../')

# Import salt libs
import integration
import salt.utils
from salt.config import minion_config
from salt.loader import grains

MINION_CONF = os.path.join(integration.CONF_DIR, 'minion')


class LoaderGrainsTest(integration.ModuleCase):
    '''
    Test the loader standard behavior with custom grains
    '''

    def setUp(self):
        self.opts = minion_config(MINION_CONF)
        self.opts['disable_modules'] = ['pillar']
        self.opts['grains'] = grains(self.opts)

        # For some reason there's a race condition here in Windows. The custom
        # grains need a little time to run and be applied.
        if salt.utils.is_windows():
            time.sleep(30)

    def test_grains_overwrite(self):
        grains_items = self.run_function('grains.items')

        # Check that custom grains are overwritten
        self.assertEqual({'k2': 'v2'}, grains_items['a_custom'])


@skipIf(True, "needs a way to reload minion after config change")
class LoaderGrainsMergeTest(integration.ModuleCase):
    '''
    Test the loader deep merge behavior with custom grains
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

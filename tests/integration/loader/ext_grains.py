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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LoaderGrainsTest)

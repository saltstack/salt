# -*- coding: utf-8 -*-
'''
    integration.loader.ext_grains
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader regarding external grains
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import socket
import time

# Third party
import yaml

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.paths import TMP, CONF_DIR, TMP_CONF_DIR, BASE_FILES
from tests.support.unit import skipIf

# Import salt libs
import salt.config
import salt.loader
import salt.utils

log = logging.getLogger(__name__)


@skipIf(True, "needs a way to reload minion after config change")
class LoaderGrainsMergeTest(ModuleCase):
    '''
    Test the loader deep merge behavior with external grains
    '''

    def setUp(self):
        # XXX: This seems like it should become a unit test instead
        self.opts = salt.config.minion_config(None)
        self.opts['grains_deep_merge'] = True
        self.assertTrue(self.opts['grains_deep_merge'])
        self.opts['disable_modules'] = ['pillar']
        __grains__ = salt.loader.grains(self.opts)

    def test_grains_merge(self):
        __grain__ = self.run_function('grains.item', ['a_custom'])

        # Check that the grain is present
        self.assertIn('a_custom', __grain__)
        # Check that the grains are merged
        self.assertEqual({'k1': 'v1', 'k2': 'v2'}, __grain__['a_custom'])


class GrainsPrecedenceTest(ModuleCase):
    '''
    Test grains evaluation order is as follows,
    per [docs](https://docs.saltstack.com/en/latest/topics/grains/#precedence):
        1. Core grains
        2. Custom grains in /etc/salt/grains
        3. Custom grains in /etc/salt/minion
        4. Custom grain modules in _grains directory, synced to minions

    With the additional caveat that non-core grains modules that are included in the salt/grains
    folder within this repo be considered core grains.
    '''

    def setUp(self):
        self.run_function('saltutil.sync_all')

    def test_core_localhost_grain(self):
        '''
        Sanity check that localhost grain is correct
        '''
        grains = self.run_function('grains.items')
        self.assertEqual(grains.get('localhost'), socket.gethostname())

    def test_etc_salt_grains(self):
        '''
        Test that /etc/salt/grains overrides core
        '''
        etc_salt_grains_file = os.path.join(TMP_CONF_DIR, 'grains')
        with salt.utils.fopen(etc_salt_grains_file, 'w') as etc_:
            etc_.write('localhost: cosmos')

        self.run_function('saltutil.refresh_grains')
        grains = self.run_function('grains.items')
        self.assertEqual(grains.get('localhost'), 'cosmos')

        os.remove(etc_salt_grains_file)
        self.run_function('saltutil.refresh_grains')

    def test_setval_override(self):
        '''
        Test that /etc/salt/grains overrides core via grains.setval function
        '''
        self.run_function('grains.setval', arg=('localhost', 'alien'))
        grains = self.run_function('grains.items')
        self.assertEqual(grains.get('localhost'), 'alien')
        self.run_function('grains.delkey', arg=('localhost'))

    def test_minion_config_grains(self):
        '''
        Test that minion config overrides core
        '''
        minion_config_filename = os.path.join(TMP_CONF_DIR, 'minion')
        # read original contents
        opts = salt.config.minion_config(minion_config_filename)
        opts['grains']['localhost'] = 'not-local'
        with salt.utils.fopen(minion_config_filename, 'w') as cfg_:
            yaml.safe_dump(opts, cfg_, default_flow_style=False)

        self.run_function('saltutil.refresh_grains')

        grains = self.run_function('grains.items')
        self.assertEqual(grains.get('localhost'), 'not-local')

        # restore original contents
        del opts['grains']['localhost']
        with salt.utils.fopen(minion_config_filename, 'w') as cfg_:
            yaml.safe_dump(opts, cfg_, default_flow_style=False)

        self.run_function('saltutil.refresh_grains')

    def test_custom_overwrite(self):
        '''
        Test that custom grain module overwrites core 'localhost' grain
        '''
        filename = 'overwrite_localhost_{0}.py'.format(int(time.time()))
        custom_grain_abs_path = os.path.join(BASE_FILES, '_grains', filename)
        with salt.utils.fopen(custom_grain_abs_path, 'w') as file_:
            file_.write("def overwrite_localhost():{0}".format(os.linesep))
            file_.write("    return {{'localhost': 'overwrite-localhost'}}{0}".format(os.linesep))

        self.run_function('saltutil.sync_grains')
        module = os.path.join(TMP, 'rootdir', 'cache', 'files',
                              'base', '_grains', filename)

        if not os.path.exists(module):
            os.remove(custom_grain_abs_path)
            raise AssertionError("{0} not found".format(module))

        grains = self.run_function('grains.items')
        try:
            self.assertEqual(grains.get('localhost'), 'overwrite-localhost')
        finally:
            os.remove(custom_grain_abs_path)

        self.run_function('saltutil.sync_grains')

    def test_zfs_overwrite(self):
        '''
        Test that 'core' grains modules not included in 'core' namespace can be overwritten
        '''
        filename = 'overwrite_zfs_support_{0}.py'.format(int(time.time()))
        custom_grain_abs_path = os.path.join(BASE_FILES, '_grains', filename)
        with salt.utils.fopen(custom_grain_abs_path, 'w') as file_:
            file_.write("def overwrite_zfs_support():{0}".format(os.linesep))
            file_.write("    return {{'zfs_support': 'dinosaur'}}{0}".format(os.linesep))

        self.run_function('saltutil.sync_grains')
        # avoid race condition
        module = os.path.join(TMP, 'rootdir', 'cache', 'files',
                              'base', '_grains', filename)

        if not os.path.exists(module):
            os.remove(custom_grain_abs_path)
            raise AssertionError("{0} not found".format(module))

        grains = self.run_function('grains.items')
        try:
            self.assertEqual(grains.get('zfs_support'), 'dinosaur')
        finally:
            os.remove(custom_grain_abs_path)

        self.run_function('saltutil.sync_grains')

    def test_dummy(self):
        '''
        Dummy test
        '''
        grains = self.run_function('grains.items')
        self.assertTrue('custom_grain_test' in grains)

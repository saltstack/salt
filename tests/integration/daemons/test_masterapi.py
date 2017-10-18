# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.paths import TMP, INTEGRATION_TEST_DIR

# Import 3rd-party libs

# Import Salt libs
import salt.utils.files


class AutosignGrainsTest(ShellCase):
    '''
    Test autosigning minions based on grain values.
    '''

    def setUp(self):
        shutil.copyfile(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'autosign_grains', 'autosign_file'),
            os.path.join(TMP, 'root_dir', 'autosign_file')
        )
        self.run_key('-d minion -y')
        self.run_call('test.ping')  # get minon to try to authenticate itself again

        if 'minion' in self.run_key('-l acc'):
            self.skipTest('Could not deauthorize minion')
        if 'minion' not in self.run_key('-l un'):
            self.skipTest('minion did not try to authenticate itself')

        self.autosign_grains_dir = os.path.join(self.master_opts['autosign_grains_dir'])
        if not os.path.isdir(self.autosign_grains_dir):
            os.makedirs(self.autosign_grains_dir)

    def tearDown(self):
        shutil.copyfile(
            os.path.join(INTEGRATION_TEST_DIR, 'files', 'autosign_file'),
            os.path.join(TMP, 'root_dir', 'autosign_file')
        )
        self.run_call('test.ping')  # get minon to try to authenticate itself again
        self.run_key('-a minion -y')

        if os.path.isdir(self.autosign_grains_dir):
            shutil.rmtree(self.autosign_grains_dir)

    def test_autosign_grains_accept(self):
        with salt.utils.files.fopen(os.path.join(self.autosign_grains_dir, 'test_grain'), 'w') as f:
            f.write('#invalid_value\ncheese')

        self.run_call('test.ping')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))

    def test_autosign_grains_fail(self):
        with salt.utils.files.fopen(os.path.join(self.autosign_grains_dir, 'test_grain'), 'w') as f:
            f.write('#cheese\ninvalid_value')

        self.run_call('test.ping')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

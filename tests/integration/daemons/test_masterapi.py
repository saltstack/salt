# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from tests.support.case import ShellCase

# Import 3rd-party libs

# Import Salt libs
import salt.utils.files


class AutosignGrainsTest(ShellCase):
    '''
    Test autosigning minions based on grain values.
    '''

    def test_autosign_grains_accept(self):
        self.run_key('-d minion -y')
        self.run_call('test.ping')  # get minon to try to authenticate itself again

        try:
            self.assertEqual(self.run_key('-l acc'), ['Accepted Keys:', 'sub_minion'])
            self.assertEqual(self.run_key('-l un'), ['Unaccepted Keys:', 'minion'])
        except AssertionError:
            self.run_key('-a minion -y')
            raise

        autosign_grains_dir = os.path.join(self.master_opts['autosign_grains_dir'])
        if not os.path.isdir(autosign_grains_dir):
            os.makedirs(autosign_grains_dir)
        with salt.utils.files.fopen(os.path.join(autosign_grains_dir, 'test_grain'), 'w') as f:
            f.write('#invalid_value\ncheese')

        self.run_call('test.ping')  # get minon to try to authenticate itself again
        try:
            self.assertEqual(self.run_key('-l acc'), ['Accepted Keys:', 'minion', 'sub_minion'])
        finally:
            self.run_key('-a minion -y')
            if os.path.isdir(autosign_grains_dir):
                shutil.rmtree(autosign_grains_dir)

    def test_autosign_grains_fail(self):
        self.run_key('-d minion -y')
        self.run_call('test.ping')  # get minon to try to authenticate itself again

        try:
            self.assertEqual(self.run_key('-l acc'), ['Accepted Keys:', 'sub_minion'])
            self.assertEqual(self.run_key('-l un'), ['Unaccepted Keys:', 'minion'])
        except AssertionError:
            self.run_key('-a minion -y')
            raise

        autosign_grains_dir = os.path.join(self.master_opts['autosign_grains_dir'])
        if not os.path.isdir(autosign_grains_dir):
            os.makedirs(autosign_grains_dir)
        with salt.utils.files.fopen(os.path.join(autosign_grains_dir, 'test_grain'), 'w') as f:
            f.write('#cheese\ninvalid_value')

        self.run_call('test.ping')  # get minon to try to authenticate itself again
        try:
            self.assertEqual(self.run_key('-l acc'), ['Accepted Keys:', 'sub_minion'])
            self.assertEqual(self.run_key('-l un'), ['Unaccepted Keys:', 'minion'])
        finally:
            self.run_key('-a minion -y')
            if os.path.isdir(autosign_grains_dir):
                shutil.rmtree(autosign_grains_dir)

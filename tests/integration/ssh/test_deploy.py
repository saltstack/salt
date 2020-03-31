# -*- coding: utf-8 -*-
"""
salt-ssh testing
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import shutil

# Import salt testing libs
from tests.support.case import SSHCase
from tests.support.runtests import RUNTIME_VARS

# Import salt libs
import salt.utils.yaml


class SSHTest(SSHCase):
    """
    Test general salt-ssh functionality
    """

    def test_ping(self):
        """
        Test a simple ping
        """
        ret = self.run_function("test.ping")
        self.assertTrue(ret, "Ping did not return true")

    def test_thin_dir(self):
        """
        test to make sure thin_dir is created
        and salt-call file is included
        """
        thin_dir = self.run_function("config.get", ["thin_dir"], wipe=False)
        os.path.isdir(thin_dir)
        os.path.exists(os.path.join(thin_dir, "salt-call"))
        os.path.exists(os.path.join(thin_dir, "running_data"))

    def test_ssh_pre_flight(self):
        '''
        test ssh when ssh_pre_flight is set
        ensure the script runs successfully
        '''
        roster = os.path.join(RUNTIME_VARS.TMP, 'pre_flight_roster')

        data = {'ssh_pre_flight': os.path.join(RUNTIME_VARS.TMP, 'ssh_pre_flight.sh')}
        self.custom_roster(roster, data)

        test_script = os.path.join(RUNTIME_VARS.TMP,
                'test-pre-flight-script-worked.txt')

        with salt.utils.files.fopen(data['ssh_pre_flight'], 'w') as fp_:
            fp_.write('touch {0}'.format(test_script))

        ret = self.run_function('test.ping', roster_file=roster)

        assert os.path.exists(test_script)

    def tearDown(self):
        """
        make sure to clean up any old ssh directories
        """
        salt_dir = self.run_function("config.get", ["thin_dir"], wipe=False)
        if os.path.exists(salt_dir):
            shutil.rmtree(salt_dir)

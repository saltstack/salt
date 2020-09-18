"""
salt-ssh testing
"""

import os
import shutil

from tests.support.case import SSHCase
from tests.support.helpers import slowTest
from tests.support.runtests import RUNTIME_VARS


class SSHTest(SSHCase):
    """
    Test general salt-ssh functionality
    """

    def setUp(self):
        thin_dir = self.run_function("config.get", ["thin_dir"], wipe=False)
        self.addCleanup(shutil.rmtree, thin_dir, ignore_errors=True)

    @slowTest
    def test_ping(self):
        """
        Test a simple ping
        """
        ret = self.run_function("test.ping")
        self.assertTrue(ret, "Ping did not return true")

    @slowTest
    def test_thin_dir(self):
        """
        test to make sure thin_dir is created
        and salt-call file is included
        """
        thin_dir = self.run_function("config.get", ["thin_dir"], wipe=False)
        os.path.isdir(thin_dir)
        os.path.exists(os.path.join(thin_dir, "salt-call"))
        os.path.exists(os.path.join(thin_dir, "running_data"))

    def test_set_path(self):
        """
        test setting the path env variable
        """
        path = "/pathdoesnotexist/"
        roster = os.path.join(RUNTIME_VARS.TMP, "roster-set-path")
        self.custom_roster(
            roster, data={"set_path": "$PATH:/usr/local/bin/:{}".format(path)}
        )
        ret = self.run_function("environ.get", ["PATH"], roster_file=roster)
        assert path in ret

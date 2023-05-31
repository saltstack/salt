"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import os
import random

import pytest

import salt.utils.files
from salt.exceptions import CommandExecutionError
from tests.support.case import ModuleCase

# Module Variables
ASSIGN_CMD = "net.inet.icmp.icmplim"
CONFIG = "/etc/sysctl.conf"


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@pytest.mark.skip_unless_on_darwin
class DarwinSysctlModuleTest(ModuleCase):
    """
    Integration tests for the darwin_sysctl module
    """

    def setUp(self):
        """
        Sets up the test requirements
        """
        super().setUp()
        # Data needed for cleanup
        self.has_conf = False
        self.val = self.run_function("sysctl.get", [ASSIGN_CMD])

        # If sysctl file is present, make a copy
        # Remove original file so we can replace it with test files
        if os.path.isfile(CONFIG):
            self.has_conf = True
            try:
                self.conf = self.__copy_sysctl()
            except CommandExecutionError:
                msg = "Could not copy file: {0}"
                raise CommandExecutionError(msg.format(CONFIG))
            os.remove(CONFIG)

    @pytest.mark.slow_test
    def test_assign(self):
        """
        Tests assigning a single sysctl parameter
        """
        try:
            rand = random.randint(0, 500)
            while rand == self.val:
                rand = random.randint(0, 500)
            self.run_function("sysctl.assign", [ASSIGN_CMD, rand])
            info = int(self.run_function("sysctl.get", [ASSIGN_CMD]))
            try:
                self.assertEqual(rand, info)
            except AssertionError:
                self.run_function("sysctl.assign", [ASSIGN_CMD, self.val])
                raise
        except CommandExecutionError:
            self.run_function("sysctl.assign", [ASSIGN_CMD, self.val])
            raise

    @pytest.mark.slow_test
    def test_persist_new_file(self):
        """
        Tests assigning a sysctl value to a system without a sysctl.conf file
        """
        # Always start with a clean/known sysctl.conf state
        if os.path.isfile(CONFIG):
            os.remove(CONFIG)
        try:
            self.run_function("sysctl.persist", [ASSIGN_CMD, 10])
            line = "{}={}".format(ASSIGN_CMD, 10)
            found = self.__check_string(CONFIG, line)
            self.assertTrue(found)
        except CommandExecutionError:
            os.remove(CONFIG)
            raise

    @pytest.mark.slow_test
    def test_persist_already_set(self):
        """
        Tests assigning a sysctl value that is already set in sysctl.conf file
        """
        # Always start with a clean/known sysctl.conf state
        if os.path.isfile(CONFIG):
            os.remove(CONFIG)
        try:
            self.run_function("sysctl.persist", [ASSIGN_CMD, 50])
            ret = self.run_function("sysctl.persist", [ASSIGN_CMD, 50])
            self.assertEqual(ret, "Already set")
        except CommandExecutionError:
            os.remove(CONFIG)
            raise

    @pytest.mark.slow_test
    def test_persist_apply_change(self):
        """
        Tests assigning a sysctl value and applying the change to system
        """
        # Always start with a clean/known sysctl.conf state
        if os.path.isfile(CONFIG):
            os.remove(CONFIG)
        try:
            rand = random.randint(0, 500)
            while rand == self.val:
                rand = random.randint(0, 500)
            self.run_function("sysctl.persist", [ASSIGN_CMD, rand], apply_change=True)
            info = int(self.run_function("sysctl.get", [ASSIGN_CMD]))
            self.assertEqual(info, rand)
        except CommandExecutionError:
            os.remove(CONFIG)
            raise

    def __copy_sysctl(self):
        """
        Copies an existing sysconf file and returns temp file path. Copied
        file will be restored in tearDown
        """
        # Create new temporary file path and open needed files
        temp_path = salt.utils.files.mkstemp()
        with salt.utils.files.fopen(CONFIG, "r") as org_conf:
            with salt.utils.files.fopen(temp_path, "w") as temp_sysconf:
                # write sysctl lines to temp file
                for line in org_conf:
                    temp_sysconf.write(line)
        return temp_path

    def __restore_sysctl(self):
        """
        Restores the original sysctl.conf file from temporary copy
        """
        # If sysctl testing file exists, delete it
        if os.path.isfile(CONFIG):
            os.remove(CONFIG)

        # write temp lines to sysctl file to restore
        with salt.utils.files.fopen(self.conf, "r") as temp_sysctl:
            with salt.utils.files.fopen(CONFIG, "w") as sysctl:
                for line in temp_sysctl:
                    sysctl.write(line)

        # delete temporary file
        os.remove(self.conf)

    def __check_string(self, conf_file, to_find):
        """
        Returns True if given line is present in file
        """
        with salt.utils.files.fopen(conf_file, "r") as f_in:
            for line in f_in:
                if to_find in salt.utils.stringutils.to_unicode(line):
                    return True
            return False

    def tearDown(self):
        """
        Clean up after tests
        """
        ret = self.run_function("sysctl.get", [ASSIGN_CMD])
        if ret != self.val:
            self.run_function("sysctl.assign", [ASSIGN_CMD, self.val])

        if self.has_conf is True:
            # restore original sysctl file
            self.__restore_sysctl()

        if self.has_conf is False and os.path.isfile(CONFIG):
            # remove sysctl.conf created by tests
            os.remove(CONFIG)

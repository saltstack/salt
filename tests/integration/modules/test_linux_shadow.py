"""
integration tests for shadow linux
"""

import os

import pytest
from saltfactories.utils import random_string

import salt.modules.linux_shadow
import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase


@pytest.mark.skip_if_not_root
@pytest.mark.skip_unless_on_linux
@pytest.mark.slow_test
class ShadowModuleTest(ModuleCase):
    """
    Validate the linux shadow system module
    """

    def setUp(self):
        """
        Get current settings
        """
        self._password = self.run_function("shadow.gen_password", ["Password1234"])
        if "ERROR" in self._password:
            self.fail(f"Failed to generate password: {self._password}")
        super().setUp()
        self._no_user = random_string("tu-", uppercase=False)
        self._test_user = random_string("tu-", uppercase=False)
        self._password = salt.modules.linux_shadow.gen_password("Password1234")

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_info(self):
        """
        Test shadow.info
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])

        # Correct Functionality
        ret = self.run_function("shadow.info", [self._test_user])
        self.assertEqual(ret["name"], self._test_user)

        # User does not exist
        ret = self.run_function("shadow.info", [self._no_user])
        self.assertEqual(ret["name"], "")

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_del_password(self):
        """
        Test shadow.del_password
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])

        # Correct Functionality
        self.assertTrue(self.run_function("shadow.del_password", [self._test_user]))
        self.assertEqual(
            self.run_function("shadow.info", [self._test_user])["passwd"], ""
        )

        # User does not exist
        self.assertFalse(self.run_function("shadow.del_password", [self._no_user]))

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_password(self):
        """
        Test shadow.set_password
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])

        # Correct Functionality
        self.assertTrue(
            self.run_function("shadow.set_password", [self._test_user, self._password])
        )

        # User does not exist
        self.assertFalse(
            self.run_function("shadow.set_password", [self._no_user, self._password])
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_inactdays(self):
        """
        Test shadow.set_inactdays
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])

        # Correct Functionality
        self.assertTrue(
            self.run_function("shadow.set_inactdays", [self._test_user, 12])
        )

        # User does not exist (set_inactdays return None is user does not exist)
        self.assertFalse(self.run_function("shadow.set_inactdays", [self._no_user, 12]))

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_maxdays(self):
        """
        Test shadow.set_maxdays
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])

        # Correct Functionality
        self.assertTrue(self.run_function("shadow.set_maxdays", [self._test_user, 12]))

        # User does not exist (set_inactdays return None is user does not exist)
        self.assertFalse(self.run_function("shadow.set_maxdays", [self._no_user, 12]))

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_mindays(self):
        """
        Test shadow.set_mindays
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])

        # Correct Functionality
        self.assertTrue(self.run_function("shadow.set_mindays", [self._test_user, 12]))

        # User does not exist (set_inactdays return None is user does not exist)
        self.assertFalse(self.run_function("shadow.set_mindays", [self._no_user, 12]))

    @pytest.mark.flaky(max_runs=4)
    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_lock_password(self):
        """
        Test shadow.lock_password
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])
        self.run_function("shadow.set_password", [self._test_user, self._password])

        # Correct Functionality
        self.assertTrue(self.run_function("shadow.lock_password", [self._test_user]))

        # User does not exist (set_inactdays return None is user does not exist)
        self.assertFalse(self.run_function("shadow.lock_password", [self._no_user]))

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_unlock_password(self):
        """
        Test shadow.lock_password
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])
        self.run_function("shadow.set_password", [self._test_user, self._password])

        # Correct Functionality
        self.assertTrue(self.run_function("shadow.unlock_password", [self._test_user]))

        # User does not exist (set_inactdays return None is user does not exist)
        self.assertFalse(self.run_function("shadow.unlock_password", [self._no_user]))

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_warndays(self):
        """
        Test shadow.set_warndays
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])

        # Correct Functionality
        self.assertTrue(self.run_function("shadow.set_warndays", [self._test_user, 12]))

        # User does not exist (set_inactdays return None is user does not exist)
        self.assertFalse(self.run_function("shadow.set_warndays", [self._no_user, 12]))

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_date(self):
        """
        Test shadow.set_date
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])

        # Correct Functionality
        self.assertTrue(
            self.run_function("shadow.set_date", [self._test_user, "2016-08-19"])
        )

        # User does not exist (set_inactdays return None is user does not exist)
        self.assertFalse(
            self.run_function("shadow.set_date", [self._no_user, "2016-08-19"])
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_expire(self):
        """
        Test shadow.set_exipre
        """
        self.addCleanup(self.run_function, "user.delete", [self._test_user])
        self.run_function("user.add", [self._test_user])

        # Correct Functionality
        self.assertTrue(
            self.run_function("shadow.set_expire", [self._test_user, "2016-08-25"])
        )

        # User does not exist (set_inactdays return None is user does not exist)
        self.assertFalse(
            self.run_function("shadow.set_expire", [self._no_user, "2016-08-25"])
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_del_root_password(self):
        """
        Test set/del password for root
        """
        # saving shadow file
        if not os.access("/etc/shadow", os.R_OK | os.W_OK):
            self.skipTest("Could not save initial state of /etc/shadow")

        def restore_shadow_file(contents):
            # restore shadow file
            with salt.utils.files.fopen("/etc/shadow", "w") as wfh:
                wfh.write(contents)

        with salt.utils.files.fopen("/etc/shadow", "r") as rfh:
            contents = rfh.read()
        self.addCleanup(restore_shadow_file, contents)

        # set root password
        self.assertTrue(
            self.run_function("shadow.set_password", ["root", self._password])
        )
        self.assertEqual(
            self.run_function("shadow.info", ["root"])["passwd"], self._password
        )
        # delete root password
        self.assertTrue(self.run_function("shadow.del_password", ["root"]))
        self.assertEqual(self.run_function("shadow.info", ["root"])["passwd"], "")

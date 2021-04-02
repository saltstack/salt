"""
integration tests for mac_shadow
"""

import datetime

import pytest
from tests.support.case import ModuleCase
from tests.support.helpers import random_string, runs_on

TEST_USER = random_string("RS-", lowercase=False)
NO_USER = random_string("RS-", lowercase=False)


@runs_on(kernel="Darwin")
@pytest.mark.skip_if_binaries_missing("dscl", "pwpolicy")
@pytest.mark.skip_if_not_root
class MacShadowModuleTest(ModuleCase):
    """
    Validate the mac_shadow module
    """

    def setUp(self):
        """
        Get current settings
        """
        self.run_function("user.add", [TEST_USER])

    def tearDown(self):
        """
        Reset to original settings
        """
        self.run_function("user.delete", [TEST_USER])

    @pytest.mark.slow_test
    def test_info(self):
        """
        Test shadow.info
        """
        # Correct Functionality
        ret = self.run_function("shadow.info", [TEST_USER])
        self.assertEqual(ret["name"], TEST_USER)

        # User does not exist
        ret = self.run_function("shadow.info", [NO_USER])
        self.assertEqual(ret["name"], "")

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_account_created(self):
        """
        Test shadow.get_account_created
        """
        # Correct Functionality
        text_date = self.run_function("shadow.get_account_created", [TEST_USER])
        self.assertNotEqual(text_date, "Invalid Timestamp")
        obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
        self.assertIsInstance(obj_date, datetime.date)

        # User does not exist
        self.assertEqual(
            self.run_function("shadow.get_account_created", [NO_USER]),
            "ERROR: User not found: {}".format(NO_USER),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_last_change(self):
        """
        Test shadow.get_last_change
        """
        # Correct Functionality
        text_date = self.run_function("shadow.get_last_change", [TEST_USER])
        self.assertNotEqual(text_date, "Invalid Timestamp")
        obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
        self.assertIsInstance(obj_date, datetime.date)

        # User does not exist
        self.assertEqual(
            self.run_function("shadow.get_last_change", [NO_USER]),
            "ERROR: User not found: {}".format(NO_USER),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_login_failed_last(self):
        """
        Test shadow.get_login_failed_last
        """
        # Correct Functionality
        text_date = self.run_function("shadow.get_login_failed_last", [TEST_USER])
        self.assertNotEqual(text_date, "Invalid Timestamp")
        obj_date = datetime.datetime.strptime(text_date, "%Y-%m-%d %H:%M:%S")
        self.assertIsInstance(obj_date, datetime.date)

        # User does not exist
        self.assertEqual(
            self.run_function("shadow.get_login_failed_last", [NO_USER]),
            "ERROR: User not found: {}".format(NO_USER),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_login_failed_count(self):
        """
        Test shadow.get_login_failed_count
        """
        # Correct Functionality
        self.assertEqual(
            self.run_function("shadow.get_login_failed_count", [TEST_USER]), "0"
        )

        # User does not exist
        self.assertEqual(
            self.run_function("shadow.get_login_failed_count", [NO_USER]),
            "ERROR: User not found: {}".format(NO_USER),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_set_maxdays(self):
        """
        Test shadow.get_maxdays
        Test shadow.set_maxdays
        """
        # Correct Functionality
        self.assertTrue(self.run_function("shadow.set_maxdays", [TEST_USER, 20]))
        self.assertEqual(self.run_function("shadow.get_maxdays", [TEST_USER]), 20)

        # User does not exist
        self.assertEqual(
            self.run_function("shadow.set_maxdays", [NO_USER, 7]),
            "ERROR: User not found: {}".format(NO_USER),
        )
        self.assertEqual(
            self.run_function("shadow.get_maxdays", [NO_USER]),
            "ERROR: User not found: {}".format(NO_USER),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_set_change(self):
        """
        Test shadow.get_change
        Test shadow.set_change
        """
        # Correct Functionality
        self.assertTrue(
            self.run_function("shadow.set_change", [TEST_USER, "02/11/2011"])
        )
        self.assertEqual(
            self.run_function("shadow.get_change", [TEST_USER]), "02/11/2011"
        )

        # User does not exist
        self.assertEqual(
            self.run_function("shadow.set_change", [NO_USER, "02/11/2012"]),
            "ERROR: User not found: {}".format(NO_USER),
        )
        self.assertEqual(
            self.run_function("shadow.get_change", [NO_USER]),
            "ERROR: User not found: {}".format(NO_USER),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_get_set_expire(self):
        """
        Test shadow.get_expire
        Test shadow.set_expire
        """
        # Correct Functionality
        self.assertTrue(
            self.run_function("shadow.set_expire", [TEST_USER, "02/11/2011"])
        )
        self.assertEqual(
            self.run_function("shadow.get_expire", [TEST_USER]), "02/11/2011"
        )

        # User does not exist
        self.assertEqual(
            self.run_function("shadow.set_expire", [NO_USER, "02/11/2012"]),
            "ERROR: User not found: {}".format(NO_USER),
        )
        self.assertEqual(
            self.run_function("shadow.get_expire", [NO_USER]),
            "ERROR: User not found: {}".format(NO_USER),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_del_password(self):
        """
        Test shadow.del_password
        """
        # Correct Functionality
        self.assertTrue(self.run_function("shadow.del_password", [TEST_USER]))
        self.assertEqual(self.run_function("shadow.info", [TEST_USER])["passwd"], "*")

        # User does not exist
        self.assertEqual(
            self.run_function("shadow.del_password", [NO_USER]),
            "ERROR: User not found: {}".format(NO_USER),
        )

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_set_password(self):
        """
        Test shadow.set_password
        """
        # Correct Functionality
        self.assertTrue(
            self.run_function("shadow.set_password", [TEST_USER, "Pa$$W0rd"])
        )

        # User does not exist
        self.assertEqual(
            self.run_function("shadow.set_password", [NO_USER, "P@SSw0rd"]),
            "ERROR: User not found: {}".format(NO_USER),
        )

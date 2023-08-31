"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
import pytest

import salt.modules.useradd as useradd
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

try:
    import pwd

    HAS_PWD = True
except ImportError:
    HAS_PWD = False


class UserAddTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.useradd
    """

    def setup_loader_modules(self):
        return {useradd: {}}

    @classmethod
    def setUpClass(cls):
        cls.mock_pwall = {
            "gid": 0,
            "groups": ["root"],
            "home": "/root",
            "name": "root",
            "passwd": "x",
            "shell": "/bin/bash",
            "uid": 0,
            "fullname": "root",
            "roomnumber": "",
            "workphone": "",
            "homephone": "",
            "other": "",
        }

    @classmethod
    def tearDownClass(cls):
        del cls.mock_pwall

    # 'getent' function tests: 2

    @pytest.mark.skipif(HAS_PWD is False, reason="The pwd module is not available")
    def test_getent(self):
        """
        Test if user.getent already have a value
        """
        with patch("salt.modules.useradd.__context__", MagicMock(return_value="Salt")):
            self.assertTrue(useradd.getent())

    @pytest.mark.skipif(HAS_PWD is False, reason="The pwd module is not available")
    def test_getent_user(self):
        """
        Tests the return information on all users
        """
        with patch("pwd.getpwall", MagicMock(return_value=[""])):
            ret = [
                {
                    "gid": 0,
                    "groups": ["root"],
                    "home": "/root",
                    "name": "root",
                    "passwd": "x",
                    "shell": "/bin/bash",
                    "uid": 0,
                    "fullname": "root",
                    "roomnumber": "",
                    "workphone": "",
                    "homephone": "",
                    "other": "",
                }
            ]
            with patch(
                "salt.modules.useradd._format_info",
                MagicMock(return_value=self.mock_pwall),
            ):
                self.assertEqual(useradd.getent(), ret)

    # 'info' function tests: 1

    @pytest.mark.skipif(HAS_PWD is False, reason="The pwd module is not available")
    def test_info(self):
        """
        Test the user information
        """
        self.assertEqual(useradd.info("username-that-does-not-exist"), {})

        mock = MagicMock(
            return_value=pwd.struct_passwd(
                (
                    "_TEST_GROUP",
                    "*",
                    83,
                    83,
                    "AMaViS Daemon",
                    "/var/virusmails",
                    "/usr/bin/false",
                )
            )
        )
        with patch.object(pwd, "getpwnam", mock):
            self.assertEqual(
                useradd.info("username-that-does-not-exist")["name"], "_TEST_GROUP"
            )

    # 'list_groups' function tests: 1

    def test_list_groups(self):
        """
        Test if it return a list of groups the named user belongs to
        """
        with patch("salt.utils.user.get_group_list", MagicMock(return_value="Salt")):
            self.assertEqual(useradd.list_groups("name"), "Salt")

    # 'list_users' function tests: 1

    @pytest.mark.skipif(HAS_PWD is False, reason="The pwd module is not available")
    def test_list_users(self):
        """
        Test if it returns a list of all users
        """
        self.assertTrue(useradd.list_users())

    def test_build_gecos_field(self):
        """
        Test if gecos fields are built correctly (removing trailing commas)
        """
        test_gecos = {
            "fullname": "Testing",
            "roomnumber": 1234,
            "workphone": 22222,
            "homephone": 99999,
        }
        expected_gecos_fields = "Testing,1234,22222,99999"
        self.assertEqual(useradd._build_gecos(test_gecos), expected_gecos_fields)
        test_gecos.pop("roomnumber")
        test_gecos.pop("workphone")
        expected_gecos_fields = "Testing,,,99999"
        self.assertEqual(useradd._build_gecos(test_gecos), expected_gecos_fields)
        test_gecos.pop("homephone")
        expected_gecos_fields = "Testing"
        self.assertEqual(useradd._build_gecos(test_gecos), expected_gecos_fields)

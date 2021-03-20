"""
Integration Tests for restcherry salt-api with pam eauth
"""
import urllib.parse

import pytest
import salt.utils.platform
import tests.support.cherrypy_testclasses as cptc
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

if cptc.HAS_CHERRYPY:
    import cherrypy

USERA = "saltdev-netapi"
USERA_PWD = "saltdev"
HASHED_USERA_PWD = "$6$SALTsalt$ZZFD90fKFWq8AGmmX0L3uBtS9fXL62SrTk5zcnQ6EkD6zoiM3kB88G1Zvs0xm/gZ7WXJRs5nsTBybUvGSqZkT."

AUTH_CREDS = {"username": USERA, "password": USERA_PWD, "eauth": "pam"}


@skipIf(cptc.HAS_CHERRYPY is False, "CherryPy not installed")
class TestAuthPAM(cptc.BaseRestCherryPyTest, ModuleCase):
    """
    Test auth with pam using salt-api
    """

    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    def setUp(self):
        super().setUp()
        try:
            add_user = self.run_function("user.add", [USERA], createhome=False)
            add_pwd = self.run_function(
                "shadow.set_password",
                [
                    USERA,
                    USERA_PWD if salt.utils.platform.is_darwin() else HASHED_USERA_PWD,
                ],
            )
            self.assertTrue(add_user)
            self.assertTrue(add_pwd)
            user_list = self.run_function("user.list_users")
            self.assertIn(USERA, str(user_list))
        except AssertionError:
            self.run_function("user.delete", [USERA], remove=True)
            self.skipTest("Could not add user or password, skipping test")

    @pytest.mark.slow_test
    def test_bad_pwd_pam_chsh_service(self):
        """
        Test login while specifying chsh service with bad passwd
        This test ensures this PR is working correctly:
        https://github.com/saltstack/salt/pull/31826
        """
        copyauth_creds = AUTH_CREDS.copy()
        copyauth_creds["service"] = "chsh"
        copyauth_creds["password"] = "wrong_password"
        body = urllib.parse.urlencode(copyauth_creds)
        request, response = self.request(
            "/login",
            method="POST",
            body=body,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status, "401 Unauthorized")

    @pytest.mark.slow_test
    def test_bad_pwd_pam_login_service(self):
        """
        Test login while specifying login service with bad passwd
        This test ensures this PR is working correctly:
        https://github.com/saltstack/salt/pull/31826
        """
        copyauth_creds = AUTH_CREDS.copy()
        copyauth_creds["service"] = "login"
        copyauth_creds["password"] = "wrong_password"
        body = urllib.parse.urlencode(copyauth_creds)
        request, response = self.request(
            "/login",
            method="POST",
            body=body,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status, "401 Unauthorized")

    @pytest.mark.slow_test
    def test_good_pwd_pam_chsh_service(self):
        """
        Test login while specifying chsh service with good passwd
        This test ensures this PR is working correctly:
        https://github.com/saltstack/salt/pull/31826
        """
        copyauth_creds = AUTH_CREDS.copy()
        copyauth_creds["service"] = "chsh"
        body = urllib.parse.urlencode(copyauth_creds)
        request, response = self.request(
            "/login",
            method="POST",
            body=body,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status, "200 OK")

    @pytest.mark.slow_test
    def test_good_pwd_pam_login_service(self):
        """
        Test login while specifying login service with good passwd
        This test ensures this PR is working correctly:
        https://github.com/saltstack/salt/pull/31826
        """
        copyauth_creds = AUTH_CREDS.copy()
        copyauth_creds["service"] = "login"
        body = urllib.parse.urlencode(copyauth_creds)
        request, response = self.request(
            "/login",
            method="POST",
            body=body,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status, "200 OK")

    @pytest.mark.destructive_test
    @pytest.mark.skip_if_not_root
    def tearDown(self):
        """
        Clean up after tests. Delete user
        """
        super().tearDown()
        user_list = self.run_function("user.list_users")
        # Remove saltdev user
        if USERA in user_list:
            self.run_function("user.delete", [USERA], remove=True)
        # need to exit cherypy engine
        cherrypy.engine.exit()

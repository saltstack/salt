import salt.auth.ldap
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf


class Bind:
    """
    fake search_s return
    """

    @staticmethod
    def search_s(*args, **kwargs):
        return [
            (
                "cn=saltusers,cn=groups,cn=compat,dc=saltstack,dc=com",
                {"memberUid": [b"saltuser"], "cn": [b"saltusers"]},
            ),
        ]


@skipIf(not salt.auth.ldap.HAS_LDAP, "Install python-ldap for this test")
class LDAPAuthTestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit tests for salt.auth.ldap
    """

    @classmethod
    def setUpClass(cls):
        cls.config = {
            "auth.ldap.binddn": (
                "uid={{username}},cn=users,cn=compat,dc=saltstack,dc=com"
            ),
            "auth.ldap.port": 389,
            "auth.ldap.tls": False,
            "auth.ldap.server": "172.18.0.2",
            "auth.ldap.accountattributename": "memberUid",
            "auth.ldap.groupattribute": "memberOf",
            "auth.ldap.group_basedn": "cn=groups,cn=compat,dc=saltstack,dc=com",
            "auth.ldap.basedn": "dc=saltstack,dc=com",
            "auth.ldap.group_filter": (
                "(&(memberUid={{ username }})(objectClass=posixgroup))"
            ),
        }

    @classmethod
    def tearDownClass(cls):
        cls.config = cls.opts = None

    def setUp(self):
        self.opts = self.config.copy()

    def tearDown(self):
        self.opts = None

    def setup_loader_modules(self):
        return {salt.auth.ldap: {"__opts__": self.config.copy()}}

    def test_config(self):
        """
        Test that the _config function works correctly
        """
        self.assertEqual(salt.auth.ldap._config("basedn"), "dc=saltstack,dc=com")
        self.assertEqual(
            salt.auth.ldap._config("group_filter"),
            "(&(memberUid={{ username }})(objectClass=posixgroup))",
        )
        self.assertEqual(salt.auth.ldap._config("accountattributename"), "memberUid")
        self.assertEqual(salt.auth.ldap._config("groupattribute"), "memberOf")

    def test_groups_freeipa(self):
        """
        test groups in freeipa
        """
        self.opts["auth.ldap.freeipa"] = True
        with patch.dict(salt.auth.ldap.__opts__, self.opts):
            with patch("salt.auth.ldap._bind", return_value=Bind):
                self.assertIn(
                    "saltusers", salt.auth.ldap.groups("saltuser", password="password")
                )

    def test_groups(self):
        """
        test groups in ldap
        """
        with patch("salt.auth.ldap._bind", return_value=Bind):
            self.assertIn(
                "saltusers", salt.auth.ldap.groups("saltuser", password="password")
            )

    def test_groups_activedirectory(self):
        """
        test groups in activedirectory
        """
        self.opts["auth.ldap.activedirectory"] = True
        with patch.dict(salt.auth.ldap.__opts__, self.opts):
            with patch("salt.auth.ldap._bind", return_value=Bind):
                self.assertIn(
                    "saltusers", salt.auth.ldap.groups("saltuser", password="password")
                )

    def test_auth_nopass(self):
        opts = self.opts.copy()
        opts["auth.ldap.bindpw"] = "p@ssw0rd!"
        with patch.dict(salt.auth.ldap.__opts__, opts):
            with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
                self.assertFalse(salt.auth.ldap.auth("foo", None))

    def test_auth_nouser(self):
        opts = self.opts.copy()
        opts["auth.ldap.bindpw"] = "p@ssw0rd!"
        with patch.dict(salt.auth.ldap.__opts__, opts):
            with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
                self.assertFalse(salt.auth.ldap.auth(None, "foo"))

    def test_auth_nouserandpass(self):
        opts = self.opts.copy()
        opts["auth.ldap.bindpw"] = "p@ssw0rd!"
        with patch.dict(salt.auth.ldap.__opts__, opts):
            with patch("salt.auth.ldap._bind_for_search", return_value=Bind):
                self.assertFalse(salt.auth.ldap.auth(None, None))

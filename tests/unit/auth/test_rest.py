import salt.auth.rest
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class RestAuthTestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit tests for salt.auth.rest
    """
    def setup_loader_modules(self):
        opts = {'external_auth': {'rest': {'^url': "https://test_url/rest",
                                    'fred': ['.*', '@runner']}}}
        return {salt.auth.rest: {"__opts__": opts}}


    def test_rest_auth_setup(self):
        ret = salt.auth.rest._rest_auth_setup()
        assert ret == "https://test_url/rest"

    def test_auth_nopass(self):
        self.assertFalse(salt.auth.rest.auth("foo", None))

    def test_auth_nouser(self):
        self.assertFalse(salt.auth.rest.auth(None, "foo"))

    def test_auth_nouserandpass(self):
        self.assertFalse(salt.auth.rest.auth(None, None))

    def test_acl_without_merge(self):
        self.assertIn(
            '@runner', salt.auth.rest.acl("fred", password="password")
        )

    def test_acl_merge(self):
        cached_acl = {'fred': ['@wheel']}
        with patch.dict(salt.auth.rest.cached_acl, cached_acl):
            self.assertIn(
                '@wheel', salt.auth.rest.acl("fred", password="password")
            )
            self.assertIn(
                '@runner', salt.auth.rest.acl("fred", password="password")
            )
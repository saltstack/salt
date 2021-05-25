import salt.auth.rest
from tests.support.mixins import LoaderModuleMockMixin
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
        ret = salt.auth.rest.rest_auth_setup()
        assert ret == "https://test_url/rest"
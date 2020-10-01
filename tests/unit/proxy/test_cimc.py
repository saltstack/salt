import logging

import salt.exceptions
import salt.proxy.cimc as cimc
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class CIMCProxyTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {cimc: {"DETAILS": {}, "__pillar__": {}}}

    def setUp(self):
        self.opts = {"proxy": {"username": "xxxx", "password": "xxx", "host": "cimc"}}

    def test_init(self):
        # No host, returns False
        opts = {"proxy": {"username": "xxxx", "password": "xxx"}}
        ret = cimc.init(opts)
        self.assertFalse(ret)

        # No username , returns False
        opts = {"proxy": {"password": "xxx", "host": "cimc"}}
        ret = cimc.init(opts)
        self.assertFalse(ret)

        # No password, returns False
        opts = {"proxy": {"username": "xxxx", "host": "cimc"}}
        ret = cimc.init(opts)
        self.assertFalse(ret)

        with patch.object(cimc, "logon", return_value="9zVG5U8DFZNsTR") as mock_logon:
            with patch.object(
                cimc, "get_config_resolver_class", return_value="True"
            ) as mock_logon:
                ret = cimc.init(self.opts)
                self.assertEqual(cimc.DETAILS["url"], "https://cimc/nuova")
                self.assertEqual(cimc.DETAILS["username"], "xxxx")
                self.assertEqual(cimc.DETAILS["password"], "xxx")
                self.assertTrue(cimc.DETAILS["initialized"])

    def test__validate_response_code(self):
        with self.assertRaisesRegex(
            salt.exceptions.CommandExecutionError,
            "Did not receive a valid response from host.",
        ):
            cimc._validate_response_code("404")

        with patch.object(cimc, "logout", return_value=True) as mock_logout:
            with self.assertRaisesRegex(
                salt.exceptions.CommandExecutionError,
                "Did not receive a valid response from host.",
            ):
                cimc._validate_response_code("404", "9zVG5U8DFZNsTR")
                mock_logout.assert_called_once_with("9zVG5U8DFZNsTR")

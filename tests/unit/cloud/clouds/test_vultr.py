# -*- coding: utf-8 -*-

# Import Salt Libs
from salt.cloud.clouds import vultrpy as vultr

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mock import patch


class VultrTestCase(TestCase):
    """
    Unit TestCase for salt.cloud.clouds.vultr module.
    """
    def test_show_keypair_no_keyname(self):
        """
        test salt.cloud.clouds.vultr.show_keypair
        when keyname is not in kwargs
        """
        kwargs = {}
        with TstSuiteLoggingHandler() as handler:
            assert not vultr.show_keypair(kwargs)
            assert "ERROR:A keyname is required." in handler.messages

    @patch("salt.cloud.clouds.vultrpy._query")
    def test_show_keypair(self, _query):
        """
        test salt.cloud.clouds.vultr.show_keypair
        when keyname provided
        """
        _query.return_value = {'test':{'SSHKEYID':'keyID'}}
        kwargs = {'keyname':'test'}
        assert vultr.show_keypair(kwargs) == {'SSHKEYID':'keyID'}

"""
tests.unit.modules.test_bigip
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the bigip module
"""
import logging

import salt.modules.bigip as bigip
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class RequestsSession:
    def __init__(self):
        self.auth = None
        self.verify = None
        self.headers = {}


class BigipModuleTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {bigip: {}}

    def test__build_session_verify_ssl(self):
        requests_session = RequestsSession()
        with patch(
            "salt.modules.bigip.requests.sessions.Session",
            MagicMock(return_value=requests_session),
        ):
            bigip._build_session("username", "password")

        self.assertEqual(requests_session.auth, ("username", "password"))
        assert requests_session.verify is True

"""
    Tests for salt.utils.boto3mod
"""

import random
import string

import salt.loader
import salt.utils.boto3mod as boto3mod
from salt.utils.versions import LooseVersion
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import boto3
    from botocore.exceptions import ClientError

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

REQUIRED_BOTO3_VERSION = "1.2.1"


def __virtual__():
    """
    Returns True/False boolean depending on if Boto3 is installed and correct
    version.
    """
    if not HAS_BOTO3:
        return False
    if LooseVersion(boto3.__version__) < LooseVersion(REQUIRED_BOTO3_VERSION):
        return (
            False,
            (
                "The boto3 module must be greater or equal to version {}"
                "".format(REQUIRED_BOTO3_VERSION)
            ),
        )
    return True


REGION = "us-east-1"
ACCESS_KEY = "GKTADJGHEIQSXMKKRBJ08H"
SECRET_KEY = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
CONN_PARAMETERS = {
    "region": REGION,
    "key": ACCESS_KEY,
    "keyid": SECRET_KEY,
    "profile": {},
}
ERROR_MESSAGE = (
    "An error occurred ({}) when calling the {} operation: Test-defined error"
)
ERROR_CONTENT = {"Error": {"Code": 101, "Message": "Test-defined error"}}
NOT_FOUND_ERROR = ClientError(
    {"Error": {"Code": "ResourceNotFoundException", "Message": "Test-defined error"}},
    "msg",
)
SESSION_RET = {}


@skipIf(HAS_BOTO3 is False, "The boto module must be installed.")
@skipIf(
    LooseVersion(boto3.__version__) < LooseVersion(REQUIRED_BOTO3_VERSION),
    "The boto3 module must be greater or equal to version {}".format(
        REQUIRED_BOTO3_VERSION
    ),
)
class Boto3modTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.utils.boto3mod module
    """

    conn = None

    def setup_loader_modules(self):
        self.opts = {
            "__salt__": {"config.option": salt.config.DEFAULT_MINION_OPTS.copy()}
        }
        return {boto3mod: self.opts}

    def setUp(self):
        super().setUp()
        boto3mod.__virtual__()
        del self.opts

        # Set up MagicMock to replace the boto3 session
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        CONN_PARAMETERS["key"] = "".join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
        )

        self.conn = MagicMock()
        self.addCleanup(delattr, self, "conn")
        self.patcher = patch("boto3.session.Session")
        self.addCleanup(self.patcher.stop)
        self.addCleanup(delattr, self, "patcher")
        mock_session = self.patcher.start()
        session_instance = mock_session.return_value
        session_instance.configure_mock(client=MagicMock(return_value=self.conn))
        self.paginator = MagicMock()
        self.addCleanup(delattr, self, "paginator")
        self.conn.configure_mock(get_paginator=MagicMock(return_value=self.paginator))

    def test_unit_test(self):
        pass

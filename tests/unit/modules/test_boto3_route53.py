"""
    Tests for salt.modules.boto3_route53
"""

import random
import string

import pytest

import salt.loader
import salt.modules.boto3_route53 as boto3_route53
from salt.utils.versions import Version
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

# the boto3_route53 module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
REQUIRED_BOTO3_VERSION = "1.2.1"

pytestmark = [
    pytest.mark.skip_on_fips_enabled_platform,
]


def __virtual__():
    """
    Returns True/False boolean depending on if Boto3 is installed and correct
    version.
    """
    if not HAS_BOTO3:
        return False
    if Version(boto3.__version__) < Version(REQUIRED_BOTO3_VERSION):
        return (
            False,
            "The boto3 module must be greater or equal to version {}".format(
                REQUIRED_BOTO3_VERSION
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

LIST_RESOURCE_RECORD_SETS_RETURN = {
    "IsTruncated": True,
    "MaxItems": "100",
    "NextRecordName": "blog3.saltstack.furniture.",
    "NextRecordType": "CNAME",
    "ResourceRecordSets": [
        {
            "Name": "blog.saltstack.furniture.",
            "ResourceRecords": [{"Value": "127.0.0.1"}],
            "TTL": 60,
            "Type": "A",
        },
        {
            "Name": "blog2.saltstack.furniture.",
            "ResourceRecords": [{"Value": "127.0.0.1"}],
            "TTL": 60,
            "Type": "A",
        },
    ],
}


@pytest.mark.skipif(HAS_BOTO3 is False, reason="The boto module must be installed.")
@pytest.mark.skipif(
    Version(boto3.__version__) < Version(REQUIRED_BOTO3_VERSION),
    reason="The boto3 module must be greater or equal to version {}".format(
        REQUIRED_BOTO3_VERSION
    ),
)
class Boto3Route53TestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.boto3_route53 moodule
    """

    conn = None

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            self.opts,
            whitelist=["boto3", "args", "systemd", "path", "platform"],
            context={},
        )
        return {boto3_route53: {"__utils__": utils}}

    def setUp(self):
        super().setUp()
        boto3_route53.__init__(self.opts)
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

    def test_get_resource_records(self):
        """
        Test get_resource_records behaviour.
        """

        # The patch below is not neccesary per se,
        # as .exists returns positive as long as no exception is raised.
        with patch.object(
            self.conn,
            "list_resource_record_sets",
            return_value=LIST_RESOURCE_RECORD_SETS_RETURN,
        ):
            self.assertEqual(
                boto3_route53.get_resource_records(
                    HostedZoneId="Z2P70J7EXAMPLE",
                    StartRecordName="blog.saltstack.furniture.",
                    StartRecordType="A",
                    **CONN_PARAMETERS
                ),
                [
                    {
                        "Name": "blog.saltstack.furniture.",
                        "ResourceRecords": [{"Value": "127.0.0.1"}],
                        "TTL": 60,
                        "Type": "A",
                    }
                ],
            )

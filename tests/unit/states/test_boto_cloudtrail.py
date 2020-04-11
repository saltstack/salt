# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import random
import string

# Import Salt libs
import salt.config
import salt.loader

# Import Salt Libs
import salt.states.boto_cloudtrail as boto_cloudtrail

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
from salt.utils.versions import LooseVersion

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

# pylint: disable=import-error,no-name-in-module,unused-import
from tests.unit.modules.test_boto_cloudtrail import BotoCloudTrailTestCaseMixin

try:
    import boto
    import boto3
    from botocore.exceptions import ClientError

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module,unused-import


# the boto_cloudtrail module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = "1.2.1"

log = logging.getLogger(__name__)


def _has_required_boto():
    """
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    """
    if not HAS_BOTO:
        return False
    elif LooseVersion(boto3.__version__) < LooseVersion(required_boto3_version):
        return False
    else:
        return True


if _has_required_boto():
    region = "us-east-1"
    access_key = "GKTADJGHEIQSXMKKRBJ08H"
    secret_key = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
    conn_parameters = {
        "region": region,
        "key": access_key,
        "keyid": secret_key,
        "profile": {},
    }
    error_message = (
        "An error occurred (101) when calling the {0} operation: Test-defined error"
    )
    not_found_error = ClientError(
        {"Error": {"Code": "TrailNotFoundException", "Message": "Test-defined error"}},
        "msg",
    )
    error_content = {"Error": {"Code": 101, "Message": "Test-defined error"}}
    trail_ret = dict(
        Name="testtrail",
        IncludeGlobalServiceEvents=True,
        KmsKeyId=None,
        LogFileValidationEnabled=False,
        S3BucketName="auditinfo",
        TrailARN="arn:aws:cloudtrail:us-east-1:214351231622:trail/testtrail",
    )
    status_ret = dict(
        IsLogging=False,
        LatestCloudWatchLogsDeliveryError=None,
        LatestCloudWatchLogsDeliveryTime=None,
        LatestDeliveryError=None,
        LatestDeliveryTime=None,
        LatestDigestDeliveryError=None,
        LatestDigestDeliveryTime=None,
        LatestNotificationError=None,
        LatestNotificationTime=None,
        StartLoggingTime=None,
        StopLoggingTime=None,
    )


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto3 module must be greater than"
    " or equal to version {0}".format(required_boto3_version),
)
class BotoCloudTrailStateTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    def setup_loader_modules(self):
        ctx = {}
        utils = salt.loader.utils(
            self.opts,
            whitelist=["boto", "boto3", "args", "systemd", "path", "platform", "reg"],
            context=ctx,
        )
        serializers = salt.loader.serializers(self.opts)
        self.funcs = funcs = salt.loader.minion_mods(
            self.opts, context=ctx, utils=utils, whitelist=["boto_cloudtrail"]
        )
        self.salt_states = salt.loader.states(
            opts=self.opts,
            functions=funcs,
            utils=utils,
            whitelist=["boto_cloudtrail"],
            serializers=serializers,
        )
        return {
            boto_cloudtrail: {
                "__opts__": self.opts,
                "__salt__": funcs,
                "__utils__": utils,
                "__states__": self.salt_states,
                "__serializers__": serializers,
            }
        }

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        cls.opts["grains"] = salt.loader.grains(cls.opts)

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    # Set up MagicMock to replace the boto3 session
    def setUp(self):
        self.addCleanup(delattr, self, "funcs")
        self.addCleanup(delattr, self, "salt_states")
        # Set up MagicMock to replace the boto3 session
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        conn_parameters["key"] = "".join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
        )

        self.patcher = patch("boto3.session.Session")
        self.addCleanup(self.patcher.stop)
        self.addCleanup(delattr, self, "patcher")
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        self.addCleanup(delattr, self, "conn")
        session_instance.client.return_value = self.conn


class BotoCloudTrailTestCase(
    BotoCloudTrailStateTestCaseBase, BotoCloudTrailTestCaseMixin
):
    """
    TestCase for salt.modules.boto_cloudtrail state.module
    """

    def test_present_when_trail_does_not_exist(self):
        """
        Tests present on a trail that does not exist.
        """
        self.conn.get_trail_status.side_effect = [not_found_error, status_ret]
        self.conn.create_trail.return_value = trail_ret
        self.conn.describe_trails.return_value = {"trailList": [trail_ret]}
        with patch.dict(
            self.funcs, {"boto_iam.get_account_id": MagicMock(return_value="1234")}
        ):
            result = self.salt_states["boto_cloudtrail.present"](
                "trail present",
                Name=trail_ret["Name"],
                S3BucketName=trail_ret["S3BucketName"],
            )

        self.assertTrue(result["result"])
        self.assertEqual(result["changes"]["new"]["trail"]["Name"], trail_ret["Name"])

    def test_present_when_trail_exists(self):
        self.conn.get_trail_status.return_value = status_ret
        self.conn.create_trail.return_value = trail_ret
        self.conn.describe_trails.return_value = {"trailList": [trail_ret]}
        with patch.dict(
            self.funcs, {"boto_iam.get_account_id": MagicMock(return_value="1234")}
        ):
            result = self.salt_states["boto_cloudtrail.present"](
                "trail present",
                Name=trail_ret["Name"],
                S3BucketName=trail_ret["S3BucketName"],
                LoggingEnabled=False,
            )
        self.assertTrue(result["result"])
        self.assertEqual(result["changes"], {})

    def test_present_with_failure(self):
        self.conn.get_trail_status.side_effect = [not_found_error, status_ret]
        self.conn.create_trail.side_effect = ClientError(error_content, "create_trail")
        with patch.dict(
            self.funcs, {"boto_iam.get_account_id": MagicMock(return_value="1234")}
        ):
            result = self.salt_states["boto_cloudtrail.present"](
                "trail present",
                Name=trail_ret["Name"],
                S3BucketName=trail_ret["S3BucketName"],
                LoggingEnabled=False,
            )
        self.assertFalse(result["result"])
        self.assertTrue("An error occurred" in result["comment"])

    def test_absent_when_trail_does_not_exist(self):
        """
        Tests absent on a trail that does not exist.
        """
        self.conn.get_trail_status.side_effect = not_found_error
        result = self.salt_states["boto_cloudtrail.absent"]("test", "mytrail")
        self.assertTrue(result["result"])
        self.assertEqual(result["changes"], {})

    def test_absent_when_trail_exists(self):
        self.conn.get_trail_status.return_value = status_ret
        result = self.salt_states["boto_cloudtrail.absent"]("test", trail_ret["Name"])
        self.assertTrue(result["result"])
        self.assertEqual(result["changes"]["new"]["trail"], None)

    def test_absent_with_failure(self):
        self.conn.get_trail_status.return_value = status_ret
        self.conn.delete_trail.side_effect = ClientError(error_content, "delete_trail")
        result = self.salt_states["boto_cloudtrail.absent"]("test", trail_ret["Name"])
        self.assertFalse(result["result"])
        self.assertTrue("An error occurred" in result["comment"])

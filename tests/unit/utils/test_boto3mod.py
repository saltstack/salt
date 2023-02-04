"""
    Tests for salt.utils.boto3mod
"""

import random
import string

import pytest

import salt.loader
import salt.utils.boto3mod as boto3mod
from salt.utils.versions import Version
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

try:
    import boto3
    from botocore.exceptions import ClientError

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

REQUIRED_BOTO3_VERSION = "1.2.1"


@pytest.mark.skipif(HAS_BOTO3 is False, reason="The boto module must be installed.")
@pytest.mark.skipif(
    Version(boto3.__version__) < Version(REQUIRED_BOTO3_VERSION),
    reason="The boto3 module must be greater or equal to version {}".format(
        REQUIRED_BOTO3_VERSION
    ),
)
class Boto3modTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.utils.boto3mod module
    """

    region = "us-east-1"
    service = "test-service"
    resource_name = "test-resource"
    resource_id = "test-resource-id"
    access_key = "GKTADJGHEIQSXMKKRBJ08H"
    secret_key = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
    conn_parameters = {}
    error_message = (
        "An error occurred ({}) when calling the {} operation: Test-defined error"
    )
    error_content = {"Error": {"Code": 101, "Message": "Test-defined error"}}
    session_ret = {}
    conn = None

    def setup_loader_modules(self):
        self.opts = {
            "__salt__": {"config.option": salt.config.DEFAULT_MINION_OPTS.copy()}
        }
        return {boto3mod: self.opts}

    def setUp(self):
        super().setUp()
        del self.opts

        # Set up MagicMock to replace the boto3 session
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        self.conn_parameters = {
            "region": self.region,
            "keyid": self.secret_key,
            "profile": {},
        }
        self.conn_parameters["key"] = "".join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(50)
        )

        self.not_found_error = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Test-defined error",
                }
            },
            "msg",
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

    def test_set_and_get_with_no_auth_params(self):
        boto3mod.cache_id(
            self.service, self.resource_name, resource_id=self.resource_id
        )
        self.assertEqual(
            boto3mod.cache_id(self.service, self.resource_name), self.resource_id
        )

    def test_set_and_get_with_explicit_auth_params(self):
        boto3mod.cache_id(
            self.service,
            self.resource_name,
            resource_id=self.resource_id,
            **self.conn_parameters
        )
        self.assertEqual(
            boto3mod.cache_id(self.service, self.resource_name, **self.conn_parameters),
            self.resource_id,
        )

    def test_set_and_get_with_different_region_returns_none(self):
        boto3mod.cache_id(
            self.service,
            self.resource_name,
            resource_id=self.resource_id,
            region="us-east-1",
        )
        self.assertEqual(
            boto3mod.cache_id(self.service, self.resource_name, region="us-west-2"),
            None,
        )

    def test_set_and_get_after_invalidation_returns_none(self):
        boto3mod.cache_id(
            self.service, self.resource_name, resource_id=self.resource_id
        )
        boto3mod.cache_id(
            self.service,
            self.resource_name,
            resource_id=self.resource_id,
            invalidate=True,
        )
        self.assertEqual(boto3mod.cache_id(self.service, self.resource_name), None)

    def test_partial(self):
        cache_id = boto3mod.cache_id_func(self.service)
        cache_id(self.resource_name, resource_id=self.resource_id)
        self.assertEqual(cache_id(self.resource_name), self.resource_id)

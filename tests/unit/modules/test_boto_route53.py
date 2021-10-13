import logging
import os.path
from collections import namedtuple

import pkg_resources  # pylint: disable=3rd-party-module-not-gated

import salt.config
import salt.loader
import salt.utils.versions
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

# pylint: disable=import-error
try:
    import salt.modules.boto_route53 as boto_route53
    from boto.route53.exception import DNSServerError
    import boto

    boto.ENDPOINTS_PATH = os.path.join(
        RUNTIME_VARS.TESTS_DIR, "unit/files/endpoints.json"
    )
    from moto import mock_route53_deprecated

    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False

    def mock_route53_deprecated(self):
        """
        if the mock_route53_deprecated function is not available due to import failure
        this replaces the decorated function with stub_function.
        Allows boto_route53 unit tests to use the @mock_route53_deprecated decorator
        without a "NameError: name 'mock_route53_deprecated' is not defined" error.
        """

        def stub_function(self):
            pass

        return stub_function


# pylint: enable=import-error

log = logging.getLogger(__name__)

required_moto = "1.0.1"


def _has_required_moto():
    """
    Returns True or False depending on if ``moto`` is installed and at the correct version,
    depending on what version of Python is running these tests.
    """
    if not HAS_MOTO:
        return False
    else:
        moto_version = salt.utils.versions.LooseVersion(
            pkg_resources.get_distribution("moto").version
        )
        if moto_version < salt.utils.versions.LooseVersion(required_moto):
            return False
    return True


@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_moto() is False,
    "The moto module must be >= to {}".format(required_moto),
)
class BotoRoute53TestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.boto_route53 module
    """

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        self.opts["route53.keyid"] = "GKTADJGHEIQSXMKKRBJ08H"
        self.opts["route53.key"] = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
        utils = salt.loader.utils(self.opts)
        funcs = salt.loader.minion_mods(
            self.opts, utils=utils, whitelist=["boto_route53", "config"]
        )
        return {
            boto_route53: {
                "__opts__": self.opts,
                "__utils__": utils,
                "__salt__": funcs,
            },
        }

    def setUp(self):
        TestCase.setUp(self)
        # __virtual__ must be caller in order for _get_conn to be injected
        boto_route53.__virtual__()
        boto_route53.__init__(self.opts)

    def tearDown(self):
        del self.opts

    @mock_route53_deprecated
    def test_create_healthcheck(self):
        """
        tests that given a valid instance id and valid ELB that
        register_instances returns True.
        """
        expected = {
            "result": {
                "CreateHealthCheckResponse": {
                    "HealthCheck": {
                        "HealthCheckConfig": {
                            "FailureThreshold": "3",
                            "IPAddress": "10.0.0.1",
                            "ResourcePath": "/",
                            "RequestInterval": "30",
                            "Type": "HTTPS",
                            "Port": "443",
                            "FullyQualifiedDomainName": "blog.saltstack.furniture",
                        },
                        "HealthCheckVersion": "1",
                    },
                },
            },
        }
        healthcheck = boto_route53.create_healthcheck(
            "10.0.0.1",
            fqdn="blog.saltstack.furniture",
            hc_type="HTTPS",
            port=443,
            resource_path="/",
        )
        del healthcheck["result"]["CreateHealthCheckResponse"]["HealthCheck"][
            "CallerReference"
        ]
        del healthcheck["result"]["CreateHealthCheckResponse"]["HealthCheck"]["Id"]
        self.assertEqual(healthcheck, expected)


class DummyConn:
    """
    Simple object housing a mock to simulate Error conditions. Each keyword
    argument passed into this will be set as MagicMock with the keyword value
    being set as the side_effect for that function.
    """

    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, MagicMock(side_effect=val))


class BotoRoute53RetryTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.boto_route53 module
    """

    _retryable_error = DNSServerError(
        555, "Rejected", body={"Error": {"Code": "Foo", "Message": "Bar"}}
    )
    _fatal_error = DNSServerError(
        666,
        "Flagrant System Error",
        body={
            "Error": {
                "Code": "SignatureDoesNotMatch",
                "Message": "Computer Over. Virus = Very Yes.",
            }
        },
    )

    def setup_loader_modules(self):
        return {
            boto_route53: {
                "__utils__": {
                    "boto.get_error": MagicMock(return_value="There was an error"),
                },
            },
        }

    def setUp(self):
        # This would normally be set by __utils__["boto.assign_funcs"], but
        # we're not running that as part of this test class, so we need to make
        # sure this attribute is present so that it can be mocked.
        boto_route53._get_conn = None  # pylint: disable=unmocked-patch

    def tearDown(self):
        delattr(boto_route53, "_get_conn")

    def test_zone_exists(self):
        """
        Tests retry behavior for zone_exists
        """
        # Retryable error (max retries reached)
        conn = DummyConn(get_zone=[self._retryable_error, self._retryable_error])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.zone_exists(
                "foo",
                error_retries=2,
            )
            assert conn.get_zone.call_count == 2
            assert result is False

        # Retryable error (passes on 2nd attempt)
        conn = DummyConn(get_zone=[self._retryable_error, True])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.zone_exists("foo")
            assert conn.get_zone.call_count == 2
            assert result is True

        # Non-retryable error (should re-raise DNSServerError)
        conn = DummyConn(get_zone=[self._fatal_error])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            try:
                result = boto_route53.zone_exists("foo")
            except DNSServerError:
                # This is the expected result
                pass
            else:
                raise Exception("DNSServerError not raised")

    @patch.object(boto, "route53", MagicMock())
    def test_create_healthcheck(self):
        """
        Tests retry behavior for create_healthcheck
        """
        # Retryable error (max retries reached)
        conn = DummyConn(
            create_health_check=[self._retryable_error, self._retryable_error]
        )
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.create_healthcheck(
                "foo",
                error_retries=2,
            )
            assert conn.create_health_check.call_count == 2
            assert result is False

        # Retryable error (passes on 2nd attempt)
        conn = DummyConn(create_health_check=[self._retryable_error, True])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.create_healthcheck("foo")
            assert conn.create_health_check.call_count == 2
            assert result == {"result": True}, result

        # Non-retryable error (should re-raise DNSServerError)
        conn = DummyConn(create_health_check=[self._fatal_error])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.create_healthcheck("foo")
            assert conn.create_health_check.call_count == 1
            assert result == {"error": "There was an error"}, result

    def test_get_record(self):
        """
        Tests retry behavior for get_record
        """
        # Retryable error (max retries reached)
        conn = DummyConn(get_zone=[self._retryable_error, self._retryable_error])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.get_record(
                "foo",
                "bar",
                "baz",
                error_retries=2,
            )
            assert conn.get_zone.call_count == 2
            assert not result

        # Retryable error (passes on 2nd attempt)
        conn = DummyConn(
            get_zone=[
                self._retryable_error,
                namedtuple("Zone", "find_records")(lambda *args, **kwargs: False),
            ]
        )
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.get_record("foo", "bar", "baz")
            assert conn.get_zone.call_count == 2
            assert not result

        # Non-retryable error (should re-raise DNSServerError)
        conn = DummyConn(get_zone=[self._fatal_error])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            try:
                result = boto_route53.get_record("foo", "bar", "baz")
            except DNSServerError:
                # This is the expected result
                pass
            else:
                raise Exception("DNSServerError not raised")

    @patch.object(boto_route53, "_wait_for_sync", MagicMock(return_value=True))
    def test_add_record(self):
        """
        Tests retry behavior for add_record
        """
        # Retryable error (max retries reached)
        zone = DummyConn(add_record=[self._retryable_error, self._retryable_error])
        zone.id = "foo"
        conn = DummyConn(get_zone=[zone])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.add_record(
                "a",
                "b",
                "c",
                "d",
                error_retries=2,
            )
            assert zone.add_record.call_count == 2
            assert not result

        # Retryable error (passes on 2nd attempt)
        zone = DummyConn(
            add_record=[self._retryable_error, namedtuple("Status", "id")("foo")]
        )
        conn = DummyConn(get_zone=[zone])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.add_record("a", "b", "c", "d")
            assert zone.add_record.call_count == 2
            assert result

        # Non-retryable error (should re-raise DNSServerError)
        zone = DummyConn(add_record=[self._fatal_error])
        conn = DummyConn(get_zone=[zone])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            try:
                result = boto_route53.add_record("a", "b", "c", "d")
            except DNSServerError:
                # This is the expected result
                pass
            else:
                raise Exception("DNSServerError not raised")

    @patch.object(boto_route53, "_wait_for_sync", MagicMock(return_value=True))
    def test_update_record(self):
        """
        Tests retry behavior for update_record
        """
        # Retryable error (max retries reached)
        zone = DummyConn(find_records=[self._retryable_error, self._retryable_error])
        conn = DummyConn(get_zone=[zone])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.update_record(
                "a",
                "b",
                "c",
                "d",
                error_retries=2,
            )
            assert zone.find_records.call_count == 2
            assert not result

        # Retryable error (passes on 2nd attempt)
        zone = DummyConn(
            find_records=[True, True],
            update_record=[self._retryable_error, namedtuple("Status", "id")("foo")],
        )
        conn = DummyConn(get_zone=[zone])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.update_record("a", "b", "c", "d")
            assert zone.update_record.call_count == 2
            assert result

        # Non-retryable error (should re-raise DNSServerError)
        zone = DummyConn(find_records=[self._fatal_error])
        conn = DummyConn(get_zone=[zone])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            try:
                result = boto_route53.update_record("a", "b", "c", "d")
            except DNSServerError:
                # This is the expected result
                pass
            else:
                raise Exception("DNSServerError not raised")

    @patch.object(boto_route53, "_wait_for_sync", MagicMock(return_value=True))
    def test_delete_record(self):
        """
        Tests retry behavior for delete_record
        """
        # Retryable error (max retries reached)
        zone = DummyConn(find_records=[self._retryable_error, self._retryable_error])
        conn = DummyConn(get_zone=[zone])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.delete_record(
                "a",
                "b",
                "c",
                "d",
                error_retries=2,
            )
            assert zone.find_records.call_count == 2
            assert not result

        # Retryable error (passes on 2nd attempt)
        zone = DummyConn(
            find_records=[True, True],
            delete_record=[self._retryable_error, namedtuple("Status", "id")("foo")],
        )
        conn = DummyConn(get_zone=[zone])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            result = boto_route53.delete_record("a", "b", "c", "d")
            assert zone.delete_record.call_count == 2
            assert result

        # Non-retryable error (should re-raise DNSServerError)
        zone = DummyConn(find_records=[self._fatal_error])
        conn = DummyConn(get_zone=[zone])
        with patch.object(boto_route53, "_get_conn", MagicMock(return_value=conn)):
            try:
                result = boto_route53.delete_record("a", "b", "c", "d")
            except DNSServerError:
                # This is the expected result
                pass
            else:
                raise Exception("DNSServerError not raised")

# TODO: Update skipped tests to expect dictionary results from the execution
#       module functions.

import os.path
import random
import string

import pytest

import salt.config
import salt.loader
import salt.modules.boto_vpc as boto_vpc
from salt._compat import importlib_metadata
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.modules.boto_vpc import _maybe_set_name_tag, _maybe_set_tags
from salt.utils.versions import Version
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

# pylint: disable=no-name-in-module,unused-import
try:
    import boto

    boto.ENDPOINTS_PATH = os.path.join(
        RUNTIME_VARS.TESTS_DIR, "unit/files/endpoints.json"
    )
    import boto3
    from boto.exception import BotoServerError

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    import moto
    from moto import mock_ec2_deprecated

    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False

    def mock_ec2_deprecated(self):
        """
        if the mock_ec2_deprecated function is not available due to import failure
        this replaces the decorated function with stub_function.
        Allows boto_vpc unit tests to use the @mock_ec2_deprecated decorator
        without a "NameError: name 'mock_ec2_deprecated' is not defined" error.
        """

        def stub_function(self):
            pass

        return stub_function


# pylint: enable=no-name-in-module,unused-import

# the boto_vpc module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto_version = "2.8.0"
required_moto_version = "1.0.0"

region = "us-east-1"
access_key = "GKTADJGHEIQSXMKKRBJ08H"
secret_key = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
conn_parameters = {
    "region": region,
    "key": access_key,
    "keyid": secret_key,
    "profile": {},
}
cidr_block = "10.0.0.0/24"
dhcp_options_parameters = {
    "domain_name": "example.com",
    "domain_name_servers": ["1.2.3.4"],
    "ntp_servers": ["5.6.7.8"],
    "netbios_name_servers": ["10.0.0.1"],
    "netbios_node_type": 2,
}
network_acl_entry_parameters = ("fake", 100, -1, "allow", cidr_block)
dhcp_options_parameters.update(conn_parameters)


def _has_required_boto():
    """
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    """
    if not HAS_BOTO:
        return False
    elif Version(boto.__version__) < Version(required_boto_version):
        return False
    else:
        return True


def _get_boto_version():
    """
    Returns the boto version
    """
    if not HAS_BOTO:
        return False
    return Version(boto.__version__)


def _get_moto_version():
    """
    Returns the moto version
    """
    try:
        return Version(str(moto.__version__))
    except AttributeError:
        try:
            return Version(importlib_metadata.version("moto"))
        except importlib_metadata.PackageNotFoundError:
            return False


def _has_required_moto():
    """
    Returns True/False boolean depending on if Moto is installed and correct
    version.
    """
    if not HAS_MOTO:
        return False
    else:
        if _get_moto_version() < Version(required_moto_version):
            return False
        return True


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipif(HAS_MOTO is False, reason="The moto module must be installed.")
@pytest.mark.skipif(
    _has_required_boto() is False,
    reason="The boto module must be greater than or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version() if HAS_BOTO else "None"
    ),
)
@pytest.mark.skipif(
    _has_required_moto() is False,
    reason="The moto version must be >= to version {}. Installed: {}".format(
        required_moto_version, _get_moto_version() if HAS_MOTO else "None"
    ),
)
class BotoVpcTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn3 = None

    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            opts, whitelist=["boto", "boto3", "args", "systemd", "path", "platform"]
        )
        return {boto_vpc: {"__utils__": utils}}

    # Set up MagicMock to replace the boto3 session
    def setUp(self):
        super().setUp()
        boto_vpc.__init__(self.opts)
        delattr(self, "opts")
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
        self.conn3 = MagicMock()
        self.addCleanup(delattr, self, "conn3")
        session_instance.client.return_value = self.conn3


class BotoVpcTestCaseMixin:
    conn = None

    def _create_vpc(self, name=None, tags=None):
        """
        Helper function to create a test vpc
        """
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        vpc = self.conn.create_vpc(cidr_block)

        _maybe_set_name_tag(name, vpc)
        _maybe_set_tags(tags, vpc)
        return vpc

    def _create_subnet(
        self,
        vpc_id,
        cidr_block="10.0.0.0/26",
        name=None,
        tags=None,
        availability_zone=None,
    ):
        """
        Helper function to create a test subnet
        """
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        subnet = self.conn.create_subnet(
            vpc_id, cidr_block, availability_zone=availability_zone
        )
        _maybe_set_name_tag(name, subnet)
        _maybe_set_tags(tags, subnet)
        return subnet

    def _create_internet_gateway(self, vpc_id, name=None, tags=None):
        """
        Helper function to create a test internet gateway
        """
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        igw = self.conn.create_internet_gateway()
        _maybe_set_name_tag(name, igw)
        _maybe_set_tags(tags, igw)
        return igw

    def _create_customer_gateway(self, vpc_id, name=None, tags=None):
        """
        Helper function to create a test customer gateway
        """
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        gw = self.conn.create_customer_gateway(vpc_id)
        _maybe_set_name_tag(name, gw)
        _maybe_set_tags(tags, gw)
        return gw

    def _create_dhcp_options(
        self,
        domain_name="example.com",
        domain_name_servers=None,
        ntp_servers=None,
        netbios_name_servers=None,
        netbios_node_type=2,
    ):
        """
        Helper function to create test dchp options
        """
        if not netbios_name_servers:
            netbios_name_servers = ["10.0.0.1"]
        if not ntp_servers:
            ntp_servers = ["5.6.7.8"]
        if not domain_name_servers:
            domain_name_servers = ["1.2.3.4"]

        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        return self.conn.create_dhcp_options(
            domain_name=domain_name,
            domain_name_servers=domain_name_servers,
            ntp_servers=ntp_servers,
            netbios_name_servers=netbios_name_servers,
            netbios_node_type=netbios_node_type,
        )

    def _create_network_acl(self, vpc_id):
        """
        Helper function to create test network acl
        """
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        return self.conn.create_network_acl(vpc_id)

    def _create_network_acl_entry(
        self,
        network_acl_id,
        rule_number,
        protocol,
        rule_action,
        cidr_block,
        egress=None,
        icmp_code=None,
        icmp_type=None,
        port_range_from=None,
        port_range_to=None,
    ):
        """
        Helper function to create test network acl entry
        """
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        return self.conn.create_network_acl_entry(
            network_acl_id,
            rule_number,
            protocol,
            rule_action,
            cidr_block,
            egress=egress,
            icmp_code=icmp_code,
            icmp_type=icmp_type,
            port_range_from=port_range_from,
            port_range_to=port_range_to,
        )

    def _create_route_table(self, vpc_id, name=None, tags=None):
        """
        Helper function to create a test route table
        """
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        rtbl = self.conn.create_route_table(vpc_id)
        _maybe_set_name_tag(name, rtbl)
        _maybe_set_tags(tags, rtbl)
        return rtbl


class BotoVpcTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    """
    TestCase for salt.modules.boto_vpc module
    """

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_vpc_exists_by_id_and_a_vpc_exists_the_vpc_exists_method_returns_true(
        self,
    ):
        """
        Tests checking vpc existence via id when the vpc already exists
        """
        vpc = self._create_vpc()

        vpc_exists_result = boto_vpc.exists(vpc_id=vpc.id, **conn_parameters)

        self.assertTrue(vpc_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_vpc_exists_by_id_and_a_vpc_does_not_exist_the_vpc_exists_method_returns_false(
        self,
    ):
        """
        Tests checking vpc existence via id when the vpc does not exist
        """
        self._create_vpc()  # Created to ensure that the filters are applied correctly

        vpc_exists_result = boto_vpc.exists(vpc_id="fake", **conn_parameters)

        self.assertFalse(vpc_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_vpc_exists_by_name_and_a_vpc_exists_the_vpc_exists_method_returns_true(
        self,
    ):
        """
        Tests checking vpc existence via name when vpc exists
        """
        self._create_vpc(name="test")

        vpc_exists_result = boto_vpc.exists(name="test", **conn_parameters)

        self.assertTrue(vpc_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_vpc_exists_by_name_and_a_vpc_does_not_exist_the_vpc_exists_method_returns_false(
        self,
    ):
        """
        Tests checking vpc existence via name when vpc does not exist
        """
        self._create_vpc()  # Created to ensure that the filters are applied correctly

        vpc_exists_result = boto_vpc.exists(name="test", **conn_parameters)

        self.assertFalse(vpc_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_vpc_exists_by_tags_and_a_vpc_exists_the_vpc_exists_method_returns_true(
        self,
    ):
        """
        Tests checking vpc existence via tag when vpc exists
        """
        self._create_vpc(tags={"test": "testvalue"})

        vpc_exists_result = boto_vpc.exists(
            tags={"test": "testvalue"}, **conn_parameters
        )

        self.assertTrue(vpc_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_vpc_exists_by_tags_and_a_vpc_does_not_exist_the_vpc_exists_method_returns_false(
        self,
    ):
        """
        Tests checking vpc existence via tag when vpc does not exist
        """
        self._create_vpc()  # Created to ensure that the filters are applied correctly

        vpc_exists_result = boto_vpc.exists(
            tags={"test": "testvalue"}, **conn_parameters
        )

        self.assertFalse(vpc_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_vpc_exists_by_cidr_and_a_vpc_exists_the_vpc_exists_method_returns_true(
        self,
    ):
        """
        Tests checking vpc existence via cidr when vpc exists
        """
        self._create_vpc()

        vpc_exists_result = boto_vpc.exists(cidr="10.0.0.0/24", **conn_parameters)

        self.assertTrue(vpc_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_vpc_exists_by_cidr_and_a_vpc_does_not_exist_the_vpc_exists_method_returns_false(
        self,
    ):
        """
        Tests checking vpc existence via cidr when vpc does not exist
        """
        self._create_vpc()  # Created to ensure that the filters are applied correctly

        vpc_exists_result = boto_vpc.exists(cidr="10.10.10.10/24", **conn_parameters)

        self.assertFalse(vpc_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_vpc_exists_but_providing_no_filters_the_vpc_exists_method_raises_a_salt_invocation_error(
        self,
    ):
        """
        Tests checking vpc existence when no filters are provided
        """
        with self.assertRaisesRegex(
            SaltInvocationError,
            "At least one of the following "
            "must be provided: vpc_id, vpc_name, "
            "cidr or tags.",
        ):
            boto_vpc.exists(**conn_parameters)

    @mock_ec2_deprecated
    def test_get_vpc_id_method_when_filtering_by_name(self):
        """
        Tests getting vpc id when filtering by name
        """
        vpc = self._create_vpc(name="test")

        get_id_result = boto_vpc.get_id(name="test", **conn_parameters)

        self.assertEqual(vpc.id, get_id_result["id"])

    @mock_ec2_deprecated
    def test_get_vpc_id_method_when_filtering_by_invalid_name(self):
        """
        Tests getting vpc id when filtering by invalid name
        """
        self._create_vpc(name="test")

        get_id_result = boto_vpc.get_id(name="test_fake", **conn_parameters)

        self.assertEqual(get_id_result["id"], None)

    @mock_ec2_deprecated
    def test_get_vpc_id_method_when_filtering_by_cidr(self):
        """
        Tests getting vpc id when filtering by cidr
        """
        vpc = self._create_vpc()

        get_id_result = boto_vpc.get_id(cidr="10.0.0.0/24", **conn_parameters)

        self.assertEqual(vpc.id, get_id_result["id"])

    @mock_ec2_deprecated
    def test_get_vpc_id_method_when_filtering_by_invalid_cidr(self):
        """
        Tests getting vpc id when filtering by invalid cidr
        """
        self._create_vpc()

        get_id_result = boto_vpc.get_id(cidr="10.10.10.10/24", **conn_parameters)

        self.assertEqual(get_id_result["id"], None)

    @mock_ec2_deprecated
    def test_get_vpc_id_method_when_filtering_by_tags(self):
        """
        Tests getting vpc id when filtering by tags
        """
        vpc = self._create_vpc(tags={"test": "testvalue"})

        get_id_result = boto_vpc.get_id(tags={"test": "testvalue"}, **conn_parameters)

        self.assertEqual(vpc.id, get_id_result["id"])

    @mock_ec2_deprecated
    def test_get_vpc_id_method_when_filtering_by_invalid_tags(self):
        """
        Tests getting vpc id when filtering by invalid tags
        """
        self._create_vpc(tags={"test": "testvalue"})

        get_id_result = boto_vpc.get_id(
            tags={"test": "fake-testvalue"}, **conn_parameters
        )

        self.assertEqual(get_id_result["id"], None)

    @mock_ec2_deprecated
    def test_get_vpc_id_method_when_not_providing_filters_raises_a_salt_invocation_error(
        self,
    ):
        """
        Tests getting vpc id but providing no filters
        """
        with self.assertRaisesRegex(
            SaltInvocationError,
            "At least one of the following must be provided: vpc_name, cidr or tags.",
        ):
            boto_vpc.get_id(**conn_parameters)

    @mock_ec2_deprecated
    def test_get_vpc_id_method_when_more_than_one_vpc_is_matched_raises_a_salt_command_execution_error(
        self,
    ):
        """
        Tests getting vpc id but providing no filters
        """
        vpc1 = self._create_vpc(name="vpc-test1")
        vpc2 = self._create_vpc(name="vpc-test2")

        with self.assertRaisesRegex(
            CommandExecutionError, "Found more than one VPC matching the criteria."
        ):
            boto_vpc.get_id(cidr="10.0.0.0/24", **conn_parameters)

    @mock_ec2_deprecated
    def test_that_when_creating_a_vpc_succeeds_the_create_vpc_method_returns_true(self):
        """
        tests True VPC created.
        """
        vpc_creation_result = boto_vpc.create(cidr_block, **conn_parameters)

        self.assertTrue(vpc_creation_result)

    @mock_ec2_deprecated
    def test_that_when_creating_a_vpc_and_specifying_a_vpc_name_succeeds_the_create_vpc_method_returns_true(
        self,
    ):
        """
        tests True VPC created.
        """
        vpc_creation_result = boto_vpc.create(
            cidr_block, vpc_name="test", **conn_parameters
        )

        self.assertTrue(vpc_creation_result)

    @mock_ec2_deprecated
    def test_that_when_creating_a_vpc_and_specifying_tags_succeeds_the_create_vpc_method_returns_true(
        self,
    ):
        """
        tests True VPC created.
        """
        vpc_creation_result = boto_vpc.create(
            cidr_block, tags={"test": "value"}, **conn_parameters
        )

        self.assertTrue(vpc_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_creating_a_vpc_fails_the_create_vpc_method_returns_false(self):
        """
        tests False VPC not created.
        """
        with patch(
            "moto.ec2.models.VPCBackend.create_vpc",
            side_effect=BotoServerError(400, "Mocked error"),
        ):
            vpc_creation_result = boto_vpc.create(cidr_block, **conn_parameters)
            self.assertFalse(vpc_creation_result["created"])
            self.assertTrue("error" in vpc_creation_result)

    @mock_ec2_deprecated
    def test_that_when_deleting_an_existing_vpc_the_delete_vpc_method_returns_true(
        self,
    ):
        """
        Tests deleting an existing vpc
        """
        vpc = self._create_vpc()

        vpc_deletion_result = boto_vpc.delete(vpc.id, **conn_parameters)

        self.assertTrue(vpc_deletion_result)

    @mock_ec2_deprecated
    def test_that_when_deleting_a_non_existent_vpc_the_delete_vpc_method_returns_false(
        self,
    ):
        """
        Tests deleting a non-existent vpc
        """
        delete_vpc_result = boto_vpc.delete("1234", **conn_parameters)

        self.assertFalse(delete_vpc_result["deleted"])

    @mock_ec2_deprecated
    def test_that_when_describing_vpc_by_id_it_returns_the_dict_of_properties_returns_true(
        self,
    ):
        """
        Tests describing parameters via vpc id if vpc exist
        """
        # With moto 0.4.25 through 0.4.30, is_default is set to True.
        # 0.4.24 and older and 0.4.31 and newer, is_default is False
        if Version("0.4.25") <= _get_moto_version() < Version("0.4.31"):
            is_default = True
        else:
            is_default = False

        vpc = self._create_vpc(name="test", tags={"test": "testvalue"})

        describe_vpc = boto_vpc.describe(vpc_id=vpc.id, **conn_parameters)

        vpc_properties = dict(
            id=vpc.id,
            cidr_block=str(cidr_block),
            is_default=is_default,
            state="available",
            tags={"Name": "test", "test": "testvalue"},
            dhcp_options_id="dopt-7a8b9c2d",
            region="us-east-1",
            instance_tenancy="default",
        )

        self.assertEqual(describe_vpc, {"vpc": vpc_properties})

    @mock_ec2_deprecated
    def test_that_when_describing_vpc_by_id_it_returns_the_dict_of_properties_returns_false(
        self,
    ):
        """
        Tests describing parameters via vpc id if vpc does not exist
        """
        vpc = self._create_vpc(name="test", tags={"test": "testvalue"})

        describe_vpc = boto_vpc.describe(vpc_id="vpc-fake", **conn_parameters)

        self.assertFalse(describe_vpc["vpc"])

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_describing_vpc_by_id_on_connection_error_it_returns_error(self):
        """
        Tests describing parameters failure
        """
        vpc = self._create_vpc(name="test", tags={"test": "testvalue"})

        with patch(
            "moto.ec2.models.VPCBackend.get_all_vpcs",
            side_effect=BotoServerError(400, "Mocked error"),
        ):
            describe_result = boto_vpc.describe(vpc_id=vpc.id, **conn_parameters)
            self.assertTrue("error" in describe_result)

    @mock_ec2_deprecated
    def test_that_when_describing_vpc_but_providing_no_vpc_id_the_describe_method_returns_the_default_vpc(
        self,
    ):
        """
        Tests describing vpc without vpc id
        """
        describe_vpc = boto_vpc.describe(vpc_id=None, **conn_parameters)

        self.assertTrue(describe_vpc["vpc"]["is_default"])


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipif(HAS_MOTO is False, reason="The moto module must be installed.")
@pytest.mark.skipif(
    _has_required_boto() is False,
    reason="The boto module must be greater than or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
@pytest.mark.skipif(
    _has_required_moto() is False,
    reason=f"The moto version must be >= to version {required_moto_version}",
)
class BotoVpcSubnetsTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2_deprecated
    def test_get_subnet_association_single_subnet(self):
        """
        tests that given multiple subnet ids in the same VPC that the VPC ID is
        returned. The test is valuable because it uses a string as an argument
        to subnets as opposed to a list.
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)
        subnet_association = boto_vpc.get_subnet_association(
            subnets=subnet.id, **conn_parameters
        )
        self.assertEqual(vpc.id, subnet_association["vpc_id"])

    @mock_ec2_deprecated
    def test_get_subnet_association_multiple_subnets_same_vpc(self):
        """
        tests that given multiple subnet ids in the same VPC that the VPC ID is
        returned.
        """
        vpc = self._create_vpc()
        subnet_a = self._create_subnet(vpc.id, "10.0.0.0/25")
        subnet_b = self._create_subnet(vpc.id, "10.0.0.128/25")
        subnet_association = boto_vpc.get_subnet_association(
            [subnet_a.id, subnet_b.id], **conn_parameters
        )
        self.assertEqual(vpc.id, subnet_association["vpc_id"])

    @mock_ec2_deprecated
    def test_get_subnet_association_multiple_subnets_different_vpc(self):
        """
        tests that given multiple subnet ids in different VPCs that False is
        returned.
        """
        vpc_a = self._create_vpc()
        vpc_b = self.conn.create_vpc(cidr_block)
        subnet_a = self._create_subnet(vpc_a.id, "10.0.0.0/24")
        subnet_b = self._create_subnet(vpc_b.id, "10.0.0.0/24")
        subnet_association = boto_vpc.get_subnet_association(
            [subnet_a.id, subnet_b.id], **conn_parameters
        )
        self.assertEqual(set(subnet_association["vpc_ids"]), {vpc_a.id, vpc_b.id})

    @mock_ec2_deprecated
    def test_that_when_creating_a_subnet_succeeds_the_create_subnet_method_returns_true(
        self,
    ):
        """
        Tests creating a subnet successfully
        """
        vpc = self._create_vpc()

        subnet_creation_result = boto_vpc.create_subnet(
            vpc.id, "10.0.0.0/24", **conn_parameters
        )

        self.assertTrue(subnet_creation_result["created"])
        self.assertTrue("id" in subnet_creation_result)

    @mock_ec2_deprecated
    def test_that_when_creating_a_subnet_and_specifying_a_name_succeeds_the_create_subnet_method_returns_true(
        self,
    ):
        """
        Tests creating a subnet successfully when specifying a name
        """
        vpc = self._create_vpc()

        subnet_creation_result = boto_vpc.create_subnet(
            vpc.id, "10.0.0.0/24", subnet_name="test", **conn_parameters
        )

        self.assertTrue(subnet_creation_result["created"])

    @mock_ec2_deprecated
    def test_that_when_creating_a_subnet_and_specifying_tags_succeeds_the_create_subnet_method_returns_true(
        self,
    ):
        """
        Tests creating a subnet successfully when specifying a tag
        """
        vpc = self._create_vpc()

        subnet_creation_result = boto_vpc.create_subnet(
            vpc.id, "10.0.0.0/24", tags={"test": "testvalue"}, **conn_parameters
        )

        self.assertTrue(subnet_creation_result["created"])

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_creating_a_subnet_fails_the_create_subnet_method_returns_error(
        self,
    ):
        """
        Tests creating a subnet failure
        """
        vpc = self._create_vpc()

        with patch(
            "moto.ec2.models.SubnetBackend.create_subnet",
            side_effect=BotoServerError(400, "Mocked error"),
        ):
            subnet_creation_result = boto_vpc.create_subnet(
                vpc.id, "10.0.0.0/24", **conn_parameters
            )
            self.assertTrue("error" in subnet_creation_result)

    @mock_ec2_deprecated
    def test_that_when_deleting_an_existing_subnet_the_delete_subnet_method_returns_true(
        self,
    ):
        """
        Tests deleting an existing subnet
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        subnet_deletion_result = boto_vpc.delete_subnet(
            subnet_id=subnet.id, **conn_parameters
        )

        self.assertTrue(subnet_deletion_result["deleted"])

    @mock_ec2_deprecated
    def test_that_when_deleting_a_non_existent_subnet_the_delete_vpc_method_returns_false(
        self,
    ):
        """
        Tests deleting a subnet that doesn't exist
        """
        delete_subnet_result = boto_vpc.delete_subnet(
            subnet_id="1234", **conn_parameters
        )
        self.assertTrue("error" in delete_subnet_result)

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_subnet_exists_by_id_the_subnet_exists_method_returns_true(
        self,
    ):
        """
        Tests checking if a subnet exists when it does exist
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        subnet_exists_result = boto_vpc.subnet_exists(
            subnet_id=subnet.id, **conn_parameters
        )

        self.assertTrue(subnet_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_a_subnet_does_not_exist_the_subnet_exists_method_returns_false(
        self,
    ):
        """
        Tests checking if a subnet exists which doesn't exist
        """
        subnet_exists_result = boto_vpc.subnet_exists("fake", **conn_parameters)

        self.assertFalse(subnet_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_subnet_exists_by_name_the_subnet_exists_method_returns_true(
        self,
    ):
        """
        Tests checking subnet existence by name
        """
        vpc = self._create_vpc()
        self._create_subnet(vpc.id, name="test")

        subnet_exists_result = boto_vpc.subnet_exists(name="test", **conn_parameters)

        self.assertTrue(subnet_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_subnet_exists_by_name_the_subnet_does_not_exist_the_subnet_method_returns_false(
        self,
    ):
        """
        Tests checking subnet existence by name when it doesn't exist
        """
        vpc = self._create_vpc()
        self._create_subnet(vpc.id)

        subnet_exists_result = boto_vpc.subnet_exists(name="test", **conn_parameters)

        self.assertFalse(subnet_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_subnet_exists_by_tags_the_subnet_exists_method_returns_true(
        self,
    ):
        """
        Tests checking subnet existence by tag
        """
        vpc = self._create_vpc()
        self._create_subnet(vpc.id, tags={"test": "testvalue"})

        subnet_exists_result = boto_vpc.subnet_exists(
            tags={"test": "testvalue"}, **conn_parameters
        )

        self.assertTrue(subnet_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_checking_if_a_subnet_exists_by_tags_the_subnet_does_not_exist_the_subnet_method_returns_false(
        self,
    ):
        """
        Tests checking subnet existence by tag when subnet doesn't exist
        """
        vpc = self._create_vpc()
        self._create_subnet(vpc.id)

        subnet_exists_result = boto_vpc.subnet_exists(
            tags={"test": "testvalue"}, **conn_parameters
        )

        self.assertFalse(subnet_exists_result["exists"])

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_checking_if_a_subnet_exists_but_providing_no_filters_the_subnet_exists_method_raises_a_salt_invocation_error(
        self,
    ):
        """
        Tests checking subnet existence without any filters
        """
        with self.assertRaisesRegex(
            SaltInvocationError,
            "At least one of the following must be specified: "
            "subnet id, cidr, subnet_name, tags, or zones.",
        ):
            boto_vpc.subnet_exists(**conn_parameters)

    @pytest.mark.skip(reason="Skip these tests while investigating failures")
    @mock_ec2_deprecated
    def test_that_describe_subnet_by_id_for_existing_subnet_returns_correct_data(self):
        """
        Tests describing a subnet by id.
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        describe_subnet_results = boto_vpc.describe_subnet(
            region=region, key=secret_key, keyid=access_key, subnet_id=subnet.id
        )
        self.assertEqual(
            set(describe_subnet_results["subnet"].keys()),
            {"id", "cidr_block", "availability_zone", "tags"},
        )

    @mock_ec2_deprecated
    def test_that_describe_subnet_by_id_for_non_existent_subnet_returns_none(self):
        """
        Tests describing a non-existent subnet by id.
        """
        self._create_vpc()

        describe_subnet_results = boto_vpc.describe_subnet(
            region=region, key=secret_key, keyid=access_key, subnet_id="subnet-a1b2c3"
        )
        self.assertEqual(describe_subnet_results["subnet"], None)

    @mock_ec2_deprecated
    def test_that_describe_subnet_by_name_for_existing_subnet_returns_correct_data(
        self,
    ):
        """
        Tests describing a subnet by name.
        """
        vpc = self._create_vpc()
        self._create_subnet(vpc.id, name="test")

        describe_subnet_results = boto_vpc.describe_subnet(
            region=region, key=secret_key, keyid=access_key, subnet_name="test"
        )
        self.assertEqual(
            set(describe_subnet_results["subnet"].keys()),
            {"id", "vpc_id", "cidr_block", "availability_zone", "tags"},
        )

    @mock_ec2_deprecated
    def test_that_describe_subnet_by_name_for_non_existent_subnet_returns_none(self):
        """
        Tests describing a non-existent subnet by id.
        """
        self._create_vpc()

        describe_subnet_results = boto_vpc.describe_subnet(
            region=region, key=secret_key, keyid=access_key, subnet_name="test"
        )
        self.assertEqual(describe_subnet_results["subnet"], None)

    @mock_ec2_deprecated
    def test_that_describe_subnets_by_id_for_existing_subnet_returns_correct_data(self):
        """
        Tests describing multiple subnets by id.
        """
        vpc = self._create_vpc()
        subnet1 = self._create_subnet(vpc.id)
        subnet2 = self._create_subnet(vpc.id, cidr_block="10.0.0.64/26")

        describe_subnet_results = boto_vpc.describe_subnets(
            region=region,
            key=secret_key,
            keyid=access_key,
            subnet_ids=[subnet1.id, subnet2.id],
        )
        self.assertEqual(len(describe_subnet_results["subnets"]), 2)
        self.assertEqual(
            set(describe_subnet_results["subnets"][0].keys()),
            {"id", "vpc_id", "cidr_block", "availability_zone", "tags"},
        )

    @mock_ec2_deprecated
    def test_that_describe_subnets_by_name_for_existing_subnets_returns_correct_data(
        self,
    ):
        """
        Tests describing multiple subnets by id.
        """
        vpc = self._create_vpc()
        self._create_subnet(vpc.id, name="subnet1")
        self._create_subnet(vpc.id, name="subnet2", cidr_block="10.0.0.64/26")

        describe_subnet_results = boto_vpc.describe_subnets(
            region=region,
            key=secret_key,
            keyid=access_key,
            subnet_names=["subnet1", "subnet2"],
        )
        self.assertEqual(len(describe_subnet_results["subnets"]), 2)
        self.assertEqual(
            set(describe_subnet_results["subnets"][0].keys()),
            {"id", "vpc_id", "cidr_block", "availability_zone", "tags"},
        )

    @mock_ec2_deprecated
    def test_create_subnet_passes_availability_zone(self):
        """
        Tests that the availability_zone kwarg is passed on to _create_resource
        """
        vpc = self._create_vpc()
        self._create_subnet(vpc.id, name="subnet1", availability_zone="us-east-1a")
        describe_subnet_results = boto_vpc.describe_subnets(
            region=region, key=secret_key, keyid=access_key, subnet_names=["subnet1"]
        )
        self.assertEqual(
            describe_subnet_results["subnets"][0]["availability_zone"], "us-east-1a"
        )


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipif(HAS_MOTO is False, reason="The moto module must be installed.")
@pytest.mark.skipif(
    _has_required_boto() is False,
    reason="The boto module must be greater than or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcInternetGatewayTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2_deprecated
    def test_that_when_creating_an_internet_gateway_the_create_internet_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an internet gateway successfully (with no vpc id or name)
        """

        igw_creation_result = boto_vpc.create_internet_gateway(
            region=region, key=secret_key, keyid=access_key
        )
        self.assertTrue(igw_creation_result.get("created"))

    @mock_ec2_deprecated
    def test_that_when_creating_an_internet_gateway_with_non_existent_vpc_the_create_internet_gateway_method_returns_an_error(
        self,
    ):
        """
        Tests that creating an internet gateway for a non-existent VPC fails.
        """

        igw_creation_result = boto_vpc.create_internet_gateway(
            region=region, key=secret_key, keyid=access_key, vpc_name="non-existent-vpc"
        )
        self.assertTrue("error" in igw_creation_result)

    @mock_ec2_deprecated
    def test_that_when_creating_an_internet_gateway_with_vpc_name_specified_the_create_internet_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an internet gateway with vpc name specified.
        """

        self._create_vpc(name="test-vpc")

        igw_creation_result = boto_vpc.create_internet_gateway(
            region=region, key=secret_key, keyid=access_key, vpc_name="test-vpc"
        )

        self.assertTrue(igw_creation_result.get("created"))

    @mock_ec2_deprecated
    def test_that_when_creating_an_internet_gateway_with_vpc_id_specified_the_create_internet_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an internet gateway with vpc name specified.
        """

        vpc = self._create_vpc()

        igw_creation_result = boto_vpc.create_internet_gateway(
            region=region, key=secret_key, keyid=access_key, vpc_id=vpc.id
        )

        self.assertTrue(igw_creation_result.get("created"))


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipif(HAS_MOTO is False, reason="The moto module must be installed.")
@pytest.mark.skipif(
    _has_required_boto() is False,
    reason="The boto module must be greater than or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcNatGatewayTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2_deprecated
    def test_that_when_creating_an_nat_gateway_the_create_nat_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an nat gateway successfully (with subnet_id specified)
        """

        vpc = self._create_vpc()
        subnet = self._create_subnet(
            vpc.id, name="subnet1", availability_zone="us-east-1a"
        )
        ngw_creation_result = boto_vpc.create_nat_gateway(
            subnet_id=subnet.id, region=region, key=secret_key, keyid=access_key
        )
        self.assertTrue(ngw_creation_result.get("created"))

    @mock_ec2_deprecated
    def test_that_when_creating_an_nat_gateway_with_non_existent_subnet_the_create_nat_gateway_method_returns_an_error(
        self,
    ):
        """
        Tests that creating an nat gateway for a non-existent subnet fails.
        """

        ngw_creation_result = boto_vpc.create_nat_gateway(
            region=region,
            key=secret_key,
            keyid=access_key,
            subnet_name="non-existent-subnet",
        )
        self.assertTrue("error" in ngw_creation_result)

    @mock_ec2_deprecated
    def test_that_when_creating_an_nat_gateway_with_subnet_name_specified_the_create_nat_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an nat gateway with subnet name specified.
        """

        vpc = self._create_vpc()
        subnet = self._create_subnet(
            vpc.id, name="test-subnet", availability_zone="us-east-1a"
        )
        ngw_creation_result = boto_vpc.create_nat_gateway(
            region=region, key=secret_key, keyid=access_key, subnet_name="test-subnet"
        )

        self.assertTrue(ngw_creation_result.get("created"))


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipif(HAS_MOTO is False, reason="The moto module must be installed.")
@pytest.mark.skipif(
    _has_required_boto() is False,
    reason="The boto module must be greater than or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcCustomerGatewayTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_a_customer_gateway_the_create_customer_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an internet gateway successfully (with no vpc id or name)
        """

        gw_creation_result = boto_vpc.create_customer_gateway(
            "ipsec.1", "10.1.1.1", None
        )
        self.assertTrue(gw_creation_result.get("created"))

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_checking_if_a_subnet_exists_by_id_the_subnet_exists_method_returns_true(
        self,
    ):
        """
        Tests checking if a subnet exists when it does exist
        """

        gw_creation_result = boto_vpc.create_customer_gateway(
            "ipsec.1", "10.1.1.1", None
        )
        gw_exists_result = boto_vpc.customer_gateway_exists(
            customer_gateway_id=gw_creation_result["id"]
        )
        self.assertTrue(gw_exists_result["exists"])

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_a_subnet_does_not_exist_the_subnet_exists_method_returns_false(
        self,
    ):
        """
        Tests checking if a subnet exists which doesn't exist
        """
        gw_exists_result = boto_vpc.customer_gateway_exists("fake")
        self.assertFalse(gw_exists_result["exists"])


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipif(HAS_MOTO is False, reason="The moto module must be installed.")
@pytest.mark.skipif(
    _has_required_boto() is False,
    reason="The boto module must be greater than or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
@pytest.mark.skipif(
    _has_required_moto() is False,
    reason=f"The moto version must be >= to version {required_moto_version}",
)
class BotoVpcDHCPOptionsTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2_deprecated
    def test_that_when_creating_dhcp_options_succeeds_the_create_dhcp_options_method_returns_true(
        self,
    ):
        """
        Tests creating dhcp options successfully
        """
        dhcp_options_creation_result = boto_vpc.create_dhcp_options(
            **dhcp_options_parameters
        )

        self.assertTrue(dhcp_options_creation_result["created"])

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_dhcp_options_and_specifying_a_name_succeeds_the_create_dhcp_options_method_returns_true(
        self,
    ):
        """
        Tests creating dchp options with name successfully
        """
        dhcp_options_creation_result = boto_vpc.create_dhcp_options(
            dhcp_options_name="test", **dhcp_options_parameters
        )

        self.assertTrue(dhcp_options_creation_result["created"])

    @mock_ec2_deprecated
    def test_that_when_creating_dhcp_options_and_specifying_tags_succeeds_the_create_dhcp_options_method_returns_true(
        self,
    ):
        """
        Tests creating dchp options with tag successfully
        """
        dhcp_options_creation_result = boto_vpc.create_dhcp_options(
            tags={"test": "testvalue"}, **dhcp_options_parameters
        )

        self.assertTrue(dhcp_options_creation_result["created"])

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_creating_dhcp_options_fails_the_create_dhcp_options_method_returns_error(
        self,
    ):
        """
        Tests creating dhcp options failure
        """
        with patch(
            "moto.ec2.models.DHCPOptionsSetBackend.create_dhcp_options",
            side_effect=BotoServerError(400, "Mocked error"),
        ):
            r = dhcp_options_creation_result = boto_vpc.create_dhcp_options(
                **dhcp_options_parameters
            )
            self.assertTrue("error" in r)

    @mock_ec2_deprecated
    def test_that_when_associating_an_existing_dhcp_options_set_to_an_existing_vpc_the_associate_dhcp_options_method_returns_true(
        self,
    ):
        """
        Tests associating existing dchp options successfully
        """
        vpc = self._create_vpc()
        dhcp_options = self._create_dhcp_options()

        dhcp_options_association_result = boto_vpc.associate_dhcp_options_to_vpc(
            dhcp_options.id, vpc.id, **conn_parameters
        )

        self.assertTrue(dhcp_options_association_result["associated"])

    @mock_ec2_deprecated
    def test_that_when_associating_a_non_existent_dhcp_options_set_to_an_existing_vpc_the_associate_dhcp_options_method_returns_error(
        self,
    ):
        """
        Tests associating non-existanct dhcp options successfully
        """
        vpc = self._create_vpc()

        dhcp_options_association_result = boto_vpc.associate_dhcp_options_to_vpc(
            "fake", vpc.id, **conn_parameters
        )

        self.assertTrue("error" in dhcp_options_association_result)

    @mock_ec2_deprecated
    def test_that_when_associating_an_existing_dhcp_options_set_to_a_non_existent_vpc_the_associate_dhcp_options_method_returns_false(
        self,
    ):
        """
        Tests associating existing dhcp options to non-existence vpc
        """
        dhcp_options = self._create_dhcp_options()

        dhcp_options_association_result = boto_vpc.associate_dhcp_options_to_vpc(
            dhcp_options.id, "fake", **conn_parameters
        )

        self.assertTrue("error" in dhcp_options_association_result)

    @mock_ec2_deprecated
    def test_that_when_creating_dhcp_options_set_to_an_existing_vpc_succeeds_the_associate_new_dhcp_options_method_returns_true(
        self,
    ):
        """
        Tests creation/association of dchp options to an existing vpc successfully
        """
        vpc = self._create_vpc()

        dhcp_creation_result = boto_vpc.create_dhcp_options(
            vpc_id=vpc.id, **dhcp_options_parameters
        )

        self.assertTrue(dhcp_creation_result["created"])

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_creating_and_associating_dhcp_options_set_to_an_existing_vpc_fails_creating_the_dhcp_options_the_associate_new_dhcp_options_method_raises_exception(
        self,
    ):
        """
        Tests creation failure during creation/association of dchp options to an existing vpc
        """
        vpc = self._create_vpc()

        with patch(
            "moto.ec2.models.DHCPOptionsSetBackend.create_dhcp_options",
            side_effect=BotoServerError(400, "Mocked error"),
        ):
            r = boto_vpc.associate_new_dhcp_options_to_vpc(
                vpc.id, **dhcp_options_parameters
            )
            self.assertTrue("error" in r)

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_creating_and_associating_dhcp_options_set_to_an_existing_vpc_fails_associating_the_dhcp_options_the_associate_new_dhcp_options_method_raises_exception(
        self,
    ):
        """
        Tests association failure during creation/association of dchp options to existing vpc
        """
        vpc = self._create_vpc()

        with patch(
            "moto.ec2.models.DHCPOptionsSetBackend.associate_dhcp_options",
            side_effect=BotoServerError(400, "Mocked error"),
        ):
            r = boto_vpc.associate_new_dhcp_options_to_vpc(
                vpc.id, **dhcp_options_parameters
            )
            self.assertTrue("error" in r)

    @mock_ec2_deprecated
    def test_that_when_creating_dhcp_options_set_to_a_non_existent_vpc_the_dhcp_options_the_associate_new_dhcp_options_method_returns_false(
        self,
    ):
        """
        Tests creation/association of dhcp options to non-existent vpc
        """

        r = boto_vpc.create_dhcp_options(vpc_name="fake", **dhcp_options_parameters)
        self.assertTrue("error" in r)

    @mock_ec2_deprecated
    def test_that_when_dhcp_options_exists_the_dhcp_options_exists_method_returns_true(
        self,
    ):
        """
        Tests existence of dhcp options successfully
        """
        dhcp_options = self._create_dhcp_options()

        dhcp_options_exists_result = boto_vpc.dhcp_options_exists(
            dhcp_options.id, **conn_parameters
        )

        self.assertTrue(dhcp_options_exists_result["exists"])

    @mock_ec2_deprecated
    def test_that_when_dhcp_options_do_not_exist_the_dhcp_options_exists_method_returns_false(
        self,
    ):
        """
        Tests existence of dhcp options failure
        """
        r = boto_vpc.dhcp_options_exists("fake", **conn_parameters)
        self.assertFalse(r["exists"])

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_checking_if_dhcp_options_exists_but_providing_no_filters_the_dhcp_options_exists_method_raises_a_salt_invocation_error(
        self,
    ):
        """
        Tests checking dhcp option existence with no filters
        """
        with self.assertRaisesRegex(
            SaltInvocationError,
            "At least one of the following must be provided: id, name, or tags.",
        ):
            boto_vpc.dhcp_options_exists(**conn_parameters)


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipif(HAS_MOTO is False, reason="The moto module must be installed.")
@pytest.mark.skipif(
    _has_required_boto() is False,
    reason="The boto module must be greater than or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcNetworkACLTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2_deprecated
    def test_that_when_creating_network_acl_for_an_existing_vpc_the_create_network_acl_method_returns_true(
        self,
    ):
        """
        Tests creation of network acl with existing vpc
        """
        vpc = self._create_vpc()

        network_acl_creation_result = boto_vpc.create_network_acl(
            vpc.id, **conn_parameters
        )

        self.assertTrue(network_acl_creation_result)

    @mock_ec2_deprecated
    def test_that_when_creating_network_acl_for_an_existing_vpc_and_specifying_a_name_the_create_network_acl_method_returns_true(
        self,
    ):
        """
        Tests creation of network acl via name with an existing vpc
        """
        vpc = self._create_vpc()

        network_acl_creation_result = boto_vpc.create_network_acl(
            vpc.id, network_acl_name="test", **conn_parameters
        )

        self.assertTrue(network_acl_creation_result)

    @mock_ec2_deprecated
    def test_that_when_creating_network_acl_for_an_existing_vpc_and_specifying_tags_the_create_network_acl_method_returns_true(
        self,
    ):
        """
        Tests creation of network acl via tags with an existing vpc
        """
        vpc = self._create_vpc()

        network_acl_creation_result = boto_vpc.create_network_acl(
            vpc.id, tags={"test": "testvalue"}, **conn_parameters
        )

        self.assertTrue(network_acl_creation_result)

    @mock_ec2_deprecated
    def test_that_when_creating_network_acl_for_a_non_existent_vpc_the_create_network_acl_method_returns_an_error(
        self,
    ):
        """
        Tests creation of network acl with a non-existent vpc
        """
        network_acl_creation_result = boto_vpc.create_network_acl(
            "fake", **conn_parameters
        )

        self.assertTrue("error" in network_acl_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_network_acl_fails_the_create_network_acl_method_returns_false(
        self,
    ):
        """
        Tests creation of network acl failure
        """
        vpc = self._create_vpc()

        with patch(
            "moto.ec2.models.NetworkACLBackend.create_network_acl",
            side_effect=BotoServerError(400, "Mocked error"),
        ):
            network_acl_creation_result = boto_vpc.create_network_acl(
                vpc.id, **conn_parameters
            )

        self.assertFalse(network_acl_creation_result)

    @mock_ec2_deprecated
    def test_that_when_deleting_an_existing_network_acl_the_delete_network_acl_method_returns_true(
        self,
    ):
        """
        Tests deletion of existing network acl successfully
        """
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)

        network_acl_deletion_result = boto_vpc.delete_network_acl(
            network_acl.id, **conn_parameters
        )

        self.assertTrue(network_acl_deletion_result)

    @mock_ec2_deprecated
    def test_that_when_deleting_a_non_existent_network_acl_the_delete_network_acl_method_returns_an_error(
        self,
    ):
        """
        Tests deleting a non-existent network acl
        """
        network_acl_deletion_result = boto_vpc.delete_network_acl(
            "fake", **conn_parameters
        )

        self.assertTrue("error" in network_acl_deletion_result)

    @mock_ec2_deprecated
    def test_that_when_a_network_acl_exists_the_network_acl_exists_method_returns_true(
        self,
    ):
        """
        Tests existence of network acl
        """
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)

        network_acl_deletion_result = boto_vpc.network_acl_exists(
            network_acl.id, **conn_parameters
        )

        self.assertTrue(network_acl_deletion_result)

    @mock_ec2_deprecated
    def test_that_when_a_network_acl_does_not_exist_the_network_acl_exists_method_returns_false(
        self,
    ):
        """
        Tests checking network acl does not exist
        """
        network_acl_deletion_result = boto_vpc.network_acl_exists(
            "fake", **conn_parameters
        )

        self.assertFalse(network_acl_deletion_result["exists"])

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_checking_if_network_acl_exists_but_providing_no_filters_the_network_acl_exists_method_raises_a_salt_invocation_error(
        self,
    ):
        """
        Tests checking existence of network acl with no filters
        """
        with self.assertRaisesRegex(
            SaltInvocationError,
            "At least one of the following must be provided: id, name, or tags.",
        ):
            boto_vpc.dhcp_options_exists(**conn_parameters)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_a_network_acl_entry_successfully_the_create_network_acl_entry_method_returns_true(
        self,
    ):
        """
        Tests creating network acl successfully
        """
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)

        network_acl_entry_creation_result = boto_vpc.create_network_acl_entry(
            network_acl.id, *network_acl_entry_parameters, **conn_parameters
        )

        self.assertTrue(network_acl_entry_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_a_network_acl_entry_for_a_non_existent_network_acl_the_create_network_acl_entry_method_returns_false(
        self,
    ):
        """
        Tests creating network acl entry for non-existent network acl
        """
        network_acl_entry_creation_result = boto_vpc.create_network_acl_entry(
            *network_acl_entry_parameters, **conn_parameters
        )

        self.assertFalse(network_acl_entry_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_replacing_a_network_acl_entry_successfully_the_replace_network_acl_entry_method_returns_true(
        self,
    ):
        """
        Tests replacing network acl entry successfully
        """
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)
        self._create_network_acl_entry(network_acl.id, *network_acl_entry_parameters)

        network_acl_entry_creation_result = boto_vpc.replace_network_acl_entry(
            network_acl.id, *network_acl_entry_parameters, **conn_parameters
        )

        self.assertTrue(network_acl_entry_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_replacing_a_network_acl_entry_for_a_non_existent_network_acl_the_replace_network_acl_entry_method_returns_false(
        self,
    ):
        """
        Tests replacing a network acl entry for a non-existent network acl
        """
        network_acl_entry_creation_result = boto_vpc.create_network_acl_entry(
            *network_acl_entry_parameters, **conn_parameters
        )
        self.assertFalse(network_acl_entry_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_deleting_an_existing_network_acl_entry_the_delete_network_acl_entry_method_returns_true(
        self,
    ):
        """
        Tests deleting existing network acl entry successfully
        """
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)
        network_acl_entry = self._create_network_acl_entry(
            network_acl.id, *network_acl_entry_parameters
        )

        network_acl_entry_deletion_result = boto_vpc.delete_network_acl_entry(
            network_acl_entry.id, 100, **conn_parameters
        )

        self.assertTrue(network_acl_entry_deletion_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_deleting_a_non_existent_network_acl_entry_the_delete_network_acl_entry_method_returns_false(
        self,
    ):
        """
        Tests deleting a non-existent network acl entry
        """
        network_acl_entry_deletion_result = boto_vpc.delete_network_acl_entry(
            "fake", 100, **conn_parameters
        )

        self.assertFalse(network_acl_entry_deletion_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_associating_an_existing_network_acl_to_an_existing_subnet_the_associate_network_acl_method_returns_true(
        self,
    ):
        """
        Tests association of existing network acl to existing subnet successfully
        """
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)
        subnet = self._create_subnet(vpc.id)

        network_acl_association_result = boto_vpc.associate_network_acl_to_subnet(
            network_acl.id, subnet.id, **conn_parameters
        )

        self.assertTrue(network_acl_association_result)

    @mock_ec2_deprecated
    def test_that_when_associating_a_non_existent_network_acl_to_an_existing_subnet_the_associate_network_acl_method_returns_an_error(
        self,
    ):
        """
        Tests associating a non-existent network acl to existing subnet failure
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_association_result = boto_vpc.associate_network_acl_to_subnet(
            "fake", subnet.id, **conn_parameters
        )

        self.assertTrue("error" in network_acl_association_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_associating_an_existing_network_acl_to_a_non_existent_subnet_the_associate_network_acl_method_returns_false(
        self,
    ):
        """
        Tests associating an existing network acl to a non-existent subnet
        """
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)

        network_acl_association_result = boto_vpc.associate_network_acl_to_subnet(
            network_acl.id, "fake", **conn_parameters
        )

        self.assertFalse(network_acl_association_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_and_associating_a_network_acl_to_a_subnet_succeeds_the_associate_new_network_acl_to_subnet_method_returns_true(
        self,
    ):
        """
        Tests creating/associating a network acl to a subnet to a new network
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_creation_and_association_result = (
            boto_vpc.associate_new_network_acl_to_subnet(
                vpc.id, subnet.id, **conn_parameters
            )
        )

        self.assertTrue(network_acl_creation_and_association_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_and_associating_a_network_acl_to_a_subnet_and_specifying_a_name_succeeds_the_associate_new_network_acl_to_subnet_method_returns_true(
        self,
    ):
        """
        Tests creation/association of a network acl to subnet via name successfully
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_creation_and_association_result = (
            boto_vpc.associate_new_network_acl_to_subnet(
                vpc.id, subnet.id, network_acl_name="test", **conn_parameters
            )
        )

        self.assertTrue(network_acl_creation_and_association_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_and_associating_a_network_acl_to_a_subnet_and_specifying_tags_succeeds_the_associate_new_network_acl_to_subnet_method_returns_true(
        self,
    ):
        """
        Tests creating/association of a network acl to a subnet via tag successfully
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_creation_and_association_result = (
            boto_vpc.associate_new_network_acl_to_subnet(
                vpc.id, subnet.id, tags={"test": "testvalue"}, **conn_parameters
            )
        )

        self.assertTrue(network_acl_creation_and_association_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_and_associating_a_network_acl_to_a_non_existent_subnet_the_associate_new_network_acl_to_subnet_method_returns_false(
        self,
    ):
        """
        Tests creation/association of a network acl to a non-existent vpc
        """
        vpc = self._create_vpc()

        network_acl_creation_and_association_result = (
            boto_vpc.associate_new_network_acl_to_subnet(
                vpc.id, "fake", **conn_parameters
            )
        )

        self.assertFalse(network_acl_creation_and_association_result)

    @mock_ec2_deprecated
    def test_that_when_creating_a_network_acl_to_a_non_existent_vpc_the_associate_new_network_acl_to_subnet_method_returns_an_error(
        self,
    ):
        """
        Tests creation/association of network acl to a non-existent subnet
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_creation_result = boto_vpc.create_network_acl(
            vpc_name="fake", subnet_id=subnet.id, **conn_parameters
        )

        self.assertTrue("error" in network_acl_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_disassociating_network_acl_succeeds_the_disassociate_network_acl_method_should_return_true(
        self,
    ):
        """
        Tests disassociation of network acl success
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        dhcp_disassociate_result = boto_vpc.disassociate_network_acl(
            subnet.id, vpc_id=vpc.id, **conn_parameters
        )

        self.assertTrue(dhcp_disassociate_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_disassociating_network_acl_for_a_non_existent_vpc_the_disassociate_network_acl_method_should_return_false(
        self,
    ):
        """
        Tests disassociation of network acl from non-existent vpc
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        dhcp_disassociate_result = boto_vpc.disassociate_network_acl(
            subnet.id, vpc_id="fake", **conn_parameters
        )

        self.assertFalse(dhcp_disassociate_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_disassociating_network_acl_for_a_non_existent_subnet_the_disassociate_network_acl_method_should_return_false(
        self,
    ):
        """
        Tests disassociation of network acl from non-existent subnet
        """
        vpc = self._create_vpc()

        dhcp_disassociate_result = boto_vpc.disassociate_network_acl(
            "fake", vpc_id=vpc.id, **conn_parameters
        )

        self.assertFalse(dhcp_disassociate_result)


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipif(HAS_MOTO is False, reason="The moto module must be installed.")
@pytest.mark.skipif(
    _has_required_boto() is False,
    reason="The boto module must be greater than or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcRouteTablesTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_a_route_table_succeeds_the_create_route_table_method_returns_true(
        self,
    ):
        """
        Tests creating route table successfully
        """
        vpc = self._create_vpc()

        route_table_creation_result = boto_vpc.create_route_table(
            vpc.id, **conn_parameters
        )

        self.assertTrue(route_table_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_a_route_table_on_a_non_existent_vpc_the_create_route_table_method_returns_false(
        self,
    ):
        """
        Tests creating route table on a non-existent vpc
        """
        route_table_creation_result = boto_vpc.create_route_table(
            "fake", **conn_parameters
        )

        self.assertTrue(route_table_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_deleting_a_route_table_succeeds_the_delete_route_table_method_returns_true(
        self,
    ):
        """
        Tests deleting route table successfully
        """
        vpc = self._create_vpc()
        route_table = self._create_route_table(vpc.id)

        route_table_deletion_result = boto_vpc.delete_route_table(
            route_table.id, **conn_parameters
        )

        self.assertTrue(route_table_deletion_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_deleting_a_non_existent_route_table_the_delete_route_table_method_returns_false(
        self,
    ):
        """
        Tests deleting non-existent route table
        """
        route_table_deletion_result = boto_vpc.delete_route_table(
            "fake", **conn_parameters
        )

        self.assertFalse(route_table_deletion_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_route_table_exists_the_route_table_exists_method_returns_true(
        self,
    ):
        """
        Tests existence of route table success
        """
        vpc = self._create_vpc()
        route_table = self._create_route_table(vpc.id)

        route_table_existence_result = boto_vpc.route_table_exists(
            route_table.id, **conn_parameters
        )

        self.assertTrue(route_table_existence_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_route_table_does_not_exist_the_route_table_exists_method_returns_false(
        self,
    ):
        """
        Tests existence of route table failure
        """
        route_table_existence_result = boto_vpc.route_table_exists(
            "fake", **conn_parameters
        )

        self.assertFalse(route_table_existence_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(
        reason="Disabled pending https://github.com/spulec/moto/issues/493"
    )
    def test_that_when_checking_if_a_route_table_exists_but_providing_no_filters_the_route_table_exists_method_raises_a_salt_invocation_error(
        self,
    ):
        """
        Tests checking route table without filters
        """
        with self.assertRaisesRegex(
            SaltInvocationError,
            "At least one of the following must be provided: id, name, or tags.",
        ):
            boto_vpc.dhcp_options_exists(**conn_parameters)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_associating_a_route_table_succeeds_the_associate_route_table_method_should_return_the_association_id(
        self,
    ):
        """
        Tests associating route table successfully
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)
        route_table = self._create_route_table(vpc.id)

        association_id = boto_vpc.associate_route_table(
            route_table.id, subnet.id, **conn_parameters
        )

        self.assertTrue(association_id)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_associating_a_route_table_with_a_non_existent_route_table_the_associate_route_table_method_should_return_false(
        self,
    ):
        """
        Tests associating of route table to non-existent route table
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        association_id = boto_vpc.associate_route_table(
            "fake", subnet.id, **conn_parameters
        )

        self.assertFalse(association_id)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_associating_a_route_table_with_a_non_existent_subnet_the_associate_route_table_method_should_return_false(
        self,
    ):
        """
        Tests associating of route table with non-existent subnet
        """
        vpc = self._create_vpc()
        route_table = self._create_route_table(vpc.id)

        association_id = boto_vpc.associate_route_table(
            route_table.id, "fake", **conn_parameters
        )

        self.assertFalse(association_id)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_disassociating_a_route_table_succeeds_the_disassociate_route_table_method_should_return_true(
        self,
    ):
        """
        Tests disassociation of a route
        """
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)
        route_table = self._create_route_table(vpc.id)

        association_id = self._associate_route_table(route_table.id, subnet.id)

        dhcp_disassociate_result = boto_vpc.disassociate_route_table(
            association_id, **conn_parameters
        )

        self.assertTrue(dhcp_disassociate_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_a_route_succeeds_the_create_route_method_should_return_true(
        self,
    ):
        """
        Tests successful creation of a route
        """
        vpc = self._create_vpc()
        route_table = self._create_route_table(vpc.id)

        route_creation_result = boto_vpc.create_route(
            route_table.id, cidr_block, **conn_parameters
        )

        self.assertTrue(route_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_creating_a_route_with_a_non_existent_route_table_the_create_route_method_should_return_false(
        self,
    ):
        """
        Tests creation of route on non-existent route table
        """
        route_creation_result = boto_vpc.create_route(
            "fake", cidr_block, **conn_parameters
        )

        self.assertFalse(route_creation_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_deleting_a_route_succeeds_the_delete_route_method_should_return_true(
        self,
    ):
        """
        Tests deleting route from route table
        """
        vpc = self._create_vpc()
        route_table = self._create_route_table(vpc.id)

        route_deletion_result = boto_vpc.delete_route(
            route_table.id, cidr_block, **conn_parameters
        )

        self.assertTrue(route_deletion_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_deleting_a_route_with_a_non_existent_route_table_the_delete_route_method_should_return_false(
        self,
    ):
        """
        Tests deleting route from a non-existent route table
        """
        route_deletion_result = boto_vpc.delete_route(
            "fake", cidr_block, **conn_parameters
        )

        self.assertFalse(route_deletion_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_replacing_a_route_succeeds_the_replace_route_method_should_return_true(
        self,
    ):
        """
        Tests replacing route successfully
        """
        vpc = self._create_vpc()
        route_table = self._create_route_table(vpc.id)

        route_replacing_result = boto_vpc.replace_route(
            route_table.id, cidr_block, **conn_parameters
        )

        self.assertTrue(route_replacing_result)

    @mock_ec2_deprecated
    @pytest.mark.skip(reason="Moto has not implemented this feature. Skipping for now.")
    def test_that_when_replacing_a_route_with_a_non_existent_route_table_the_replace_route_method_should_return_false(
        self,
    ):
        """
        Tests replacing a route when the route table doesn't exist
        """
        route_replacing_result = boto_vpc.replace_route(
            "fake", cidr_block, **conn_parameters
        )

        self.assertFalse(route_replacing_result)


@pytest.mark.skipif(HAS_BOTO is False, reason="The boto module must be installed.")
@pytest.mark.skipif(HAS_MOTO is False, reason="The moto module must be installed.")
@pytest.mark.skipif(
    _has_required_boto() is False,
    reason="The boto module must be greater than or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
@pytest.mark.skipif(
    _has_required_moto() is False,
    reason=f"The moto version must be >= to version {required_moto_version}",
)
class BotoVpcPeeringConnectionsTest(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2_deprecated
    def test_request_vpc_peering_connection(self):
        """
        Run with 2 vpc ids and returns a message
        """
        my_vpc = self._create_vpc()
        other_vpc = self._create_vpc()
        self.assertTrue(
            "msg"
            in boto_vpc.request_vpc_peering_connection(
                name="my_peering",
                requester_vpc_id=my_vpc.id,
                peer_vpc_id=other_vpc.id,
                **conn_parameters,
            )
        )

    @mock_ec2_deprecated
    def test_request_vpc_peering_peer_region(self):
        """
        Run with 2 vpc ids with peer_region set
        and returns a message
        """
        my_vpc = self._create_vpc()
        other_vpc = self._create_vpc()
        assert "msg" in boto_vpc.request_vpc_peering_connection(
            name="my_peering",
            requester_vpc_id=my_vpc.id,
            peer_vpc_id=other_vpc.id,
            peer_region="test_region",
            **conn_parameters,
        )

    @mock_ec2_deprecated
    def test_raises_error_if_both_vpc_name_and_vpc_id_are_specified(self):
        """
        Must specify only one
        """
        my_vpc = self._create_vpc()
        other_vpc = self._create_vpc()
        with self.assertRaises(SaltInvocationError):
            boto_vpc.request_vpc_peering_connection(
                name="my_peering",
                requester_vpc_id=my_vpc.id,
                requester_vpc_name="foobar",
                peer_vpc_id=other_vpc.id,
                **conn_parameters,
            )

        boto_vpc.request_vpc_peering_connection(
            name="my_peering",
            requester_vpc_name="my_peering",
            peer_vpc_id=other_vpc.id,
            **conn_parameters,
        )


class BotoVpcTestDeprecation(TestCase):
    def test_deprecation_58636(self):
        try:
            boto_vpc.describe_route_table
        except AttributeError:
            return
        raise AttributeError("describe_route_table should be deprecated")

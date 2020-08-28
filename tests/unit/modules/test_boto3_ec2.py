# Import Python libs

import inspect
import logging

# pylint: disable=3rd-party-module-not-gated
import pkg_resources
from pkg_resources import DistributionNotFound

# Import Salt libs
import salt.config
import salt.loader
import salt.modules.boto3_ec2 as boto3_ec2
import salt.modules.boto3_generic as boto3_generic
import salt.utils.boto3mod
import salt.utils.data
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
# pylint: disable=import-error
from salt.utils.versions import LooseVersion

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch  # pylint: disable=unused-import
from tests.support.runtests import RUNTIME_VARS  # pylint: disable=unused-import
from tests.support.unit import TestCase, skipIf

# pylint: enable=3rd-party-module-not-gated


# pylint: disable=no-name-in-module,unused-import
try:
    import boto3
    import botocore
    from botocore.exceptions import ClientError

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    import moto
    import moto.ec2.responses
    from moto import mock_ec2

    # Add mocks for functions not implemented in moto
    # mocked_functions = {
    #    'describe_vpcs': MagicMock(return_value={'Vpcs': [{'VpcId': 'vpc-12345678'}]}),
    #    'describe_subnets': MagicMock(return_value={'Subnets': [{'SubnetId': 'subnet-12345678'}]}),
    #    'describe_customer_gateways': MagicMock(return_value={'CustomerGateways': [{'CustomerGatewayId': 'cgw-12345678'}]}),
    #    'describe_network_acls': MagicMock(return_value={'NetworkAcls': [{'NetworkAclId': 'acl-12345678'}]}),
    # }
    # for function_name, mock_function in mocked_functions.items():
    #    if not hasattr(moto.ec2.ec2_backend, function_name):
    #        setattr(moto.ec2.ec2_backend, function_name, mock_function)

    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False

    def mock_ec2():
        """
        if the mock_ec2 function is not available due to import failure
        this replaces the decorated function with stub_function.
        Allows boto3_ec2 unit tests to use the @mock_ec2 decorator
        without a "NameError: name 'mock_ec2' is not defined" error.
        """

        def stub_function():
            pass

        return stub_function


log = logging.getLogger(__name__)
# pylint: enable=import-error,no-name-in-module,unused-import
required_boto_version = "1.13.0"
required_moto_version = "1.0.0"

region = "us-east-1"
access_key = "GKTADJGHEIQSXMKKRBJ08H"
secret_key = "askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs"
boto3_conn_parameters = {
    "region_name": region,
    "aws_access_key_id": access_key,
    "aws_secret_access_key": secret_key,
}
salt_conn_parameters = {
    "region": region,
    "key": access_key,
    "keyid": secret_key,
    "profile": {},
}
cidr_block = "10.0.0.0/16"
dhcp_options_parameters = {
    "domain_name": "example.com",
    "domain_name_servers": ["1.2.3.4"],
    "ntp_servers": ["5.6.7.8"],
    "netbios_name_servers": ["10.0.0.1"],
    "netbios_node_type": 2,
}


def _has_required_boto():
    """
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    """
    if not HAS_BOTO:
        return False
    elif LooseVersion(boto3.__version__) < LooseVersion(required_boto_version):
        return False
    else:
        return True


def _get_boto_version():
    """
    Returns the boto version
    """
    if not HAS_BOTO:
        return False
    return LooseVersion(boto3.__version__)


def _get_moto_version():
    """
    Returns the moto version
    """
    try:
        return LooseVersion(str(moto.__version__))
    except AttributeError:
        try:
            return LooseVersion(pkg_resources.get_distribution("moto").version)
        except DistributionNotFound:
            return False


def _has_required_moto():
    """
    Returns True/False boolean depending on if Moto is installed and correct
    version.
    """
    if not HAS_MOTO:
        return False
    else:
        if _get_moto_version() < LooseVersion(required_moto_version):
            return False
        return True


def _moto_cannot(*args):
    """
    Checks whether moto implements the specified functions in the ec2 backend.
    Used as argument with skipIf to dynamically skip tests if moto does not
    implement any of the boto3 functions used in the test.

    :param str *args: One or more (boto3) function names to check.
    :rtype: (bool, str)
    :return: True if any of the functions are not implemented
        False if all functions are implemented
        The returned string lists the functions that are not implemented.
    """
    not_implemented = [
        item
        for item in args
        if not (
            hasattr(moto.ec2.ec2_backend, item)
            or hasattr(moto.ec2.responses.EC2Response, item)
        )
    ]
    return (
        bool(not_implemented),
        "Moto does not implement: {}".format(", ".join(not_implemented)),
    )


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto module must be greater than"
    " or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version() if HAS_BOTO else "None"
    ),
)
@skipIf(
    _has_required_moto() is False,
    "The moto version must be >= to version {}. Installed: {}".format(
        required_moto_version, _get_moto_version() if HAS_MOTO else "None"
    ),
)
class BotoVpcTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn3 = None

    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            opts,
            whitelist=["boto", "boto3"],  # , "args", "systemd", "path", "platform"]
        )
        wanted_modules = {}
        for function_name, function in inspect.getmembers(
            boto3_ec2, inspect.isfunction
        ):
            wanted_modules.update({"boto3_ec2.{}".format(function_name): function})
        for function_name, function in inspect.getmembers(
            boto3_generic, inspect.isfunction
        ):
            wanted_modules.update({"boto3_generic.{}".format(function_name): function})
        ret = {
            boto3_ec2: {"__utils__": utils, "__salt__": wanted_modules},
            boto3_generic: {"__salt__": wanted_modules},
        }
        return ret

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.network_acl_entry_parameters = {
            "network_acl_id": "fake",
            "rule_number": 100,
            "protocol": "-1",
            "rule_action": "allow",
            "cidr_block": cidr_block,
            "egress": True,
        }
        cls.mock_error = {"Error": {"Code": "Mock", "Message": "Mocked error"}}
        cls.mock_errormessage = (
            "An error occurred (Mock) when calling the {} operation: Mocked error"
        )

    def setUp(self):
        super().setUp()
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        boto3_ec2.__init__(self.opts)
        delattr(self, "opts")

    def test_dummy(self):
        pass


class BotoVpcTestCaseMixin:
    """
    Helper class to setup the moto virtual cloud using boto3 directly.
    """

    conn = None
    ec2 = None

    def _create_tags(self, resource_id, tags=None):
        """
        Helper function to create tags on a resource
        """
        if not self.conn:
            self.conn = boto3.client("ec2", **boto3_conn_parameters)
        params = {
            "Resources": [resource_id],
            "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
        }
        self.conn.create_tags(**params)

    def _create_vpc(self, name=None, tags=None):
        """
        Helper function to create a test vpc

        Note that moto 1.3.14 does not support TagSpecification on create, so we
        will need to call create_tags separately.
        """
        if not self.conn:
            self.conn = boto3.client("ec2", **boto3_conn_parameters)
        if tags is None:
            tags = {}
        if name is not None:
            tags.update({"Name": name})
        params = salt.utils.data.filter_falsey({"CidrBlock": cidr_block})
        res = self.conn.create_vpc(**params)
        vpc_id = res["Vpc"]["VpcId"]
        self._create_tags(vpc_id, tags)
        return vpc_id

    def _create_subnet(
        self,
        vpc_id,
        cidr_block="10.0.0.0/25",
        name=None,
        tags=None,
        availability_zone=None,
    ):
        """
        Helper function to create a test subnet
        """
        if not self.conn:
            self.conn = boto3.client("ec2", **boto3_conn_parameters)
        if tags is None:
            tags = {}
        if name is not None:
            tags.update({"Name": name})
        params = salt.utils.data.filter_falsey(
            {
                "AvailabilityZone": availability_zone,
                "CidrBlock": cidr_block,
                "VpcId": vpc_id,
            },
            recurse_depth=1,
        )
        res = self.conn.create_subnet(**params)
        subnet_id = res["Subnet"]["SubnetId"]
        self._create_tags(subnet_id, tags)
        return subnet_id

    def _create_internet_gateway(self, vpc_id, name=None, tags=None):
        """
        Helper function to create a test internet gateway
        """
        if not self.conn:
            self.conn = boto3.client("ec2", **boto3_conn_parameters)

        if tags is None:
            tags = {}
        if name is not None:
            tags.update({"Name": name})

        res = self.conn.create_internet_gateway(VpcId=vpc_id)
        igw_id = res["InternetGateway"]["InternetGatewayId"]
        self._create_tags(igw_id, tags)
        return igw_id

    def _create_customer_gateway(self, vpc_id, name=None, tags=None):
        """
        Helper function to create a test customer gateway
        """
        if not self.conn:
            self.conn = boto3.client("ec2", **boto3_conn_parameters)

        if tags is None:
            tags = {}
        if name is not None:
            tags.update({"Name": name})
        params = salt.utils.data.filter_falsey({"VpcId": vpc_id}, recurse_depth=1)

        res = self.conn.create_customer_gateway(**params)
        cgw_id = res["CustomerGateway"]["CustomerGatewayId"]
        self._create_tags(cgw_id, tags)
        return cgw_id

    def _create_dhcp_options(
        self,
        domain_name="example.com",
        domain_name_servers=None,
        ntp_servers=None,
        netbios_name_servers=None,
        netbios_node_type="2",
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
            self.conn = boto3.client("ec2", **boto3_conn_parameters)

        res = self.conn.create_dhcp_options(
            DhcpConfigurations=[
                {"Key": "domain-name", "Values": [domain_name]},
                {"Key": "domain-name-server", "Values": domain_name_servers},
                {"Key": "ntp-servers", "Values": ntp_servers},
                {"Key": "netbios-name-servers", "Values": netbios_name_servers},
                {"Key": "netbios-node-type", "Values": [netbios_node_type]},
            ]
        )
        return res["DhcpOptions"]["DhcpOptionsId"]

    def _create_network_acl(self, vpc_id, tags=None):
        """
        Helper function to create test network acl
        """
        if not self.conn:
            self.conn = boto3.client("ec2", **boto3_conn_parameters)
        if tags is None:
            tags = {}
        res = self.conn.create_network_acl(VpcId=vpc_id)
        network_acl_id = res["NetworkAcl"]["NetworkAclId"]
        self._create_tags(network_acl_id, tags)
        return network_acl_id

    def _create_network_acl_entry(
        self,
        network_acl_id=None,
        rule_number=None,
        protocol=None,
        rule_action=None,
        cidr_block=None,
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
            self.conn = boto3.client("ec2", **boto3_conn_parameters)

        params = salt.utils.data.filter_falsey(
            {
                "NetworkAclId": network_acl_id,
                "RuleNumber": rule_number,
                "Protocol": protocol,
                "RuleAction": rule_action,
                "CidrBlock": cidr_block,
                "Egress": egress,
                "IcmpTypeCode": {"Code": icmp_code, "Type": icmp_type},
                "PortRange": {"From": port_range_from, "To": port_range_to},
            },
            recurse_depth=1,
        )

        return self.conn.create_network_acl_entry(**params)

    def _create_route_table(self, vpc_id, name=None, tags=None):
        """
        Helper function to create a test route table
        """
        if not self.conn:
            self.conn = boto3.client("ec2", **boto3_conn_parameters)

        if tags is None:
            tags = {}
        if name is not None:
            tags.update({"Name": name})
        params = salt.utils.data.filter_falsey({"VpcId": vpc_id}, recurse_depth=1)

        res = self.conn.create_route_table(**params)
        route_table_id = res["RouteTable"]["RouteTableId"]
        self._create_tags(route_table_id, tags)
        return route_table_id

    def _associate_route_table(self, route_table_id, subnet_id):
        """
        Helper function to associate a route table to a subnet.
        """
        if not self.conn:
            self.conn = boto3.client("ec2", **boto3_conn_parameters)
        res = self.conn.associate_route_table(
            RouteTableId=route_table_id, SubnetId=subnet_id,
        )
        return res["AssociationId"]


class BotoVpcTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    """
    TestCase for salt.modules.boto3_ec2 module
    """

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_checking_if_a_vpc_exists_by_id_and_a_vpc_exists_the_lookup_vpc_method_returns_it(
        self,
    ):
        """
        Tests checking vpc existence via id when the vpc already exists
        """
        vpc_id = self._create_vpc()

        res = boto3_ec2.lookup_vpc(vpc_id=vpc_id, **salt_conn_parameters)

        self.assertIn("result", res)
        self.assertEqual(res["result"]["VpcId"], vpc_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_checking_if_a_vpc_exists_by_id_and_a_vpc_does_not_exist_the_describe_vpcs_method_returns_empty(
        self,
    ):
        """
        Tests checking vpc existence via id when the vpc does not exist
        """
        self._create_vpc()  # Created to ensure that the filters are applied correctly

        res = boto3_ec2.describe_vpcs(vpc_ids="fake", **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertIn("VpcID {'fake'} does not exist.", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_checking_if_a_vpc_exists_by_name_and_a_vpc_exists_the_lookup_vpc_method_returns_it(
        self,
    ):
        """
        Tests checking vpc existence via name when vpc exists
        """
        vpc_id = self._create_vpc(name="test")

        res = boto3_ec2.lookup_vpc(vpc_name="test", **salt_conn_parameters)

        self.assertIn("result", res)
        self.assertEqual(res["result"]["VpcId"], vpc_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_checking_if_a_vpc_exists_by_name_and_a_vpc_does_not_exist_the_vpc_exists_method_returns_false(
        self,
    ):
        """
        Tests checking vpc existence via name when vpc does not exist
        """
        self._create_vpc()  # Created to ensure that the filters are applied correctly

        res = boto3_ec2.lookup_vpc(vpc_name="test", **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertEqual("No vpc found with the specified parameters", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_checking_if_a_vpc_exists_by_tags_and_a_vpc_exists_the_lookup_method_returns_it(
        self,
    ):
        """
        Tests checking vpc existence via tag when vpc exists
        """
        vpc_id = self._create_vpc(tags={"test": "testvalue"})

        res = boto3_ec2.lookup_vpc(tags={"test": "testvalue"}, **salt_conn_parameters)

        self.assertIn("result", res)
        self.assertEqual(res["result"]["VpcId"], vpc_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_checking_if_a_vpc_exists_by_tags_and_a_vpc_does_not_exist_the_lookup_method_returns_error(
        self,
    ):
        """
        Tests checking vpc existence via tag when vpc does not exist
        """
        self._create_vpc()  # Created to ensure that the filters are applied correctly

        res = boto3_ec2.lookup_vpc(tags={"test": "testvalue"}, **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertEqual("No vpc found with the specified parameters", res["error"])
        self.assertIn("result", res)
        self.assertEqual({}, res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_checking_if_a_vpc_exists_by_cidr_and_a_vpc_exists_the_vpc_exists_method_returns_true(
        self,
    ):
        """
        Tests checking vpc existence via cidr when vpc exists
        """
        vpc_id = self._create_vpc()

        res = boto3_ec2.lookup_vpc(cidr="10.0.0.0/16", **salt_conn_parameters)

        self.assertIn("result", res)
        self.assertEqual(res["result"]["VpcId"], vpc_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_checking_if_a_vpc_exists_by_cidr_and_a_vpc_does_not_exist_the_vpc_exists_method_returns_false(
        self,
    ):
        """
        Tests checking vpc existence via cidr when vpc does not exist
        """
        self._create_vpc()  # Created to ensure that the filters are applied correctly

        res = boto3_ec2.lookup_vpc(cidr="10.10.10.10/24", **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertEqual("No vpc found with the specified parameters", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_get_vpc_id_method_when_filtering_by_name(self):
        """
        Tests getting vpc id when filtering by name
        """
        vpc_id = self._create_vpc(name="test")

        res = boto3_ec2.lookup_vpc(vpc_name="test", **salt_conn_parameters)

        self.assertIn("result", res)
        self.assertEqual(res["result"]["VpcId"], vpc_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_get_vpc_id_method_when_filtering_by_invalid_name(self):
        """
        Tests getting vpc id when filtering by invalid name
        """
        self._create_vpc(name="test")

        res = boto3_ec2.lookup_vpc(vpc_name="test_fake", **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertEqual("No vpc found with the specified parameters", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_get_vpc_id_method_when_filtering_by_cidr(self):
        """
        Tests getting vpc id when filtering by cidr
        """
        vpc_id = self._create_vpc()

        res = boto3_ec2.lookup_vpc(cidr="10.0.0.0/16", **salt_conn_parameters)

        self.assertIn("result", res)
        self.assertEqual(res["result"]["VpcId"], vpc_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_get_vpc_id_method_when_filtering_by_invalid_cidr(self):
        """
        Tests getting vpc id when filtering by invalid cidr
        """
        self._create_vpc()

        res = boto3_ec2.lookup_vpc(cidr="10.10.10.10/24", **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertEqual("No vpc found with the specified parameters", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_get_vpc_id_method_when_filtering_by_tags(self):
        """
        Tests getting vpc id when filtering by tags
        """
        vpc_id = self._create_vpc(tags={"test": "testvalue"})

        res = boto3_ec2.lookup_vpc(tags={"test": "testvalue"}, **salt_conn_parameters)

        self.assertIn("result", res)
        self.assertEqual(res["result"]["VpcId"], vpc_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_get_vpc_id_method_when_filtering_by_invalid_tags(self):
        """
        Tests getting vpc id when filtering by invalid tags
        """
        self._create_vpc(tags={"test": "testvalue"})

        res = boto3_ec2.lookup_vpc(
            tags={"test": "fake-testvalue"}, **salt_conn_parameters
        )

        self.assertIn("error", res)
        self.assertEqual("No vpc found with the specified parameters", res["error"])

    @mock_ec2
    def test_get_vpc_id_method_when_not_providing_filters_raises_a_salt_invocation_error(
        self,
    ):
        """
        Tests getting vpc id but providing no filters
        """
        with self.assertRaisesRegex(
            SaltInvocationError, "No constraints where given when for lookup_vpc.",
        ):
            boto3_ec2.lookup_vpc(**salt_conn_parameters)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_get_vpc_id_method_when_more_than_one_vpc_is_matched_raises_a_salt_command_execution_error(
        self,
    ):
        """
        Tests getting vpc id but providing no filters
        """
        self._create_vpc(name="vpc-test1")
        self._create_vpc(name="vpc-test2")

        res = boto3_ec2.lookup_vpc(cidr="10.0.0.0/16", **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertEqual(
            "There are multiple vpcs with the specified filters. Please specify additional filters.",
            res["error"],
        )

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_creating_a_vpc_succeeds_the_create_vpc_method_returns_true(self):
        """
        tests True VPC created.
        """
        res = boto3_ec2.create_vpc(cidr_block, **salt_conn_parameters)

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_creating_a_vpc_and_specifying_a_vpc_name_succeeds_the_create_vpc_method_returns_true(
        self,
    ):
        """
        tests True VPC created.
        """
        res = boto3_ec2.create_vpc(
            cidr_block, tags={"Name": "test"}, **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_creating_a_vpc_fails_the_create_vpc_method_returns_false(self):
        """
        tests False VPC not created.
        """
        patch_function = "create_vpc"
        with patch(
            "moto.ec2.ec2_backend.{}".format(patch_function),
            side_effect=ClientError(self.mock_error, patch_function),
        ):
            res = boto3_ec2.create_vpc(cidr_block, **salt_conn_parameters)
        self.assertEqual(res, {"error": self.mock_errormessage.format(patch_function)})

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "delete_vpc"))
    def test_that_when_deleting_an_existing_vpc_the_delete_vpc_method_returns_true(
        self,
    ):
        """
        Tests deleting an existing vpc
        """
        vpc_id = self._create_vpc()

        res = boto3_ec2.delete_vpc(vpc_id, **salt_conn_parameters)
        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("delete_vpc"))
    def test_that_when_deleting_a_non_existent_vpc_the_delete_vpc_method_returns_false(
        self,
    ):
        """
        Tests deleting a non-existent vpc
        """
        res = boto3_ec2.delete_vpc("1234", **salt_conn_parameters)
        self.assertIn("error", res)
        self.assertIn("VpcID 1234 does not exist.", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_describing_vpc_by_id_it_returns_the_dict_of_properties_returns_true(
        self,
    ):
        """
        Tests describing parameters via vpc id if vpc exist
        """
        # With moto 0.4.25 through 0.4.30, is_default is set to True.
        # 0.4.24 and older and 0.4.31 and newer, is_default is False
        if LooseVersion("0.4.25") <= _get_moto_version() < LooseVersion("0.4.31"):
            is_default = True
        else:
            is_default = False

        vpc_id = self._create_vpc(name="test", tags={"test": "testvalue"})

        res = boto3_ec2.describe_vpcs(vpc_ids=vpc_id, **salt_conn_parameters)

        # Check individual properties as newer versions might return more
        self.assertEqual(res["result"][0]["VpcId"], vpc_id)
        self.assertEqual(res["result"][0]["CidrBlock"], cidr_block)
        self.assertEqual(res["result"][0]["IsDefault"], is_default)
        self.assertEqual(res["result"][0]["State"], "available")
        self.assertEqual(res["result"][0]["DhcpOptionsId"], "dopt-7a8b9c2d")
        self.assertEqual(res["result"][0]["InstanceTenancy"], "default")
        self.assertEqual(
            res["result"][0]["Tags"],
            [{"Key": "test", "Value": "testvalue"}, {"Key": "Name", "Value": "test"}],
        )

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_describing_vpc_by_id_it_returns_error(self,):
        """
        Tests describing parameters via vpc id if vpc does not exist
        """
        self._create_vpc(name="test", tags={"test": "testvalue"})

        res = boto3_ec2.describe_vpcs(vpc_ids="vpc-fake", **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertIn("VpcID {'vpc-fake'} does not exist.", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_when_describing_vpc_by_id_on_connection_error_it_returns_error(self):
        """
        Tests describing parameters failure
        """
        vpc_id = self._create_vpc(name="test", tags={"test": "testvalue"})

        patch_function = "get_all_vpcs"
        with patch(
            "moto.ec2.ec2_backend.{}".format(patch_function),
            side_effect=ClientError(self.mock_error, patch_function),
        ):
            res = boto3_ec2.describe_vpcs(vpc_ids=vpc_id, **salt_conn_parameters)
        self.assertEqual(res, {"error": self.mock_errormessage.format(patch_function)})


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto module must be greater than"
    " or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
@skipIf(
    _has_required_moto() is False,
    "The moto version must be >= to version {}".format(required_moto_version),
)
class BotoVpcSubnetsTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_when_creating_a_subnet_succeeds_the_create_subnet_method_returns_true(
        self,
    ):
        """
        Tests creating a subnet successfully
        """
        vpc_id = self._create_vpc()

        res = boto3_ec2.create_subnet(
            cidr_block="10.0.0.0/24", vpc_id=vpc_id, **salt_conn_parameters
        )

        self.assertTrue(res["result"])
        self.assertTrue("SubnetId" in res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_when_creating_a_subnet_and_specifying_a_name_succeeds_the_create_subnet_method_returns_true(
        self,
    ):
        """
        Tests creating a subnet successfully when specifying a name
        """
        vpc_id = self._create_vpc()

        res = boto3_ec2.create_subnet(
            cidr_block="10.0.0.0/24",
            vpc_id=vpc_id,
            tags={"Name": "test"},
            **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_when_creating_a_subnet_and_specifying_tags_succeeds_the_create_subnet_method_returns_true(
        self,
    ):
        """
        Tests creating a subnet successfully when specifying a tag
        """
        vpc_id = self._create_vpc()

        res = boto3_ec2.create_subnet(
            cidr_block="10.0.0.0/24",
            vpc_id=vpc_id,
            tags={"test": "testvalue"},
            **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_when_creating_a_subnet_fails_the_create_subnet_method_returns_error(
        self,
    ):
        """
        Tests creating a subnet failure
        """
        vpc_id = self._create_vpc()

        patch_function = "create_subnet"
        with patch(
            "moto.ec2.ec2_backend.{}".format(patch_function),
            side_effect=ClientError(self.mock_error, patch_function),
        ):
            res = boto3_ec2.create_subnet(
                cidr_block="10.0.0.0/24", vpc_id=vpc_id, **salt_conn_parameters
            )
        self.assertEqual(res, {"error": self.mock_errormessage.format(patch_function)})

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet", "delete_subnet"))
    def test_that_when_deleting_an_existing_subnet_the_delete_subnet_method_returns_true(
        self,
    ):
        """
        Tests deleting an existing subnet
        """
        vpc_id = self._create_vpc()
        subnet_id = self._create_subnet(vpc_id)

        res = boto3_ec2.delete_subnet(subnet_id=subnet_id, **salt_conn_parameters)

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("delete_subnet"))
    def test_that_when_deleting_a_non_existent_subnet_the_delete_vpc_method_returns_false(
        self,
    ):
        """
        Tests deleting a subnet that doesn't exist
        """
        delete_subnet_result = boto3_ec2.delete_subnet(
            subnet_id="1234", **salt_conn_parameters
        )
        log.debug(
            "test_that_when_deleting_a_non_existent_subnet_the_delete_vpc_method_returns_false\n"
            "\t\tres: %s",
            delete_subnet_result,
        )
        self.assertTrue("error" in delete_subnet_result)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_when_checking_if_a_subnet_exists_by_id_the_subnet_exists_method_returns_true(
        self,
    ):
        """
        Tests checking if a subnet exists when it does exist
        """
        vpc_id = self._create_vpc()
        subnet_id = self._create_subnet(vpc_id)

        res = boto3_ec2.lookup_subnet(subnet_id=subnet_id, **salt_conn_parameters)
        self.assertIn("result", res)
        self.assertIn("SubnetId", res["result"])
        self.assertIn("SubnetId", res["result"])

    @mock_ec2
    def test_that_when_a_subnet_does_not_exist_the_subnet_exists_method_returns_false(
        self,
    ):
        """
        Tests checking if a subnet exists which doesn't exist
        """
        res = boto3_ec2.lookup_subnet(subnet_id="fake", **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertEqual(res["error"], "No subnet found with the specified parameters")

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_when_checking_if_a_subnet_exists_by_name_the_subnet_exists_method_returns_true(
        self,
    ):
        """
        Tests checking subnet existence by name
        """
        vpc_id = self._create_vpc()
        subnet_id = self._create_subnet(vpc_id, name="test")

        res = boto3_ec2.lookup_subnet(subnet_name="test", **salt_conn_parameters)
        self.assertIn("result", res)
        self.assertIn("SubnetId", res["result"])
        self.assertEqual(res["result"]["SubnetId"], subnet_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_when_checking_if_a_subnet_exists_by_name_the_subnet_does_not_exist_the_subnet_method_returns_false(
        self,
    ):
        """
        Tests checking subnet existence by name when it doesn't exist
        """
        vpc_id = self._create_vpc()
        self._create_subnet(vpc_id)

        res = boto3_ec2.lookup_subnet(subnet_name="test", **salt_conn_parameters)

        self.assertIn("error", res)
        self.assertEqual(res["error"], "No subnet found with the specified parameters")

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_when_checking_if_a_subnet_exists_by_tags_the_subnet_exists_method_returns_true(
        self,
    ):
        """
        Tests checking subnet existence by tag
        """
        vpc_id = self._create_vpc()
        subnet_id = self._create_subnet(vpc_id, tags={"test": "testvalue"})

        res = boto3_ec2.lookup_subnet(
            tags={"test": "testvalue"}, **salt_conn_parameters
        )
        self.assertIn("result", res)
        self.assertIn("SubnetId", res["result"])
        self.assertEqual(res["result"]["SubnetId"], subnet_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_when_checking_if_a_subnet_exists_by_tags_the_subnet_does_not_exist_the_subnet_method_returns_false(
        self,
    ):
        """
        Tests checking subnet existence by tag when subnet doesn't exist
        """
        vpc_id = self._create_vpc()
        self._create_subnet(vpc_id)

        res = boto3_ec2.lookup_subnet(
            tags={"test": "testvalue"}, **salt_conn_parameters
        )
        self.assertIn("error", res)
        self.assertEqual(res["error"], "No subnet found with the specified parameters")

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_describe_subnet_by_id_for_existing_subnet_returns_correct_data(self):
        """
        Tests describing a subnet by id.
        """
        vpc_id = self._create_vpc()
        subnet_id = self._create_subnet(vpc_id)

        res = boto3_ec2.describe_subnets(subnet_ids=subnet_id, **salt_conn_parameters)
        self.assertIn("result", res)
        self.assertLessEqual(
            {"SubnetId", "CidrBlock", "AvailabilityZone"}, set(res["result"][0].keys()),
        )
        self.assertEqual(res["result"][0]["SubnetId"], subnet_id)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_describe_subnet_by_id_for_non_existent_subnet_returns_error(self):
        """
        Tests describing a non-existent subnet by id.
        """
        self._create_vpc()

        res = boto3_ec2.describe_subnets(
            subnet_ids="subnet-a1b2c3", **salt_conn_parameters
        )
        self.assertIn("error", res)
        self.assertIn("The subnet ID '{'subnet-a1b2c3'}' does not exist", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_describe_subnet_by_name_for_existing_subnet_returns_correct_data(
        self,
    ):
        """
        Tests describing a subnet by name.
        """
        vpc_id = self._create_vpc()
        self._create_subnet(vpc_id, name="test")

        res = boto3_ec2.describe_subnets(
            filters={"tag:Name": "test"}, **salt_conn_parameters
        )
        self.assertIn("result", res)
        self.assertLessEqual(
            {"SubnetId", "CidrBlock", "AvailabilityZone", "Tags"},
            set(res["result"][0].keys()),
        )

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc"))
    def test_that_describe_subnet_by_name_for_non_existent_subnet_returns_empty(self):
        """
        Tests describing a non-existent subnet by id.
        """
        self._create_vpc()

        res = boto3_ec2.describe_subnets(
            filters={"tag:Name": "test"}, **salt_conn_parameters
        )
        self.assertIn("result", res)
        self.assertEqual(res["result"], [])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_describe_subnets_by_id_for_existing_subnet_returns_correct_data(self):
        """
        Tests describing multiple subnets by id.
        """
        vpc_id = self._create_vpc()
        subnet1_id = self._create_subnet(vpc_id, cidr_block="10.0.1.0/24")
        subnet2_id = self._create_subnet(vpc_id, cidr_block="10.0.2.0/24")

        res = boto3_ec2.describe_subnets(
            subnet_ids=[subnet1_id, subnet2_id], **salt_conn_parameters
        )
        self.assertIn("result", res)
        self.assertEqual(len(res["result"]), 2)
        self.assertLessEqual(
            {"SubnetId", "CidrBlock", "AvailabilityZone", "State"},
            set(res["result"][0].keys()),
        )

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_that_describe_subnets_by_name_for_existing_subnets_returns_correct_data(
        self,
    ):
        """
        Tests describing multiple subnets by id.
        """
        vpc_id = self._create_vpc()
        self._create_subnet(vpc_id, name="subnet1", cidr_block="10.0.1.0/24")
        self._create_subnet(vpc_id, name="subnet2", cidr_block="10.0.2.0/24")

        res = boto3_ec2.lookup_subnet(subnet_name="subnet2", **salt_conn_parameters)
        self.assertLessEqual(
            {"SubnetId", "CidrBlock", "AvailabilityZone", "State"},
            set(res["result"].keys()),
        )

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet"))
    def test_create_subnet_passes_availability_zone(self):
        """
        Tests that the availability_zone kwarg is passed on to _create_resource
        """
        vpc_id = self._create_vpc()
        self._create_subnet(vpc_id, name="subnet1", availability_zone="us-east-1a")
        res = boto3_ec2.lookup_subnet(subnet_name="subnet1", **salt_conn_parameters)
        self.assertIn("result", res)
        self.assertEqual(res["result"]["AvailabilityZone"], "us-east-1a")


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto module must be greater than"
    " or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcInternetGatewayTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2
    @skipIf(*_moto_cannot("create_internet_gateway"))
    @skipIf(
        not hasattr(moto.ec2.ec2_backend, "create_internet_gateway"),
        "Not implemented in Moto",
    )
    def test_that_when_creating_an_internet_gateway_the_create_internet_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an internet gateway successfully (with no vpc id or name)
        """

        res = boto3_ec2.create_internet_gateway(**salt_conn_parameters)
        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_internet_gateway"))
    def test_that_when_creating_an_internet_gateway_with_non_existent_vpc_the_create_internet_gateway_method_returns_an_error(
        self,
    ):
        """
        Tests that creating an internet gateway for a non-existent VPC fails.
        """

        res = boto3_ec2.create_internet_gateway(
            vpc_lookup={"vpc_name": "non-existent-vpc"}, **salt_conn_parameters
        )
        self.assertTrue("error" in res)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_internet_gateway"))
    def test_that_when_creating_an_internet_gateway_with_vpc_name_specified_the_create_internet_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an internet gateway with vpc name specified.
        """

        self._create_vpc(name="test-vpc")

        res = boto3_ec2.create_internet_gateway(
            vpc_lookup={"vpc_name": "test-vpc"}, **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_internet_gateway"))
    def test_that_when_creating_an_internet_gateway_with_vpc_id_specified_the_create_internet_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an internet gateway with vpc name specified.
        """

        vpc_id = self._create_vpc()

        res = boto3_ec2.create_internet_gateway(vpc_id=vpc_id, **salt_conn_parameters)

        self.assertTrue(res["result"])


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto module must be greater than"
    " or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcNatGatewayTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet", "create_nat_gateway"))
    def test_that_when_creating_an_nat_gateway_the_create_nat_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an nat gateway successfully (with subnet_id specified)
        """

        vpc_id = self._create_vpc()
        subnet_id = self._create_subnet(vpc_id, availability_zone="us-east-1a")
        res = boto3_ec2.create_nat_gateway(subnet_id=subnet_id, **salt_conn_parameters)
        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_nat_gateway"))
    def test_that_when_creating_an_nat_gateway_with_non_existent_subnet_the_create_nat_gateway_method_returns_an_error(
        self,
    ):
        """
        Tests that creating an nat gateway for a non-existent subnet fails.
        """

        ngw_creation_result = boto3_ec2.create_nat_gateway(
            subnet_id="non-existent-subnet", **salt_conn_parameters
        )
        self.assertTrue("error" in ngw_creation_result)

    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc", "create_subnet", "create_nat_gateway"))
    def test_that_when_creating_an_nat_gateway_with_subnet_name_specified_the_create_nat_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an nat gateway with subnet name specified.
        """

        vpc_id = self._create_vpc()
        self._create_subnet(vpc_id, name="test-subnet", availability_zone="us-east-1a")
        res = boto3_ec2.create_nat_gateway(
            subnet_lookup={"subnet_name": "test-subnet"}, **salt_conn_parameters
        )
        self.assertIn("result", res)
        self.assertIn("NatGatewayId", res["result"])


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto module must be greater than"
    " or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcCustomerGatewayTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2
    @skipIf(*_moto_cannot("create_customer_gateway"))
    def test_that_when_creating_a_customer_gateway_the_create_customer_gateway_method_returns_true(
        self,
    ):
        """
        Tests creating an internet gateway successfully (with no vpc id or name)
        """

        res = boto3_ec2.create_customer_gateway(
            65000, "ipsec.1", public_ip="10.1.1.1", **salt_conn_parameters
        )
        self.assertTrue(res["result"])

    @mock_ec2
    def test_that_when_checking_if_a_cgw_exists_by_id_the_lookup_cgw_method_returns_true(
        self,
    ):
        """
        Tests checking if a customer gateway exists when it does exist
        """

        res = boto3_ec2.create_customer_gateway(
            65000,
            "ipsec.1",
            public_ip="10.1.1.1",
            tags={"Name": "test_cgw"},
            **salt_conn_parameters
        )
        self.assertIn("result", res)
        customer_gateway_id = res["result"]["CustomerGatewayId"]
        # Moto 1.3.14 does not support filters except filter-by-tags.
        res = boto3_ec2.lookup_customer_gateway(
            tags={"Name": "test_cgw"}, **salt_conn_parameters
        )
        self.assertIn("result", res)
        self.assertIn("CustomerGatewayId", res["result"])
        self.assertEqual(res["result"]["CustomerGatewayId"], customer_gateway_id)

    @mock_ec2
    def test_that_when_a_cgw_does_not_exist_the_describe_cgw_method_returns_empty(
        self,
    ):
        """
        Tests checking if a subnet exists which doesn't exist
        """
        res = boto3_ec2.describe_customer_gateways(
            customer_gateway_ids="fake", **salt_conn_parameters
        )
        self.assertIn("result", res)
        self.assertEqual(res["result"], [])


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto module must be greater than"
    " or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
@skipIf(
    _has_required_moto() is False,
    "The moto version must be >= to version {}".format(required_moto_version),
)
class BotoVpcDHCPOptionsTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2
    @skipIf(*_moto_cannot("create_dhcp_options"))
    def test_that_when_creating_dhcp_options_succeeds_the_create_dhcp_options_method_returns_true(
        self,
    ):
        """
        Tests creating dhcp options successfully
        """
        res = boto3_ec2.create_dhcp_options(
            **dhcp_options_parameters, **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_dhcp_options"))
    def test_that_when_creating_dhcp_options_and_specifying_a_name_succeeds_the_create_dhcp_options_method_returns_true(
        self,
    ):
        """
        Tests creating dchp options with name successfully
        """
        res = boto3_ec2.create_dhcp_options(
            tags={"Name": "test"}, **dhcp_options_parameters, **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_dhcp_options"))
    def test_that_when_creating_dhcp_options_and_specifying_tags_succeeds_the_create_dhcp_options_method_returns_true(
        self,
    ):
        """
        Tests creating dchp options with tag successfully
        """
        res = boto3_ec2.create_dhcp_options(
            tags={"test": "testvalue"},
            **dhcp_options_parameters,
            **salt_conn_parameters
        )
        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_dhcp_options"))
    def test_that_when_creating_dhcp_options_fails_the_create_dhcp_options_method_returns_error(
        self,
    ):
        """
        Tests creating dhcp options failure
        """
        patch_function = "create_dhcp_options"
        with patch(
            "moto.ec2.ec2_backend.{}".format(patch_function),
            side_effect=ClientError(self.mock_error, patch_function),
        ):
            res = boto3_ec2.create_dhcp_options(
                **dhcp_options_parameters, **salt_conn_parameters
            )
        self.assertEqual(res, {"error": self.mock_errormessage.format(patch_function)})

    @mock_ec2
    @skipIf(*_moto_cannot("associate_dhcp_options"))
    def test_that_when_associating_an_existing_dhcp_options_set_to_an_existing_vpc_the_associate_dhcp_options_method_returns_true(
        self,
    ):
        """
        Tests associating existing dchp options successfully
        """
        vpc_id = self._create_vpc()
        dhcp_options_id = self._create_dhcp_options()

        res = boto3_ec2.associate_dhcp_options(
            dhcp_options_id=dhcp_options_id, vpc_id=vpc_id, **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("associate_dhcp_options"))
    def test_that_when_associating_a_non_existent_dhcp_options_set_to_an_existing_vpc_the_associate_dhcp_options_method_returns_error(
        self,
    ):
        """
        Tests associating non-existanct dhcp options successfully
        """
        vpc_id = self._create_vpc()

        res = boto3_ec2.associate_dhcp_options(
            dhcp_options_id="fake", vpc_id=vpc_id, **salt_conn_parameters
        )
        self.assertIn("error", res)
        self.assertIn("DhcpOptionID fake does not exist.", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("associate_dhcp_options"))
    def test_that_when_associating_an_existing_dhcp_options_set_to_a_non_existent_vpc_the_associate_dhcp_options_method_returns_false(
        self,
    ):
        """
        Tests associating existing dhcp options to non-existence vpc
        """
        dhcp_options_id = self._create_dhcp_options()

        res = boto3_ec2.associate_dhcp_options(
            dhcp_options_id=dhcp_options_id, vpc_id="fake", **salt_conn_parameters
        )

        self.assertTrue("error" in res)

    @mock_ec2
    @skipIf(*_moto_cannot("describe_dhcp_options"))
    def test_that_when_dhcp_options_exists_the_dhcp_options_exists_method_returns_true(
        self,
    ):
        """
        Tests existence of dhcp options successfully
        """
        dhcp_options_id = self._create_dhcp_options()

        res = boto3_ec2.describe_dhcp_options(
            dhcp_option_ids=dhcp_options_id, **salt_conn_parameters
        )
        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("describe_dhcp_options"))
    def test_that_when_dhcp_options_do_not_exist_the_dhcp_options_exists_method_returns_false(
        self,
    ):
        """
        Tests existence of dhcp options failure
        """
        res = boto3_ec2.describe_dhcp_options("fake", **salt_conn_parameters)
        self.assertIn("error", res)
        self.assertIn("DhcpOptionID fake does not exist.", res["error"])


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto module must be greater than"
    " or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcNetworkACLTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2
    @skipIf(*_moto_cannot("create_network_acl"))
    def test_that_when_creating_network_acl_for_an_existing_vpc_the_create_network_acl_method_returns_true(
        self,
    ):
        """
        Tests creation of network acl with existing vpc
        """
        vpc_id = self._create_vpc()

        network_acl_creation_result = boto3_ec2.create_network_acl(
            vpc_id=vpc_id, **salt_conn_parameters
        )

        self.assertTrue(network_acl_creation_result)

    @mock_ec2
    @skipIf(*_moto_cannot("create_network_acl"))
    def test_that_when_creating_network_acl_for_an_existing_vpc_and_specifying_a_name_the_create_network_acl_method_returns_true(
        self,
    ):
        """
        Tests creation of network acl via name with an existing vpc
        """
        vpc_id = self._create_vpc()

        network_acl_creation_result = boto3_ec2.create_network_acl(
            vpc_id, tags={"Name": "test"}, **salt_conn_parameters
        )

        self.assertTrue(network_acl_creation_result)

    @mock_ec2
    @skipIf(*_moto_cannot("create_network_acl"))
    def test_that_when_creating_network_acl_for_an_existing_vpc_and_specifying_tags_the_create_network_acl_method_returns_true(
        self,
    ):
        """
        Tests creation of network acl via tags with an existing vpc
        """
        vpc_id = self._create_vpc()

        network_acl_creation_result = boto3_ec2.create_network_acl(
            vpc_id=vpc_id, tags={"test": "testvalue"}, **salt_conn_parameters
        )

        self.assertTrue(network_acl_creation_result)

    @mock_ec2
    @skipIf(*_moto_cannot("create_network_acl"))
    def test_that_when_creating_network_acl_for_a_non_existent_vpc_the_create_network_acl_method_returns_an_error(
        self,
    ):
        """
        Tests creation of network acl with a non-existent vpc
        """
        network_acl_creation_result = boto3_ec2.create_network_acl(
            vpc_id="fake", **salt_conn_parameters
        )

        self.assertTrue("error" in network_acl_creation_result)

    @mock_ec2
    @skipIf(*_moto_cannot("create_network_acl"))
    def test_that_when_creating_network_acl_fails_the_create_network_acl_method_returns_false(
        self,
    ):
        """
        Tests creation of network acl failure
        """
        vpc_id = self._create_vpc()

        patch_function = "create_network_acl"
        with patch(
            "moto.ec2.ec2_backend.{}".format(patch_function),
            side_effect=ClientError(self.mock_error, patch_function),
        ):
            res = boto3_ec2.create_network_acl(vpc_id=vpc_id, **salt_conn_parameters)
        self.assertEqual(res, {"error": self.mock_errormessage.format(patch_function)})

    @mock_ec2
    @skipIf(*_moto_cannot("delete_network_acl"))
    def test_that_when_deleting_an_existing_network_acl_the_delete_network_acl_method_returns_true(
        self,
    ):
        """
        Tests deletion of existing network acl successfully
        """
        vpc_id = self._create_vpc()
        network_acl_id = self._create_network_acl(vpc_id)

        res = boto3_ec2.delete_network_acl(
            network_acl_id=network_acl_id, **salt_conn_parameters
        )

        self.assertTrue(res)

    @mock_ec2
    @skipIf(*_moto_cannot("delete_network_acl"))
    def test_that_when_deleting_a_non_existent_network_acl_the_delete_network_acl_method_returns_an_error(
        self,
    ):
        """
        Tests deleting a non-existent network acl
        """
        network_acl_deletion_result = boto3_ec2.delete_network_acl(
            network_acl_id="fake", **salt_conn_parameters
        )

        self.assertTrue("error" in network_acl_deletion_result)

    @mock_ec2
    def test_that_when_a_network_acl_exists_the_lookup_network_acl_method_returns_it(
        self,
    ):
        """
        Tests existence of network acl
        """
        vpc_id = self._create_vpc()
        network_acl_id = self._create_network_acl(vpc_id, tags={"Name": "testacl"})

        # Moto 1.13.14 does not implement the network-acl-id filter, lookup by tag instead.
        res = boto3_ec2.lookup_network_acl(
            tags={"Name": "testacl"}, **salt_conn_parameters
        )

        self.assertIn("result", res)
        self.assertEqual(res["result"]["NetworkAclId"], network_acl_id)

    @mock_ec2
    def test_that_when_a_network_acl_does_not_exist_the_network_acl_exists_method_returns_false(
        self,
    ):
        """
        Tests checking network acl does not exist
        """
        res = boto3_ec2.lookup_network_acl(
            tags={"Name": "fake"}, **salt_conn_parameters
        )

        self.assertIn("error", res)
        self.assertEqual(
            res["error"], "No network_acl found with the specified parameters"
        )

    @mock_ec2
    def test_that_when_checking_if_network_acl_exists_but_providing_no_filters_the_network_acl_exists_method_raises_a_salt_invocation_error(
        self,
    ):
        """
        Tests checking existence of network acl with no filters
        """
        with self.assertRaisesRegex(
            SaltInvocationError,
            "No constraints where given when for lookup_network_acl.",
        ):
            boto3_ec2.lookup_network_acl(**salt_conn_parameters)

    @mock_ec2
    @skipIf(*_moto_cannot("create_network_acl_entry"))
    def test_that_when_creating_a_network_acl_entry_successfully_the_create_network_acl_entry_method_returns_true(
        self,
    ):
        """
        Tests creating network acl successfully
        """
        vpc_id = self._create_vpc()
        network_acl_id = self._create_network_acl(vpc_id)

        params = dict(self.network_acl_entry_parameters)
        params.update({"network_acl_id": network_acl_id})
        network_acl_entry_creation_result = boto3_ec2.create_network_acl_entry(
            **params, **salt_conn_parameters
        )

        self.assertTrue(network_acl_entry_creation_result)

    @mock_ec2
    @skipIf(*_moto_cannot("create_network_acl_entry"))
    def test_that_when_creating_a_network_acl_entry_for_a_non_existent_network_acl_the_create_network_acl_entry_method_returns_false(
        self,
    ):
        """
        Tests creating network acl entry for non-existent network acl
        """
        res = boto3_ec2.create_network_acl_entry(
            **self.network_acl_entry_parameters, **salt_conn_parameters
        )

        self.assertIn("error", res)
        self.assertIn("The network acl ID 'fake' does not exist", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("replace_network_acl_entry"))
    def test_that_when_replacing_a_network_acl_entry_successfully_the_replace_network_acl_entry_method_returns_true(
        self,
    ):
        """
        Tests replacing network acl entry successfully
        """
        vpc_id = self._create_vpc()
        network_acl_id = self._create_network_acl(vpc_id)
        params = dict(self.network_acl_entry_parameters)
        params.update({"network_acl_id": network_acl_id})
        self._create_network_acl_entry(**params)

        res = boto3_ec2.replace_network_acl_entry(**params, **salt_conn_parameters)

        self.assertIn("result", res)
        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_network_acl_entry"))
    def test_that_when_replacing_a_network_acl_entry_for_a_non_existent_network_acl_the_replace_network_acl_entry_method_returns_false(
        self,
    ):
        """
        Tests replacing a network acl entry for a non-existent network acl
        """
        res = boto3_ec2.create_network_acl_entry(
            **self.network_acl_entry_parameters, **salt_conn_parameters
        )
        self.assertIn("error", res)
        self.assertIn("The network acl ID 'fake' does not exist", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("delete_network_acl_entry"))
    def test_that_when_deleting_an_existing_network_acl_entry_the_delete_network_acl_entry_method_returns_true(
        self,
    ):
        """
        Tests deleting existing network acl entry successfully
        """
        vpc_id = self._create_vpc()
        network_acl_id = self._create_network_acl(vpc_id)
        params = dict(self.network_acl_entry_parameters)
        params.update({"network_acl_id": network_acl_id})
        self._create_network_acl_entry(**params)

        res = boto3_ec2.delete_network_acl_entry(
            100, True, network_acl_id=network_acl_id, **salt_conn_parameters
        )  # TODO: Make bugreport to moto: deleting network acl entries that do not exist is not handled properly

        self.assertIn("result", res)
        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("delete_network_acl_entry"))
    def test_that_when_deleting_a_non_existent_network_acl_entry_the_delete_network_acl_entry_method_returns_false(
        self,
    ):
        """
        Tests deleting a non-existent network acl entry
        """
        res = boto3_ec2.delete_network_acl_entry(
            100, False, network_acl_id="fake", **salt_conn_parameters
        )

        self.assertIn("error", res)
        self.assertIn("The network acl ID 'fake' does not exist", res["error"])


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto module must be greater than"
    " or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
class BotoVpcRouteTablesTestCase(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2
    @skipIf(*_moto_cannot("create_route_table"))
    def test_that_when_creating_a_route_table_succeeds_the_create_route_table_method_returns_true(
        self,
    ):
        """
        Tests creating route table successfully
        """
        vpc_id = self._create_vpc()

        route_table_creation_result = boto3_ec2.create_route_table(
            vpc_id=vpc_id, **salt_conn_parameters
        )

        self.assertTrue(route_table_creation_result)

    @mock_ec2
    @skipIf(*_moto_cannot("create_route_table"))
    def test_that_when_creating_a_route_table_on_a_non_existent_vpc_the_create_route_table_method_returns_false(
        self,
    ):
        """
        Tests creating route table on a non-existent vpc
        """
        route_table_creation_result = boto3_ec2.create_route_table(
            vpc_id="fake", **salt_conn_parameters
        )

        self.assertTrue(route_table_creation_result)

    @mock_ec2
    @skipIf(*_moto_cannot("delete_route_table"))
    def test_that_when_deleting_a_route_table_succeeds_the_delete_route_table_method_returns_true(
        self,
    ):
        """
        Tests deleting route table successfully
        """
        vpc_id = self._create_vpc()
        route_table_id = self._create_route_table(vpc_id)

        route_table_deletion_result = boto3_ec2.delete_route_table(
            route_table_id=route_table_id, **salt_conn_parameters
        )

        self.assertTrue(route_table_deletion_result)

    @mock_ec2
    @skipIf(*_moto_cannot("delete_route_table"))
    def test_that_when_deleting_a_non_existent_route_table_the_delete_route_table_method_returns_false(
        self,
    ):
        """
        Tests deleting non-existent route table
        """
        res = boto3_ec2.delete_route_table(
            route_table_id="fake", **salt_conn_parameters
        )

        self.assertIn("error", res)

    @mock_ec2
    def test_that_when_route_table_exists_the_route_table_exists_method_returns_true(
        self,
    ):
        """
        Tests existence of route table success
        """
        vpc_id = self._create_vpc()
        route_table_id = self._create_route_table(vpc_id)

        res = boto3_ec2.describe_route_tables(
            route_table_ids=route_table_id, **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    def test_that_when_route_table_does_not_exist_the_route_table_exists_method_returns_false(
        self,
    ):
        """
        Tests existence of route table failure
        """
        res = boto3_ec2.describe_route_tables(
            route_table_ids="fake", **salt_conn_parameters
        )

        self.assertIn("error", res)
        self.assertIn("The routeTable ID 'fake' does not exist", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("associate_route_table"))
    def test_that_when_associating_a_route_table_succeeds_the_associate_route_table_method_should_return_the_association_id(
        self,
    ):
        """
        Tests associating route table successfully
        """
        vpc_id = self._create_vpc()
        subnet_id = self._create_subnet(vpc_id)
        route_table_id = self._create_route_table(vpc_id)

        res = boto3_ec2.associate_route_table(
            route_table_id=route_table_id, subnet_id=subnet_id, **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("associate_route_table"))
    def test_that_when_associating_a_route_table_with_a_non_existent_route_table_the_associate_route_table_method_should_return_false(
        self,
    ):
        """
        Tests associating of route table to non-existent route table
        """
        vpc_id = self._create_vpc()
        subnet_id = self._create_subnet(vpc_id)

        res = boto3_ec2.associate_route_table(
            route_table_id="fake", subnet_id=subnet_id, **salt_conn_parameters
        )
        self.assertIn("error", res)
        self.assertIn("The routeTable ID 'fake' does not exist", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("associate_route_table"))
    def test_that_when_associating_a_route_table_with_a_non_existent_subnet_the_associate_route_table_method_should_return_false(
        self,
    ):
        """
        Tests associating of route table with non-existent subnet
        """
        vpc_id = self._create_vpc()
        route_table_id = self._create_route_table(vpc_id)

        res = boto3_ec2.associate_route_table(
            route_table_id=route_table_id, subnet_id="fake", **salt_conn_parameters
        )
        self.assertIn("error", res)
        self.assertIn("The subnet ID 'fake' does not exist", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("disassociate_route_table"))
    def test_that_when_disassociating_a_route_table_succeeds_the_disassociate_route_table_method_should_return_true(
        self,
    ):
        """
        Tests disassociation of a route
        """
        vpc_id = self._create_vpc()
        subnet_id = self._create_subnet(vpc_id)
        route_table_id = self._create_route_table(vpc_id)
        association_id = self._associate_route_table(route_table_id, subnet_id)

        res = boto3_ec2.disassociate_route_table(
            association_id=association_id, **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_route_table"))
    def test_that_when_creating_a_route_succeeds_the_create_route_method_should_return_true(
        self,
    ):
        """
        Tests successful creation of a route
        """
        vpc_id = self._create_vpc()
        route_table_id = self._create_route_table(vpc_id)

        res = boto3_ec2.create_route(
            route_table_id=route_table_id,
            destination_cidr_block=cidr_block,
            **salt_conn_parameters
        )

        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("create_route"))
    def test_that_when_creating_a_route_with_a_non_existent_route_table_the_create_route_method_should_return_false(
        self,
    ):
        """
        Tests creation of route on non-existent route table
        """
        res = boto3_ec2.create_route(
            route_table_id="fake",
            destination_cidr_block=cidr_block,
            **salt_conn_parameters
        )
        self.assertIn("error", res)
        self.assertIn("The routeTable ID 'fake' does not exist", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("delete_route"))
    def test_that_when_deleting_a_route_succeeds_the_delete_route_method_should_return_true(
        self,
    ):
        """
        Tests deleting route from route table
        """
        vpc_id = self._create_vpc()
        route_table_id = self._create_route_table(vpc_id)

        res = boto3_ec2.delete_route(
            route_table_id=route_table_id,
            destination_cidr_block=cidr_block,
            **salt_conn_parameters
        )
        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("delete_route"))
    def test_that_when_deleting_a_route_with_a_non_existent_route_table_the_delete_route_method_should_return_false(
        self,
    ):
        """
        Tests deleting route from a non-existent route table
        """
        res = boto3_ec2.delete_route(
            route_table_id="fake",
            destination_cidr_block=cidr_block,
            **salt_conn_parameters
        )
        self.assertIn("error", res)
        self.assertIn("The routeTable ID 'fake' does not exist", res["error"])

    @mock_ec2
    @skipIf(*_moto_cannot("replace_route"))
    def test_that_when_replacing_a_route_succeeds_the_replace_route_method_should_return_true(
        self,
    ):
        """
        Tests replacing route successfully
        """
        vpc_id = self._create_vpc()
        route_table_id = self._create_route_table(vpc_id)

        res = boto3_ec2.replace_route(
            route_table_id=route_table_id,
            destination_cidr_block=cidr_block,
            **salt_conn_parameters
        )
        self.assertTrue(res["result"])

    @mock_ec2
    @skipIf(*_moto_cannot("replace_route"))
    def test_that_when_replacing_a_route_with_a_non_existent_route_table_the_replace_route_method_should_return_false(
        self,
    ):
        """
        Tests replacing a route when the route table doesn't exist
        """
        res = boto3_ec2.replace_route(
            route_table_id="fake",
            destination_cidr_block=cidr_block,
            **salt_conn_parameters
        )
        self.assertIn("error", res)
        self.assertIn("The routeTable ID 'fake' does not exist", res["error"])


@skipIf(HAS_BOTO is False, "The boto module must be installed.")
@skipIf(HAS_MOTO is False, "The moto module must be installed.")
@skipIf(
    _has_required_boto() is False,
    "The boto module must be greater than"
    " or equal to version {}. Installed: {}".format(
        required_boto_version, _get_boto_version()
    ),
)
@skipIf(
    _has_required_moto() is False,
    "The moto version must be >= to version {}".format(required_moto_version),
)
class BotoVpcPeeringConnectionsTest(BotoVpcTestCaseBase, BotoVpcTestCaseMixin):
    @mock_ec2
    @skipIf(*_moto_cannot("create_vpc_peering_connection"))
    def test_request_vpc_peering_connection(self):
        """
        Run with 2 vpc ids and returns a message
        """
        my_vpc_id = self._create_vpc()
        other_vpc_id = self._create_vpc()
        res = boto3_ec2.create_vpc_peering_connection(
            requester_vpc_id=my_vpc_id, peer_vpc_id=other_vpc_id, **salt_conn_parameters
        )
        self.assertIn("result", res)
        self.assertIn("VpcPeeringConnectionId", res["result"])

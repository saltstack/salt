# -*- coding: utf-8 -*-

# import Python Third Party Libs

from boto.exception import BotoServerError
from mock import patch

from tests.utils import expectedNotImplementedFailure, expectedImportFailure


try:
    import boto

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    from moto import mock_ec2

    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False

    def mock_ec2(self):
        '''
        if the mock_ec2 function is not available due to import failure
        this replaces the decorated function with stub_function.
        Allows boto_vpc unit tests to use the @mock_ec2 decorator
        without a "NameError: name 'mock_ec2' is not defined" error.
        '''

        def stub_function(self):
            pass

        return stub_function

# Import Python libs
from distutils.version import LooseVersion

# Import Salt Libs
from salt.modules import boto_vpc

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# the boto_vpc module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto_version = '2.8.0'
region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key, 'profile': {}}
cidr_block = '10.0.0.0/24'
dhcp_options_parameters = {'domain_name': 'example.com', 'domain_name_servers': ['1.2.3.4'], 'ntp_servers': ['5.6.7.8'],
                           'netbios_name_servers': ['10.0.0.1'], 'netbios_node_type': 2}
network_acl_entry_parameters = ('fake', 100, -1, 'allow', cidr_block)
dhcp_options_parameters.update(conn_parameters)


def _has_required_boto():
    '''
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    '''
    if not HAS_BOTO:
        return False
    elif LooseVersion(boto.__version__) < LooseVersion(required_boto_version):
        return False
    else:
        return True


class BotoVpcTestCaseBase(TestCase):
    conn = None

    def _create_vpc(self):
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        return self.conn.create_vpc(cidr_block)

    def _create_subnet(self, vpc_id, cidr_block='10.0.0.0/25'):
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        return self.conn.create_subnet(vpc_id, cidr_block)

    def _create_dhcp_options(self, domain_name='example.com', domain_name_servers=None, ntp_servers=None,
                             netbios_name_servers=None, netbios_node_type=2):
        if not netbios_name_servers:
            netbios_name_servers = ['10.0.0.1']
        if not ntp_servers:
            ntp_servers = ['5.6.7.8']
        if not domain_name_servers:
            domain_name_servers = ['1.2.3.4']

        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        return self.conn.create_dhcp_options(domain_name=domain_name, domain_name_servers=domain_name_servers,
                                             ntp_servers=ntp_servers, netbios_name_servers=netbios_name_servers,
                                             netbios_node_type=netbios_node_type)

    def _create_network_acl(self, vpc_id):
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        return self.conn.create_network_acl(vpc_id)

    def _create_network_acl_entry(self, network_acl_id, rule_number, protocol, rule_action, cidr_block, egress=None,
                                  icmp_code=None, icmp_type=None, port_range_from=None, port_range_to=None):
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        return self.conn.create_network_acl_entry(network_acl_id, rule_number, protocol, rule_action,
                                                  cidr_block,
                                                  egress=egress,
                                                  icmp_code=icmp_code, icmp_type=icmp_type,
                                                  port_range_from=port_range_from, port_range_to=port_range_to)

    def _create_route_table(self, vpc_id):
        if not self.conn:
            self.conn = boto.vpc.connect_to_region(region)

        return self.conn.create_route_table(vpc_id)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoVpcTestCase(BotoVpcTestCaseBase):
    '''
    TestCase for salt.modules.boto_vpc module
    '''

    @mock_ec2
    def test_exists_true(self):
        '''
        tests True existence of a VPC.
        '''
        vpc = self._create_vpc()
        vpc_exists = boto_vpc.exists(vpc.id, **conn_parameters)
        self.assertTrue(vpc_exists)

    @mock_ec2
    def test_that_when_creating_a_vpc_succeeds_the_create_vpc_method_returns_true(self):
        '''
        tests True VPC created.
        '''
        vpc_creation_result = boto_vpc.create(cidr_block, **conn_parameters)

        self.assertTrue(vpc_creation_result)

    @mock_ec2
    def test_that_when_creating_a_vpc_and_specifying_a_vpc_name_succeeds_the_create_vpc_method_returns_true(self):
        '''
        tests True VPC created.
        '''
        vpc_creation_result = boto_vpc.create(cidr_block, vpc_name='test', **conn_parameters)

        self.assertTrue(vpc_creation_result)

    @mock_ec2
    def test_that_when_creating_a_vpc_and_specifying_tags_succeeds_the_create_vpc_method_returns_true(self):
        '''
        tests True VPC created.
        '''
        vpc_creation_result = boto_vpc.create(cidr_block, tags={'test': 'value'}, **conn_parameters)

        self.assertTrue(vpc_creation_result)

    @mock_ec2
    def test_that_when_creating_a_vpc_fails_the_create_vpc_method_returns_false(self):
        '''
        tests False VPC not created.
        '''
        with patch('moto.ec2.models.VPCBackend.create_vpc', side_effect=BotoServerError(400, 'Mocked error')):
            vpc_creation_result = boto_vpc.create(cidr_block, **conn_parameters)

        self.assertFalse(vpc_creation_result)

    @mock_ec2
    def test_that_when_deleting_an_existing_vpc_the_delete_vpc_method_returns_true(self):
        vpc = self._create_vpc()

        vpc_deletion_result = boto_vpc.delete(vpc.id, **conn_parameters)

        self.assertTrue(vpc_deletion_result)

    @mock_ec2
    def test_that_when_deleting_a_non_existent_vpc_the_delete_vpc_method_returns_false(self):
        vpc_deletion_result = boto_vpc.delete('1234', **conn_parameters)

        self.assertFalse(vpc_deletion_result)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoVpcSubnetsTestCase(BotoVpcTestCaseBase):
    @mock_ec2
    def test_get_subnet_association_single_subnet(self):
        '''
        tests that given multiple subnet ids in the same VPC that the VPC ID is
        returned. The test is valuable because it uses a string as an argument
        to subnets as opposed to a list.
        '''
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)
        subnet_association = boto_vpc.get_subnet_association(subnets=subnet.id,
                                                             **conn_parameters)
        self.assertEqual(vpc.id, subnet_association)

    @mock_ec2
    def test_get_subnet_association_multiple_subnets_same_vpc(self):
        '''
        tests that given multiple subnet ids in the same VPC that the VPC ID is
        returned.
        '''
        vpc = self._create_vpc()
        subnet_a = self._create_subnet(vpc.id, '10.0.0.0/25')
        subnet_b = self._create_subnet(vpc.id, '10.0.0.128/25')
        subnet_association = boto_vpc.get_subnet_association([subnet_a.id, subnet_b.id],
                                                             **conn_parameters)
        self.assertEqual(vpc.id, subnet_association)

    @mock_ec2
    def test_get_subnet_association_multiple_subnets_different_vpc(self):
        '''
        tests that given multiple subnet ids in different VPCs that False is
        returned.
        '''
        vpc_a = self._create_vpc()
        vpc_b = self.conn.create_vpc(cidr_block)
        subnet_a = self._create_subnet(vpc_a.id, '10.0.0.0/24')
        subnet_b = self._create_subnet(vpc_b.id, '10.0.0.0/24')
        subnet_assocation = boto_vpc.get_subnet_association([subnet_a.id, subnet_b.id],
                                                            **conn_parameters)
        self.assertFalse(subnet_assocation)

    @mock_ec2
    def test_that_when_creating_a_subnet_succeeds_the_create_subnet_method_returns_true(self):
        vpc = self._create_vpc()

        subnet_creation_result = boto_vpc.create_subnet(vpc.id, '10.0.0.0/24', **conn_parameters)

        self.assertTrue(subnet_creation_result)

    @mock_ec2
    def test_that_when_creating_a_subnet_and_specifying_a_name_succeeds_the_create_subnet_method_returns_true(self):
        vpc = self._create_vpc()

        subnet_creation_result = boto_vpc.create_subnet(vpc.id, '10.0.0.0/24', subnet_name='test', **conn_parameters)

        self.assertTrue(subnet_creation_result)

    @mock_ec2
    def test_that_when_creating_a_subnet_and_specifying_tags_succeeds_the_create_subnet_method_returns_true(self):
        vpc = self._create_vpc()

        subnet_creation_result = boto_vpc.create_subnet(vpc.id, '10.0.0.0/24', tags={'test': 'testvalue'},
                                                        **conn_parameters)

        self.assertTrue(subnet_creation_result)

    @mock_ec2
    def test_that_when_creating_a_subnet_fails_the_create_subnet_method_returns_false(self):
        vpc = self._create_vpc()

        with patch('moto.ec2.models.SubnetBackend.create_subnet', side_effect=BotoServerError(400, 'Mocked error')):
            subnet_creation_result = boto_vpc.create_subnet(vpc.id, '10.0.0.0/24', **conn_parameters)

        self.assertFalse(subnet_creation_result)

    @mock_ec2
    def test_that_when_deleting_an_existing_subnet_the_delete_subnet_method_returns_true(self):
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        subnet_deletion_result = boto_vpc.delete_subnet(subnet.id, **conn_parameters)

        self.assertTrue(subnet_deletion_result)

    @mock_ec2
    def test_that_when_deleting_a_non_existent_subnet_the_delete_vpc_method_returns_false(self):
        subnet_deletion_result = boto_vpc.delete_subnet('1234', **conn_parameters)

        self.assertFalse(subnet_deletion_result)

    @mock_ec2
    def test_that_when_a_subnet_exists_the_subnet_exists_method_returns_true(self):
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        subnet_exists_result = boto_vpc.subnet_exists(subnet.id, **conn_parameters)

        self.assertTrue(subnet_exists_result)

    @mock_ec2
    def test_that_when_a_subnet_does_not_exist_the_subnet_exists_method_returns_false(self):
        subnet_exists_result = boto_vpc.subnet_exists('fake', **conn_parameters)

        self.assertFalse(subnet_exists_result)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoVpcDHCPOptionsTestCase(BotoVpcTestCaseBase):
    @mock_ec2
    def test_when_creating_dhcp_options_succeeds_the_create_dhcp_options_method_returns_true(self):
        dhcp_options_creation_result = boto_vpc.create_dhcp_options(**dhcp_options_parameters)

        self.assertTrue(dhcp_options_creation_result)

    @mock_ec2
    def test_when_creating_dhcp_options_and_specifying_a_name_succeeds_the_create_dhcp_options_method_returns_true(
            self):
        dhcp_options_creation_result = boto_vpc.create_dhcp_options(dhcp_options_name='test',
                                                                    **dhcp_options_parameters)

        self.assertTrue(dhcp_options_creation_result)

    @mock_ec2
    def test_when_creating_dhcp_options_and_specifying_tags_succeeds_the_create_dhcp_options_method_returns_true(
            self):
        dhcp_options_creation_result = boto_vpc.create_dhcp_options(tags={'test': 'testvalue'},
                                                                    **dhcp_options_parameters)

        self.assertTrue(dhcp_options_creation_result)

    @mock_ec2
    def test_when_creating_dhcp_options_fails_the_create_dhcp_options_method_returns_false(self):
        with patch('moto.ec2.models.DHCPOptionsSetBackend.create_dhcp_options',
                   side_effect=BotoServerError(400, 'Mocked error')):
            dhcp_options_creation_result = boto_vpc.create_dhcp_options(**dhcp_options_parameters)

        self.assertFalse(dhcp_options_creation_result)

    @mock_ec2
    def test_when_associating_an_existing_dhcp_options_set_to_an_existing_vpc_the_associate_dhcp_options_method_returns_true(
            self):
        vpc = self._create_vpc()
        dhcp_options = self._create_dhcp_options()

        dhcp_options_association_result = boto_vpc.associate_dhcp_options_to_vpc(dhcp_options.id, vpc.id,
                                                                                 **conn_parameters)

        self.assertTrue(dhcp_options_association_result)

    @mock_ec2
    def test_when_associating_a_non_existent_dhcp_options_set_to_an_existing_vpc_the_associate_dhcp_options_method_returns_true(
            self):
        vpc = self._create_vpc()

        dhcp_options_association_result = boto_vpc.associate_dhcp_options_to_vpc('fake', vpc.id, **conn_parameters)

        self.assertFalse(dhcp_options_association_result)

    @mock_ec2
    def test_when_associating_an_existing_dhcp_options_set_to_a_non_existent_vpc_the_associate_dhcp_options_method_returns_false(
            self):
        dhcp_options = self._create_dhcp_options()

        dhcp_options_association_result = boto_vpc.associate_dhcp_options_to_vpc(dhcp_options.id, 'fake',
                                                                                 **conn_parameters)

        self.assertFalse(dhcp_options_association_result)

    @mock_ec2
    def test_when_creating_and_associating_dhcp_options_set_to_an_existing_vpc_succeeds_the_associate_new_dhcp_options_method_returns_true(
            self):
        vpc = self._create_vpc()

        dhcp_creation_and_association_result = boto_vpc.associate_new_dhcp_options_to_vpc(vpc.id,
                                                                                          **dhcp_options_parameters)

        self.assertTrue(dhcp_creation_and_association_result)

    @mock_ec2
    def test_when_creating_and_associating_dhcp_options_set_to_an_existing_vpc_fails_creating_the_dhcp_options_the_associate_new_dhcp_options_method_returns_false(
            self):
        vpc = self._create_vpc()

        with patch('moto.ec2.models.DHCPOptionsSetBackend.create_dhcp_options',
                   side_effect=BotoServerError(400, 'Mocked error')):
            dhcp_creation_and_association_result = boto_vpc.associate_new_dhcp_options_to_vpc(vpc.id,
                                                                                              **dhcp_options_parameters)

        self.assertFalse(dhcp_creation_and_association_result)

    @mock_ec2
    def test_when_creating_and_associating_dhcp_options_set_to_an_existing_vpc_fails_associating_the_dhcp_options_the_associate_new_dhcp_options_method_returns_false(
            self):
        vpc = self._create_vpc()

        with patch('moto.ec2.models.DHCPOptionsSetBackend.associate_dhcp_options',
                   side_effect=BotoServerError(400, 'Mocked error')):
            dhcp_creation_and_association_result = boto_vpc.associate_new_dhcp_options_to_vpc(vpc.id,
                                                                                              **dhcp_options_parameters)

        self.assertFalse(dhcp_creation_and_association_result)

    @mock_ec2
    def test_when_creating_and_associating_dhcp_options_set_to_a_non_existent_vpc_the_dhcp_options_the_associate_new_dhcp_options_method_returns_false(
            self):
        dhcp_creation_and_association_result = boto_vpc.associate_new_dhcp_options_to_vpc('fake',
                                                                                          **dhcp_options_parameters)

        self.assertFalse(dhcp_creation_and_association_result)

    @mock_ec2
    def test_that_when_dhcp_options_exists_the_dhcp_options_exists_method_returns_true(self):
        dhcp_options = self._create_dhcp_options()

        dhcp_options_exists_result = boto_vpc.dhcp_options_exists(dhcp_options.id, **conn_parameters)

        self.assertTrue(dhcp_options_exists_result)

    @mock_ec2
    def test_that_when_dhcp_options_do_not_exist_the_dhcp_options_exists_method_returns_false(self):
        dhcp_options_exists_result = boto_vpc.dhcp_options_exists('fake', **conn_parameters)

        self.assertFalse(dhcp_options_exists_result)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoVpcNetworkACLTestCase(BotoVpcTestCaseBase):
    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_network_acl_for_an_existing_vpc_the_create_network_acl_method_returns_true(self):
        vpc = self._create_vpc()

        network_acl_creation_result = boto_vpc.create_network_acl(vpc.id, **conn_parameters)

        self.assertTrue(network_acl_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_network_acl_for_an_existing_vpc_and_specifying_a_name_the_create_network_acl_method_returns_true(
            self):
        vpc = self._create_vpc()

        network_acl_creation_result = boto_vpc.create_network_acl(vpc.id, network_acl_name='test', **conn_parameters)

        self.assertTrue(network_acl_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_network_acl_for_an_existing_vpc_and_specifying_tags_the_create_network_acl_method_returns_true(
            self):
        vpc = self._create_vpc()

        network_acl_creation_result = boto_vpc.create_network_acl(vpc.id, tags={'test': 'testvalue'}, **conn_parameters)

        self.assertTrue(network_acl_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_network_acl_for_a_non_existent_vpc_the_create_network_acl_method_returns_false(self):
        network_acl_creation_result = boto_vpc.create_network_acl('fake', **conn_parameters)

        self.assertFalse(network_acl_creation_result)

    @mock_ec2
    @expectedImportFailure
    def test_when_creating_network_acl_fails_the_create_network_acl_method_returns_false(self):
        vpc = self._create_vpc()

        with patch('moto.ec2.models.NetworkACLBackend.create_network_acl',
                   side_effect=BotoServerError(400, 'Mocked error')):
            network_acl_creation_result = boto_vpc.create_network_acl(vpc.id, **conn_parameters)

        self.assertFalse(network_acl_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_deleting_an_existing_network_acl_the_delete_network_acl_method_returns_true(self):
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)

        network_acl_deletion_result = boto_vpc.delete_network_acl(network_acl.id, **conn_parameters)

        self.assertTrue(network_acl_deletion_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_deleting_a_non_existent_network_acl_the_delete_network_acl_method_returns_false(self):
        network_acl_deletion_result = boto_vpc.delete_network_acl('fake', **conn_parameters)

        self.assertFalse(network_acl_deletion_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_a_network_acl_exists_the_network_acl_exists_method_returns_true(self):
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)

        network_acl_deletion_result = boto_vpc.network_acl_exists(network_acl.id, **conn_parameters)

        self.assertTrue(network_acl_deletion_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_a_network_acl_does_not_exist_the_network_acl_exists_method_returns_false(self):
        network_acl_deletion_result = boto_vpc.network_acl_exists('fake', **conn_parameters)

        self.assertFalse(network_acl_deletion_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_a_network_acl_entry_successfully_the_create_network_acl_entry_method_returns_true(self):
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)

        network_acl_entry_creation_result = boto_vpc.create_network_acl_entry(network_acl.id,
                                                                              *network_acl_entry_parameters,
                                                                              **conn_parameters)

        self.assertTrue(network_acl_entry_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_a_network_acl_entry_for_a_non_existent_network_acl_the_create_network_acl_entry_method_returns_false(
            self):
        network_acl_entry_creation_result = boto_vpc.create_network_acl_entry(*network_acl_entry_parameters,
                                                                              **conn_parameters)

        self.assertFalse(network_acl_entry_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_replacing_a_network_acl_entry_successfully_the_replace_network_acl_entry_method_returns_true(self):
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)
        self._create_network_acl_entry(network_acl.id, *network_acl_entry_parameters)

        network_acl_entry_creation_result = boto_vpc.replace_network_acl_entry(network_acl.id,
                                                                               *network_acl_entry_parameters,
                                                                               **conn_parameters)

        self.assertTrue(network_acl_entry_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_replacing_a_network_acl_entry_for_a_non_existent_network_acl_the_replace_network_acl_entry_method_returns_false(
            self):
        network_acl_entry_creation_result = boto_vpc.create_network_acl_entry(*network_acl_entry_parameters,
                                                                              **conn_parameters)

        self.assertFalse(network_acl_entry_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_deleting_an_existing_network_acl_entry_the_delete_network_acl_entry_method_returns_true(self):
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)
        network_acl_entry = self._create_network_acl_entry(network_acl.id, *network_acl_entry_parameters)

        network_acl_entry_deletion_result = boto_vpc.delete_network_acl_entry(network_acl_entry.id, 100,
                                                                              **conn_parameters)

        self.assertTrue(network_acl_entry_deletion_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_deleting_a_non_existent_network_acl_entry_the_delete_network_acl_entry_method_returns_false(self):
        network_acl_entry_deletion_result = boto_vpc.delete_network_acl_entry('fake', 100,
                                                                              **conn_parameters)

        self.assertFalse(network_acl_entry_deletion_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_associating_an_existing_network_acl_to_an_existing_subnet_the_associate_network_acl_method_returns_true(
            self):
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)
        subnet = self._create_subnet(vpc.id)

        network_acl_association_result = boto_vpc.associate_network_acl_to_subnet(network_acl.id, subnet.id,
                                                                                  **conn_parameters)

        self.assertTrue(network_acl_association_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_associating_a_non_existent_network_acl_to_an_existing_subnet_the_associate_network_acl_method_returns_false(
            self):
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_association_result = boto_vpc.associate_network_acl_to_subnet('fake', subnet.id,
                                                                                  **conn_parameters)

        self.assertFalse(network_acl_association_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_associating_an_existing_network_acl_to_a_non_existent_subnet_the_associate_network_acl_method_returns_false(
            self):
        vpc = self._create_vpc()
        network_acl = self._create_network_acl(vpc.id)

        network_acl_association_result = boto_vpc.associate_network_acl_to_subnet(network_acl.id, 'fake',
                                                                                  **conn_parameters)

        self.assertFalse(network_acl_association_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_and_associating_a_network_acl_to_a_subnet_succeeds_the_associate_new_network_acl_to_subnet_method_returns_true(
            self):
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_creation_and_association_result = boto_vpc.associate_new_network_acl_to_subnet(vpc.id, subnet.id,
                                                                                                   **conn_parameters)

        self.assertTrue(network_acl_creation_and_association_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_and_associating_a_network_acl_to_a_subnet_and_specifying_a_name_succeeds_the_associate_new_network_acl_to_subnet_method_returns_true(
            self):
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_creation_and_association_result = boto_vpc.associate_new_network_acl_to_subnet(vpc.id, subnet.id,
                                                                                                   network_acl_name='test',
                                                                                                   **conn_parameters)

        self.assertTrue(network_acl_creation_and_association_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_and_associating_a_network_acl_to_a_subnet_and_specifying_tags_succeeds_the_associate_new_network_acl_to_subnet_method_returns_true(
            self):
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_creation_and_association_result = boto_vpc.associate_new_network_acl_to_subnet(vpc.id, subnet.id,
                                                                                                   tags={
                                                                                                       'test': 'testvalue'},
                                                                                                   **conn_parameters)

        self.assertTrue(network_acl_creation_and_association_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_and_associating_a_network_acl_to_a_non_existent_subnet_the_associate_new_network_acl_to_subnet_method_returns_false(
            self):
        vpc = self._create_vpc()

        network_acl_creation_and_association_result = boto_vpc.associate_new_network_acl_to_subnet(vpc.id, 'fake',
                                                                                                   **conn_parameters)

        self.assertFalse(network_acl_creation_and_association_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_and_associating_a_network_acl_to_a_non_existent_vpc_the_associate_new_network_acl_to_subnet_method_returns_false(
            self):
        vpc = self._create_vpc()
        subnet = self._create_subnet(vpc.id)

        network_acl_creation_and_association_result = boto_vpc.associate_new_network_acl_to_subnet('fake', subnet.id,
                                                                                                   **conn_parameters)

        self.assertFalse(network_acl_creation_and_association_result)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoVpcRoutingTablesTestCase(BotoVpcTestCaseBase):
    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_a_route_table_succeeds_the_create_route_table_method_returns_true(self):
        vpc = self._create_vpc()

        route_table_creation_result = boto_vpc.create_route_table(vpc.id, **conn_parameters)

        self.assertTrue(route_table_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_creating_a_route_table_on_a_non_existent_vpc_the_create_route_table_method_returns_false(self):
        route_table_creation_result = boto_vpc.create_route_table('fake', **conn_parameters)

        self.assertTrue(route_table_creation_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_deleting_a_route_table_succeeds_the_delete_route_table_method_returns_true(self):
        vpc = self._create_vpc()
        route_table = self._create_route_table(vpc.id)

        route_table_deletion_result = boto_vpc.delete_route_table(route_table.id)

        self.assertTrue(route_table_deletion_result)

    @mock_ec2
    @expectedNotImplementedFailure
    def test_when_deleting_a_non_existent_route_table_the_delete_route_table_method_returns_false(self):
        route_table_deletion_result = boto_vpc.delete_route_table('fake')

        self.assertFalse(route_table_deletion_result)

if __name__ == '__main__':
    from integration import run_tests

    run_tests(BotoVpcTestCase, needs_daemon=False)

# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module

# Import Salt Testing libs
from salttesting.unit import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
import salt.config
import salt.loader
from unit.modules.boto_vpc_test import BotoVpcTestCaseMixin

# Import 3rd-party libs
import salt.ext.six as six
# pylint: disable=import-error
try:
    import boto
    from boto.exception import BotoServerError

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
# pylint: enable=import-error

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

opts = salt.config.DEFAULT_MINION_OPTS
ctx = {}
utils = salt.loader.utils(opts, context=ctx, whitelist=['boto'])
funcs = salt.loader.minion_mods(opts, context=ctx, utils=utils, whitelist=['boto_vpc'])
salt_states = salt.loader.states(opts=opts, functions=funcs, whitelist=['boto_vpc'])


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

class BotoVpcStateTestCaseBase(TestCase):
    def setUp(self):
        ctx.clear()

@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoVpcTestCase(BotoVpcStateTestCaseBase, BotoVpcTestCaseMixin):
    '''
    TestCase for salt.states.boto_vpc state.module
    '''

    @mock_ec2
    def test_present_when_vpc_does_not_exist(self):
        '''
        Tests present on a VPC that does not exist.
        '''
        vpc_present_result = salt_states['boto_vpc.present']('test', cidr_block)

        self.assertTrue(vpc_present_result['result'])
        self.assertEqual(vpc_present_result['changes']['new']['vpc']['state'], 'available')

    @mock_ec2
    def test_present_when_vpc_exists(self):
        vpc = self._create_vpc(name='test')
        vpc_present_result = salt_states['boto_vpc.present']('test', cidr_block)
        self.assertTrue(vpc_present_result['result'])
        self.assertEqual(vpc_present_result['changes'], {})

    @mock_ec2
    def test_present_with_failure(self):
        with patch('moto.ec2.models.VPCBackend.create_vpc', side_effect=BotoServerError(400, 'Mocked error')):
            vpc_present_result = salt_states['boto_vpc.present']('test', cidr_block)
            self.assertFalse(vpc_present_result['result'])
            self.assertTrue('Mocked error' in vpc_present_result['comment'])

    @mock_ec2
    def test_absent_when_vpc_does_not_exist(self):
        '''
        Tests absent on a VPC that does not exist.
        '''
        vpc_absent_result = salt_states['boto_vpc.absent']('test')
        self.assertTrue(vpc_absent_result['result'])
        self.assertEqual(vpc_absent_result['changes'], {})

    @mock_ec2
    def test_absent_when_vpc_exists(self):
        vpc = self._create_vpc(name='test')
        vpc_absent_result = salt_states['boto_vpc.absent']('test')
        self.assertTrue(vpc_absent_result['result'])
        self.assertEqual(vpc_absent_result['changes']['new']['vpc'], None)

    @mock_ec2
    def test_absent_with_failure(self):
        vpc = self._create_vpc(name='test')
        with patch('moto.ec2.models.VPCBackend.delete_vpc', side_effect=BotoServerError(400, 'Mocked error')):
            vpc_absent_result = salt_states['boto_vpc.absent']('test')
            self.assertFalse(vpc_absent_result['result'])
            self.assertTrue('Mocked error' in vpc_absent_result['comment'])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoVpcSubnetsTestCase(BotoVpcStateTestCaseBase, BotoVpcTestCaseMixin):

    @mock_ec2
    def test_present_when_subnet_does_not_exist(self):
        '''
        Tests present on a subnet that does not exist.
        '''
        vpc = self._create_vpc(name='test')
        subnet_present_result = salt_states['boto_vpc.subnet_present']('test', cidr_block,
                                                                       vpc_name='test')

        self.assertTrue(subnet_present_result['result'])
        self.assertTrue('id' in subnet_present_result['changes']['new']['subnet'])

    @mock_ec2
    def test_present_when_subnet_exists(self):
        vpc = self._create_vpc(name='test')
        subnet = self._create_subnet(vpc_id=vpc.id, name='test')
        subnet_present_result = salt_states['boto_vpc.subnet_present']('test', cidr_block,
                                                                       vpc_name='test')
        self.assertTrue(subnet_present_result['result'])
        self.assertEqual(subnet_present_result['changes'], {})

    @mock_ec2
    def test_present_with_failure(self):
        vpc = self._create_vpc(name='test')
        with patch('moto.ec2.models.SubnetBackend.create_subnet', side_effect=BotoServerError(400, 'Mocked error')):
            subnet_present_result = salt_states['boto_vpc.subnet_present']('test', cidr_block,
                                                                           vpc_name='test')
            self.assertFalse(subnet_present_result['result'])
            self.assertTrue('Mocked error' in subnet_present_result['comment'])

    @mock_ec2
    def test_absent_when_subnet_does_not_exist(self):
        '''
        Tests absent on a subnet that does not exist.
        '''
        subnet_absent_result = salt_states['boto_vpc.subnet_absent']('test')
        self.assertTrue(subnet_absent_result['result'])
        self.assertEqual(subnet_absent_result['changes'], {})

    @mock_ec2
    def test_absent_when_subnet_exists(self):
        vpc = self._create_vpc(name='test')
        subnet = self._create_subnet(vpc_id=vpc.id, name='test')
 
        subnet_absent_result = salt_states['boto_vpc.subnet_absent']('test')
        self.assertTrue(subnet_absent_result['result'])
        self.assertEqual(subnet_absent_result['changes']['new']['subnet'], None)

    @mock_ec2
    def test_absent_with_failure(self):
        vpc = self._create_vpc(name='test')
        subnet = self._create_subnet(vpc_id=vpc.id, name='test')
 
        with patch('moto.ec2.models.SubnetBackend.delete_subnet', side_effect=BotoServerError(400, 'Mocked error')):
            subnet_absent_result = salt_states['boto_vpc.subnet_absent']('test')
            self.assertFalse(subnet_absent_result['result'])
            self.assertTrue('Mocked error' in subnet_absent_result['comment'])


class BotoVpcResourceTestCaseMixin(BotoVpcTestCaseMixin):
    resource_type = None
    backend_create = None
    backend_delete = None

    def _create_resource(self, vpc_id=None, name=None):
        _create = getattr(self, '_create_' + self.resource_type)
        _create(vpc_id=vpc_id, name=name)

    @mock_ec2
    def test_present_when_resource_does_not_exist(self):
        '''
        Tests present on a resource that does not exist.
        '''
        vpc = self._create_vpc(name='test')
        resource_present_result = salt_states['boto_vpc.{0}_present'.format(self.resource_type)](
                name='test', vpc_name='test')

        self.assertTrue(resource_present_result['result'])
        
        exists = funcs['boto_vpc.resource_exists'](self.resource_type, 'test').get('exists')
        self.assertTrue(exists)

    @mock_ec2
    def test_present_when_resource_exists(self):
        vpc = self._create_vpc(name='test')
        resource = self._create_resource(vpc_id=vpc.id, name='test')
        resource_present_result = salt_states['boto_vpc.{0}_present'.format(self.resource_type)](
                name='test', vpc_name='test')
        self.assertTrue(resource_present_result['result'])
        self.assertEqual(resource_present_result['changes'], {})

    @mock_ec2
    def test_present_with_failure(self):
        vpc = self._create_vpc(name='test')
        with patch('moto.ec2.models.{0}'.format(self.backend_create), side_effect=BotoServerError(400, 'Mocked error')):
            resource_present_result = salt_states['boto_vpc.{0}_present'.format(self.resource_type)](
                    name='test', vpc_name='test')

            self.assertFalse(resource_present_result['result'])
            self.assertTrue('Mocked error' in resource_present_result['comment'])

    @mock_ec2
    def test_absent_when_resource_does_not_exist(self):
        '''
        Tests absent on a resource that does not exist.
        '''
        resource_absent_result = salt_states['boto_vpc.{0}_absent'.format(self.resource_type)]('test')
        self.assertTrue(resource_absent_result['result'])
        self.assertEqual(resource_absent_result['changes'], {})

    @mock_ec2
    def test_absent_when_resource_exists(self):
        vpc = self._create_vpc(name='test')
        resource = self._create_resource(vpc_id=vpc.id, name='test')
 
        resource_absent_result = salt_states['boto_vpc.{0}_absent'.format(self.resource_type)]('test')
        self.assertTrue(resource_absent_result['result'])
        self.assertEqual(resource_absent_result['changes']['new'][self.resource_type], None)
        exists = funcs['boto_vpc.resource_exists'](self.resource_type, 'test').get('exists')
        self.assertFalse(exists)

    @mock_ec2
    def test_absent_with_failure(self):
        vpc = self._create_vpc(name='test')
        resource = self._create_resource(vpc_id=vpc.id, name='test')
 
        with patch('moto.ec2.models.{0}'.format(self.backend_delete), side_effect=BotoServerError(400, 'Mocked error')):
            resource_absent_result = salt_states['boto_vpc.{0}_absent'.format(self.resource_type)]('test')
            self.assertFalse(resource_absent_result['result'])
            self.assertTrue('Mocked error' in resource_absent_result['comment'])


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoVpcInternetGatewayTestCase(BotoVpcStateTestCaseBase, BotoVpcResourceTestCaseMixin):
    resource_type = 'internet_gateway'
    backend_create = 'InternetGatewayBackend.create_internet_gateway'
    backend_delete = 'InternetGatewayBackend.delete_internet_gateway'


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto_version))
class BotoVpcRouteTableTestCase(BotoVpcStateTestCaseBase, BotoVpcResourceTestCaseMixin):
    resource_type = 'route_table'
    backend_create = 'RouteTableBackend.create_route_table'
    backend_delete = 'RouteTableBackend.delete_route_table'

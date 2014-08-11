# -*- coding: utf-8 -*-

# import Python Third Party Libs
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

# Import Salt Libs
from salt.modules import boto_vpc

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key, 'profile': {}}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@mock_ec2
class Boto_VpcTestCase(TestCase):
    '''
    TestCase for salt.modules.boto_vpc module
    '''
    def test_get_subnet_association_single_subnet(self):
        '''
        tests that given multiple subnet ids in the same VPC that the VPC ID is
        returned. The test is valuable because it uses a string as an argument
        to subnets as opposed to a list.
        '''
        conn = boto.vpc.connect_to_region(region)
        vpc = conn.create_vpc('10.0.0.0/24')
        subnet = conn.create_subnet(vpc.id, '10.0.0.0/25')
        subnet_assocation = boto_vpc.get_subnet_association(subnets=subnet.id,
                                                            **conn_parameters)
        self.assertEqual(vpc.id, subnet_assocation)

    def test_get_subnet_association_multiple_subnets_same_vpc(self):
        '''
        tests that given multiple subnet ids in the same VPC that the VPC ID is
        returned.
        '''
        conn = boto.vpc.connect_to_region(region)
        vpc = conn.create_vpc('10.0.0.0/24')
        subnet_a = conn.create_subnet(vpc.id, '10.0.0.0/25')
        subnet_b = conn.create_subnet(vpc.id, '10.0.0.128/25')
        subnet_assocation = boto_vpc.get_subnet_association([subnet_a.id, subnet_b.id],
                                                            **conn_parameters)
        self.assertEqual(vpc.id, subnet_assocation)

    def test_get_subnet_association_multiple_subnets_different_vpc(self):
        '''
        tests that given multiple subnet ids in different VPCs that False is
        returned.
        '''
        conn = boto.vpc.connect_to_region(region)
        vpc_a = conn.create_vpc('10.0.0.0/24')
        vpc_b = conn.create_vpc('10.0.0.0/24')
        subnet_a = conn.create_subnet(vpc_a.id, '10.0.0.0/24')
        subnet_b = conn.create_subnet(vpc_b.id, '10.0.0.0/24')
        subnet_assocation = boto_vpc.get_subnet_association([subnet_a.id, subnet_b.id],
                                                            **conn_parameters)
        self.assertFalse(subnet_assocation)

    def test_exists_true(self):
        '''
        tests True existence of a VPC.
        '''
        conn = boto.vpc.connect_to_region(region)
        vpc = conn.create_vpc('10.0.0.0/24')
        vpc_exists = boto_vpc.exists(vpc.id, **conn_parameters)
        self.assertTrue(vpc_exists)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(Boto_VpcTestCase)

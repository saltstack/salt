# -*- coding: utf-8 -*-

# import Python Libs
import random
import string
from collections import OrderedDict

# import Python Third Party Libs
try:
    import boto
    from moto import mock_ec2
    missing_requirements = False
    missing_requirements_msg = ''
except ImportError:
    missing_requirements = True
    missing_requirements_msg = 'boto and moto modules required for test.'

    def mock_ec2(self):
        '''
        if the mock_ec2 function is not available due to import failure
        this replaces the decorated function with stub_function.
        Allows boto_secgroup unit tests to use the @mock_ec2 decorator
        without a "NameError: name 'mock_ec2' is not defined" error.
        '''
        def stub_function(self):
            pass
        return stub_function

# Import Salt Libs
from salt.modules import boto_secgroup

# Import Salt Testing Libs
from salttesting import skipIf, TestCase

vpc_id = 'vpc-mjm05d27'
region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key, 'profile': {}}


def _random_group_name():
    group_name = 'boto_secgroup-{0}'.format(''.join((random.choice(string.ascii_lowercase)) for char in range(12)))
    return group_name


class Boto_SecgroupTestCase(TestCase):
    '''
    TestCase for salt.modules.boto_secgroup module
    '''
    def test__split_rules(self):
        '''
        tests the splitting of a list of rules into individual rules
        '''
        rules = [OrderedDict([('ip_protocol', u'tcp'), ('from_port', 22), ('to_port', 22), ('grants', [OrderedDict([('cidr_ip', u'0.0.0.0/0')])])]),
                 OrderedDict([('ip_protocol', u'tcp'), ('from_port', 80), ('to_port', 80), ('grants', [OrderedDict([('cidr_ip', u'0.0.0.0/0')])])])]
        split_rules = [{'to_port': 22, 'from_port': 22, 'ip_protocol': u'tcp', 'cidr_ip': u'0.0.0.0/0'},
                       {'to_port': 80, 'from_port': 80, 'ip_protocol': u'tcp', 'cidr_ip': u'0.0.0.0/0'}]
        self.assertEqual(boto_secgroup._split_rules(rules), split_rules)

    @skipIf(missing_requirements, missing_requirements_msg)
    # test can be enabled if running version of moto contains commit id
    # https://github.com/spulec/moto/commit/cc0166964371f7b5247a49d45637a8f936ccbe6f
    @skipIf(True, 'test skipped because of'
                  ' https://github.com/spulec/moto/issues/152')
    @mock_ec2
    def test_get_group_id_ec2_classic(self):
        '''
        tests that given a name of a group in EC2-Classic that the correct
        group id will be retreived
        '''
        group_name = _random_group_name()
        group_description = 'test_get_group_id_ec2_classic'
        conn = boto.ec2.connect_to_region(region)
        group_classic = conn.create_security_group(name=group_name,
                                                   description=group_description)
        # note that the vpc_id does not need to be created in order to create
        # a security group within the vpc when using moto
        group_vpc = conn.create_security_group(name=group_name,
                                               description=group_description,
                                               vpc_id=vpc_id)
        retreived_group_id = boto_secgroup.get_group_id(group_name,
                                                        **conn_parameters)
        self.assertEqual(group_classic.id, retreived_group_id)

    @skipIf(True, 'test skipped because moto does not yet support group'
                  ' filters https://github.com/spulec/moto/issues/154')
    @mock_ec2
    def test_get_group_id_ec2_vpc(self):
        '''
        tests that given a name of a group in EC2-VPC that the correct
        group id will be retreived
        '''
        group_name = _random_group_name()
        group_description = 'test_get_group_id_ec2_vpc'
        conn = boto.ec2.connect_to_region(region)
        group_classic = conn.create_security_group(name=group_name,
                                                   description=group_description)
        # note that the vpc_id does not need to be created in order to create
        # a security group within the vpc when using moto
        group_vpc = conn.create_security_group(name=group_name,
                                               description=group_description,
                                               vpc_id=vpc_id)
        retreived_group_id = boto_secgroup.get_group_id(group_name, group_vpc,
                                                        **conn_parameters)
        self.assertEqual(group_vpc.id, retreived_group_id)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(Boto_SecgroupTestCase)

# -*- coding: utf-8 -*-

# import Python Third Party Libs

from mock import patch

from salt.exceptions import CommandExecutionError
from salt.modules.boto_tag import _get_conn


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

# Import Python libs
from distutils.version import LooseVersion

# Import Salt Libs
from salt.modules import boto_tag

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

required_boto_version = '2.8.0'
required_moto_version = '0.3.7'
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


def _has_required_moto():
    '''
    Returns True/False boolean depending on if Moto is installed and correct
    version.
    '''
    if not HAS_MOTO:
        return False
    else:
        import pkg_resources

        if LooseVersion(pkg_resources.get_distribution('moto').version) < LooseVersion(required_moto_version):
            return False
        return True


class BotoTagTestCaseBase(TestCase):
    conn = None

    def _create_vpc(self, name=None, tags=None):
        '''
        Helper function to create a test vpc
        '''
        if not self.conn:
            self.conn = _get_conn('vpc', **conn_parameters)

        vpc = self.conn.create_vpc(cidr_block)
        return vpc

    def _create_security_group(self, name=None, description=None):
        '''
        Helper function to create a test subnet
        '''
        if not self.conn:
            self.conn = _get_conn('ec2', **conn_parameters)

        security_group = self.conn.create_security_group(name, description)
        return security_group


    def _create_instance(self, ami_id='ami-08389d60'):
        '''
        Helper function to create a test instance
        '''
        if not self.conn:
            self.conn = _get_conn('ec2', **conn_parameters)

        reservations = self.conn.run_instances(ami_id)
        return reservations.instances[0]



@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False,
        'The boto module must be greater than'
        ' or equal to version {0}'.format(required_boto_version))
class BotoTagTestCase(BotoTagTestCaseBase):
    '''
    TestCase for salt.modules.boto_tags module
    '''
    # vpc
    @mock_ec2
    def test_that_when_adding_tags_to_vpc_method_returns_true(self):
        vpc = self._create_vpc()
        ret = boto_tag.add(resource_id=vpc.id, tags={"environment":"development"}, **conn_parameters)
        self.assertTrue(ret) and self.assertEqual(vpc.tags, {"environment":"development"})

    @mock_ec2
    def test_that_when_adding_tags_to_non_existing_vpc_method_returns_false(self):
        ret = boto_tag.add(resource_id='vpc-123456', tags='{"environment":"development"}', **conn_parameters)
        self.assertFalse(ret)
    
    @mock_ec2
    def test_that_when_removing_tags_from_vpc_method_returns_true(self):
        vpc = self._create_vpc(tags={"environment":"development", "cluster":"compute1"})
        ret = boto_tag.remove(resource_id=vpc.id, tags={"cluster":"compute1"}, **conn_parameters)
        self.assertTrue(ret) and self.assertEqual(vpc.tags, {"environment":"development"})

    @mock_ec2
    def test_that_when_removing_tags_from_non_existing_vpc_method_returns_false(self):
        ret = boto_tag.remove(resource_id='vpc-123456', tags={"cluster":"compute1"}, **conn_parameters)
        self.assertFalse(ret)
    
    # sg
    @mock_ec2
    def test_that_when_adding_tags_to_sg_method_returns_true(self):
        sg = self._create_security_group()
        ret = boto_tag.add(resource_id=sg.id, tags={"environment":"development"}, **conn_parameters)
        self.assertTrue(ret) and self.assertEqual(sg.tags, {"environment":"development"})

    @mock_ec2
    def test_that_when_adding_tags_to_non_existing_sg_method_returns_false(self):
        ret = boto_tag.add(resource_id='sg-123456', tags={"environment":"development"}, **conn_parameters)
        self.assertFalse(ret)
    
    @mock_ec2
    def test_that_when_removing_tags_from_sg_method_returns_true(self):
        sg = self._create_security_group()
        boto_tag.add(resource_id=sg.id, tags={"environment":"development", "cluster":"compute1"}, **conn_parameters)
        ret = boto_tag.remove(resource_id=sg.id, tags={"cluster":"compute1"}, **conn_parameters)
        self.assertTrue(ret) and self.assertEqual(sg.tags, {"environment":"development"})

    @mock_ec2
    def test_that_when_removing_tags_from_non_existing_sg_method_returns_false(self):
        ret = boto_tag.remove(resource_id='sg-123456', tags={"cluster":"compute1"}, **conn_parameters)
        self.assertFalse(ret)

    # instance
    @mock_ec2
    def test_that_when_adding_tags_to_instance_method_returns_true(self):
        instance = self._create_instance()
        ret = boto_tag.add(resource_id=instance.id, tags={"environment":"development"}, **conn_parameters)
        self.assertTrue(ret) and self.assertEqual(sg.tags, {"environment":"development"})

    @mock_ec2
    def test_that_when_adding_tags_to_non_existing_instance_method_returns_false(self):
        ret = boto_tag.add(resource_id='i-123456', tags={"environment":"development"}, **conn_parameters)
        self.assertFalse(ret)
    
    @mock_ec2
    def test_that_when_removing_tags_from_instance_method_returns_true(self):
        instance = self._create_instance()
        boto_tag.add(resource_id=instance.id, tags={"environment":"development", "cluster":"compute1"}, **conn_parameters)
        ret = boto_tag.remove(resource_id=instance.id, tags={"cluster":"compute1"}, **conn_parameters)
        self.assertTrue(ret) and self.assertEqual(instance.tags, {"environment":"development"})

    @mock_ec2
    def test_that_when_removing_tags_from_non_existing_instance_method_returns_false(self):
        ret = boto_tag.remove(resource_id='i-123456', tags={"cluster":"compute1"}, **conn_parameters)
        self.assertFalse(ret)
    
    # unknown    
    @mock_ec2
    def test_that_when_adding_tags_to_unknown_resource_method_returns_false(self):
        with self.assertRaisesRegexp(CommandExecutionError, 'Resource id: unknown-123456 could not be recognized.'):
            ret = boto_tag.add(resource_id='unknown-123456', tags={"cluster":"compute1"}, **conn_parameters)

    @mock_ec2        
    def test_that_when_removing_tags_from_unknown_resource_method_returns_false(self):
        with self.assertRaisesRegexp(CommandExecutionError, 'Resource id: unknown-123456 could not be recognized.'):
            ret = boto_tag.remove(resource_id='unknown-123456', tags={"cluster":"compute1"}, **conn_parameters)


if __name__ == '__main__':
    from integration import run_tests

    run_tests(BotoTagTestCase, needs_daemon=False)

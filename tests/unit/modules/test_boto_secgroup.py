# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import
import random
import string
from copy import deepcopy

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import salt.config
import salt.loader
from salt.utils.versions import LooseVersion
from salt.utils.odict import OrderedDict
import salt.modules.boto_secgroup as boto_secgroup

# Import Third Party Libs
# pylint: disable=import-error
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin
try:
    import boto
    import boto.ec2  # pylint: enable=unused-import
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
        Allows boto_secgroup unit tests to use the @mock_ec2 decorator
        without a "NameError: name 'mock_ec2' is not defined" error.
        '''
        def stub_function(self):
            pass
        return stub_function
# pylint: enable=import-error


required_boto_version = '2.4.0'
vpc_id = 'vpc-mjm05d27'
region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key, 'profile': {}}
boto_conn_parameters = {'aws_access_key_id': access_key, 'aws_secret_access_key': secret_key}


def _random_group_id():
    group_id = 'sg-{0:x}'.format(random.randrange(2 ** 32))
    return group_id


def _random_group_name():
    group_name = 'boto_secgroup-{0}'.format(''.join((random.choice(string.ascii_lowercase)) for char in range(12)))
    return group_name


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


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto module must be greater than'
                                       ' or equal to version {0}'
                                       .format(required_boto_version))
class BotoSecgroupTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.boto_secgroup module
    '''

    def setup_loader_modules(self):
        opts = salt.config.DEFAULT_MASTER_OPTS
        utils = salt.loader.utils(opts, whitelist=['boto'])
        funcs = salt.loader.minion_mods(opts, utils=utils)
        return {
            boto_secgroup: {
                '__opts__': opts,
                '__utils__': utils,
                '__salt__': funcs
            }
        }

    def setUp(self):
        super(BotoSecgroupTestCase, self).setUp()
        # __virtual__ must be caller in order for _get_conn to be injected
        boto_secgroup.__virtual__()

    def test__split_rules(self):
        '''
        tests the splitting of a list of rules into individual rules
        '''
        rules = [OrderedDict([('ip_protocol', u'tcp'), ('from_port', 22), ('to_port', 22), ('grants', [OrderedDict([('cidr_ip', u'0.0.0.0/0')])])]),
                 OrderedDict([('ip_protocol', u'tcp'), ('from_port', 80), ('to_port', 80), ('grants', [OrderedDict([('cidr_ip', u'0.0.0.0/0')])])])]
        split_rules = [{'to_port': 22, 'from_port': 22, 'ip_protocol': u'tcp', 'cidr_ip': u'0.0.0.0/0'},
                       {'to_port': 80, 'from_port': 80, 'ip_protocol': u'tcp', 'cidr_ip': u'0.0.0.0/0'}]
        self.assertEqual(boto_secgroup._split_rules(rules), split_rules)

    @mock_ec2
    def test_create_ec2_classic(self):
        '''
        Test of creation of an EC2-Classic security group. The test ensures
        that a group was created with the desired name and description
        '''
        group_name = _random_group_name()
        group_description = 'test_create_ec2_classic'
        boto_secgroup.create(group_name, group_description, **conn_parameters)
        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        group_filter = {'group-name': group_name}
        secgroup_created_group = conn.get_all_security_groups(filters=group_filter)
        expected_create_result = [group_name,
                                  group_description,
                                  None]
        secgroup_create_result = [secgroup_created_group[0].name,
                                  secgroup_created_group[0].description,
                                  secgroup_created_group[0].vpc_id]
        self.assertEqual(expected_create_result, secgroup_create_result)

    @mock_ec2
    def test_create_ec2_vpc(self):
        '''
        test of creation of an EC2-VPC security group. The test ensures that a
        group was created in a given vpc with the desired name and description
        '''
        group_name = _random_group_name()
        group_description = 'test_create_ec2_vpc'
        # create a group using boto_secgroup
        boto_secgroup.create(group_name, group_description, vpc_id=vpc_id, **conn_parameters)
        # confirm that the group actually exists
        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        group_filter = {'group-name': group_name, 'vpc-id': vpc_id}
        secgroup_created_group = conn.get_all_security_groups(filters=group_filter)
        expected_create_result = [group_name, group_description, vpc_id]
        secgroup_create_result = [secgroup_created_group[0].name, secgroup_created_group[0].description, secgroup_created_group[0].vpc_id]
        self.assertEqual(expected_create_result, secgroup_create_result)

    @mock_ec2
    def test_get_group_id_ec2_classic(self):
        '''
        tests that given a name of a group in EC2-Classic that the correct
        group id will be retrieved
        '''
        group_name = _random_group_name()
        group_description = 'test_get_group_id_ec2_classic'
        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        group_classic = conn.create_security_group(name=group_name,
                                                   description=group_description)
        # note that the vpc_id does not need to be created in order to create
        # a security group within the vpc when using moto
        group_vpc = conn.create_security_group(name=group_name,
                                               description=group_description,
                                               vpc_id=vpc_id)
        retrieved_group_id = boto_secgroup.get_group_id(group_name,
                                                        **conn_parameters)
        self.assertEqual(group_classic.id, retrieved_group_id)

    @skipIf(True, 'test skipped because moto does not yet support group'
                  ' filters https://github.com/spulec/moto/issues/154')
    @mock_ec2
    def test_get_group_id_ec2_vpc(self):
        '''
        tests that given a name of a group in EC2-VPC that the correct
        group id will be retrieved
        '''
        group_name = _random_group_name()
        group_description = 'test_get_group_id_ec2_vpc'
        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        group_classic = conn.create_security_group(name=group_name,
                                                   description=group_description)
        # note that the vpc_id does not need to be created in order to create
        # a security group within the vpc when using moto
        group_vpc = conn.create_security_group(name=group_name,
                                               description=group_description,
                                               vpc_id=vpc_id)
        retrieved_group_id = boto_secgroup.get_group_id(group_name, group_vpc,
                                                        **conn_parameters)
        self.assertEqual(group_vpc.id, retrieved_group_id)

    @mock_ec2
    def test_get_config_single_rule_group_name(self):
        '''
        tests return of 'config' when given group name. get_config returns an OrderedDict.
        '''
        group_name = _random_group_name()
        ip_protocol = u'tcp'
        from_port = 22
        to_port = 22
        cidr_ip = u'0.0.0.0/0'
        rules_egress = [{'to_port': -1, 'from_port': -1, 'ip_protocol': u'-1', 'cidr_ip': u'0.0.0.0/0'}]

        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        group = conn.create_security_group(name=group_name, description=group_name)
        group.authorize(ip_protocol=ip_protocol, from_port=from_port, to_port=to_port, cidr_ip=cidr_ip)
        # setup the expected get_config result
        expected_get_config_result = OrderedDict([('name', group.name), ('group_id', group.id), ('owner_id', u'111122223333'),
                                                 ('description', group.description), ('tags', {}),
                                                 ('rules', [{'to_port': to_port, 'from_port': from_port,
                                                  'ip_protocol': ip_protocol, 'cidr_ip': cidr_ip}]),
                                                 ('rules_egress', rules_egress)])
        secgroup_get_config_result = boto_secgroup.get_config(group_id=group.id, **conn_parameters)
        self.assertEqual(expected_get_config_result, secgroup_get_config_result)

    @mock_ec2
    def test_exists_true_name_classic(self):
        '''
        tests 'true' existence of a group in EC2-Classic when given name
        '''
        group_name = _random_group_name()
        group_description = 'test_exists_true_ec2_classic'
        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        group_classic = conn.create_security_group(group_name, group_description)
        group_vpc = conn.create_security_group(group_name, group_description, vpc_id=vpc_id)
        salt_exists_result = boto_secgroup.exists(name=group_name, **conn_parameters)
        self.assertTrue(salt_exists_result)

    @mock_ec2
    def test_exists_false_name_classic(self):
        pass

    @mock_ec2
    def test_exists_true_name_vpc(self):
        '''
        tests 'true' existence of a group in EC2-VPC when given name and vpc_id
        '''
        group_name = _random_group_name()
        group_description = 'test_exists_true_ec2_vpc'
        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        conn.create_security_group(group_name, group_description, vpc_id=vpc_id)
        salt_exists_result = boto_secgroup.exists(name=group_name, vpc_id=vpc_id, **conn_parameters)
        self.assertTrue(salt_exists_result)

    @mock_ec2
    def test_exists_false_name_vpc(self):
        '''
        tests 'false' existence of a group in vpc when given name and vpc_id
        '''
        group_name = _random_group_name()
        salt_exists_result = boto_secgroup.exists(group_name, vpc_id=vpc_id, **conn_parameters)
        self.assertFalse(salt_exists_result)

    @mock_ec2
    def test_exists_true_group_id(self):
        '''
        tests 'true' existence of a group when given group_id
        '''
        group_name = _random_group_name()
        group_description = 'test_exists_true_group_id'
        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        group = conn.create_security_group(group_name, group_description)
        salt_exists_result = boto_secgroup.exists(group_id=group.id, **conn_parameters)
        self.assertTrue(salt_exists_result)

    @mock_ec2
    def test_exists_false_group_id(self):
        '''
        tests 'false' existence of a group when given group_id
        '''
        group_id = _random_group_id()
        salt_exists_result = boto_secgroup.exists(group_id=group_id, **conn_parameters)
        self.assertFalse(salt_exists_result)

    @mock_ec2
    def test_delete_group_ec2_classic(self):
        '''
        test deletion of a group in EC2-Classic. Test does the following:
        1. creates two groups, in EC2-Classic and one in EC2-VPC
        2. saves the group_ids to group_ids_pre_delete
        3. removes the group in EC2-VPC
        4. saves the group ids of groups to group_ids_post_delete
        5. compares the group_ids_pre_delete and group_ids_post_delete lists
           to ensure that the correct group was deleted
        '''
        group_name = _random_group_name()
        group_description = 'test_delete_group_ec2_classic'
        # create two groups using boto, one in EC2-Classic and one in EC2-VPC
        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        group_classic = conn.create_security_group(name=group_name, description=group_description)
        group_vpc = conn.create_security_group(name=group_name, description=group_description, vpc_id=vpc_id)
        # creates a list of all the existing all_group_ids in an AWS account
        all_groups = [group.id for group in conn.get_all_security_groups()]
        # removes the EC2-Classic Security Group
        deleted = boto_secgroup.delete(name=group_name, **conn_parameters)
        expected_groups = deepcopy(all_groups)
        expected_groups.remove(group_classic.id)
        actual_groups = [group.id for group in conn.get_all_security_groups()]
        self.assertEqual(expected_groups, actual_groups)

    @mock_ec2
    def test_delete_group_name_ec2_vpc(self):
        pass

    @mock_ec2
    def test__get_conn_true(self):
        '''
        tests ensures that _get_conn returns an boto.ec2.connection.EC2Connection object.
        '''
        conn = boto.ec2.connect_to_region(region, **boto_conn_parameters)
        salt_conn = boto_secgroup._get_conn(**conn_parameters)
        self.assertEqual(conn.__class__, salt_conn.__class__)

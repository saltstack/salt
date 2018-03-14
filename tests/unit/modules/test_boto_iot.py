# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import random
import string
import logging

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt libs
import salt.config
import salt.loader
import salt.modules.boto_iot as boto_iot
from salt.utils.versions import LooseVersion
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
# pylint: disable=import-error,no-name-in-module,unused-import
try:
    import boto
    import boto3
    from botocore.exceptions import ClientError
    from botocore import __version__ as found_botocore_version
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module,unused-import

# the boto_iot module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = '1.2.1'
required_botocore_version = '1.4.41'

log = logging.getLogger(__name__)


def _has_required_boto():
    '''
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    '''
    if not HAS_BOTO:
        return False
    elif LooseVersion(boto3.__version__) < LooseVersion(required_boto3_version):
        return False
    elif LooseVersion(found_botocore_version) < LooseVersion(required_botocore_version):
        return False
    else:
        return True


if _has_required_boto():
    region = 'us-east-1'
    access_key = 'GKTADJGHEIQSXMKKRBJ08H'
    secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
    conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key, 'profile': {}}
    error_message = 'An error occurred (101) when calling the {0} operation: Test-defined error'
    not_found_error = ClientError({
        'Error': {
            'Code': 'ResourceNotFoundException',
            'Message': "Test-defined error"
        }
    }, 'msg')
    topic_rule_not_found_error = ClientError({
        'Error': {
            'Code': 'UnauthorizedException',
            'Message': "Test-defined error"
        }
    }, 'msg')
    error_content = {
      'Error': {
        'Code': 101,
        'Message': "Test-defined error"
      }
    }
    policy_ret = dict(policyName='testpolicy',
                      policyDocument='{"Version": "2012-10-17", "Statement": [{"Action": ["iot:Publish"], "Resource": ["*"], "Effect": "Allow"}]}',
                      policyArn='arn:aws:iot:us-east-1:123456:policy/my_policy',
                      policyVersionId=1,
                      defaultVersionId=1)
    topic_rule_ret = dict(ruleName='testrule',
                      sql="SELECT * FROM 'iot/test'",
                      description='topic rule description',
                      createdAt='1970-01-01',
                      actions=[{'lambda': {'functionArn': 'arn:aws:::function'}}],
                      ruleDisabled=True)

    thing_type_name = 'test_thing_type'
    thing_type_desc = 'test_thing_type_desc'
    thing_type_attr_1 = 'test_thing_type_search_attr_1'
    thing_type_ret = dict(
        thingTypeName=thing_type_name,
        thingTypeProperties=dict(
            thingTypeDescription=thing_type_desc,
            searchableAttributes=[thing_type_attr_1],
        ),
        thingTypeMetadata=dict(
            deprecated=False,
            creationDate='test_thing_type_create_date'
        )
    )
    thing_type_arn = 'test_thing_type_arn'
    create_thing_type_ret = dict(
        thingTypeName=thing_type_name,
        thingTypeArn=thing_type_arn
    )


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoIoTTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS
        utils = salt.loader.utils(opts, whitelist=['boto3'], context={})
        return {boto_iot: {'__utils__': utils}}

    def setUp(self):
        super(BotoIoTTestCaseBase, self).setUp()
        boto_iot.__init__(self.opts)
        del self.opts

        # Set up MagicMock to replace the boto3 session
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        conn_parameters['key'] = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(50))

        self.patcher = patch('boto3.session.Session')
        self.addCleanup(self.patcher.stop)
        self.addCleanup(delattr, self, 'patcher')
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        self.addCleanup(delattr, self, 'conn')
        session_instance.client.return_value = self.conn


class BotoIoTTestCaseMixin(object):
    pass


class BotoIoTThingTypeTestCase(BotoIoTTestCaseBase, BotoIoTTestCaseMixin):
    '''
    TestCase for salt.modules.boto_iot module
    '''

    def test_that_when_checking_if_a_thing_type_exists_and_a_thing_type_exists_the_thing_type_exists_method_returns_true(self):
        '''
        Tests checking iot thing type existence when the iot thing type already exists
        '''
        self.conn.describe_thing_type.return_value = thing_type_ret
        result = boto_iot.thing_type_exists(thingTypeName=thing_type_name, **conn_parameters)

        self.assertTrue(result['exists'])

    def test_that_when_checking_if_a_thing_type_exists_and_a_thing_type_does_not_exist_the_thing_type_exists_method_returns_false(self):
        '''
        Tests checking iot thing type existence when the iot thing type does not exist
        '''
        self.conn.describe_thing_type.side_effect = not_found_error
        result = boto_iot.thing_type_exists(thingTypeName='non existent thing type', **conn_parameters)

        self.assertFalse(result['exists'])

    def test_that_when_checking_if_a_thing_type_exists_and_boto3_returns_an_error_the_thing_type_exists_method_returns_error(self):
        '''
        Tests checking iot thing type existence when boto returns an error
        '''
        self.conn.describe_thing_type.side_effect = ClientError(error_content, 'describe_thing_type')
        result = boto_iot.thing_type_exists(thingTypeName='mythingtype', **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'), error_message.format('describe_thing_type'))

    def test_that_when_describing_thing_type_and_thing_type_exists_the_describe_thing_type_method_returns_thing_type(self):
        '''
        Tests describe thing type for an existing thing type
        '''
        self.conn.describe_thing_type.return_value = thing_type_ret
        result = boto_iot.describe_thing_type(thingTypeName=thing_type_name, **conn_parameters)

        self.assertEqual(result.get('thing_type'), thing_type_ret)

    def test_that_when_describing_thing_type_and_thing_type_does_not_exists_the_describe_thing_type_method_returns_none(self):
        '''
        Tests describe thing type for an non existent thing type
        '''
        self.conn.describe_thing_type.side_effect = not_found_error
        result = boto_iot.describe_thing_type(thingTypeName='non existent thing type', **conn_parameters)

        self.assertEqual(result.get('thing_type'), None)

    def test_that_when_describing_thing_type_and_boto3_returns_error_an_error_the_describe_thing_type_method_returns_error(self):
        self.conn.describe_thing_type.side_effect = ClientError(error_content, 'describe_thing_type')
        result = boto_iot.describe_thing_type(thingTypeName='mythingtype', **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'), error_message.format('describe_thing_type'))

    def test_that_when_creating_a_thing_type_succeeds_the_create_thing_type_method_returns_true(self):
        '''
        tests True when thing type created
        '''
        self.conn.create_thing_type.return_value = create_thing_type_ret
        result = boto_iot.create_thing_type(thingTypeName=thing_type_name,
                                            thingTypeDescription=thing_type_desc,
                                            searchableAttributesList=[thing_type_attr_1],
                                            **conn_parameters)
        self.assertTrue(result['created'])
        self.assertTrue(result['thingTypeArn'], thing_type_arn)

    def test_that_when_creating_a_thing_type_fails_the_create_thing_type_method_returns_error(self):
        '''
        tests False when thing type not created
        '''
        self.conn.create_thing_type.side_effect = ClientError(error_content, 'create_thing_type')
        result = boto_iot.create_thing_type(thingTypeName=thing_type_name,
                                            thingTypeDescription=thing_type_desc,
                                            searchableAttributesList=[thing_type_attr_1],
                                            **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('create_thing_type'))

    def test_that_when_deprecating_a_thing_type_succeeds_the_deprecate_thing_type_method_returns_true(self):
        '''
        tests True when deprecate thing type succeeds
        '''
        self.conn.deprecate_thing_type.return_value = {}
        result = boto_iot.deprecate_thing_type(thingTypeName=thing_type_name,
                                               undoDeprecate=False,
                                               **conn_parameters)

        self.assertTrue(result.get('deprecated'))
        self.assertEqual(result.get('error'), None)

    def test_that_when_deprecating_a_thing_type_fails_the_deprecate_thing_type_method_returns_error(self):
        '''
        tests False when thing type fails to deprecate
        '''
        self.conn.deprecate_thing_type.side_effect = ClientError(error_content, 'deprecate_thing_type')
        result = boto_iot.deprecate_thing_type(thingTypeName=thing_type_name,
                                               undoDeprecate=False,
                                               **conn_parameters)

        self.assertFalse(result.get('deprecated'))
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('deprecate_thing_type'))

    def test_that_when_deleting_a_thing_type_succeeds_the_delete_thing_type_method_returns_true(self):
        '''
        tests True when delete thing type succeeds
        '''
        self.conn.delete_thing_type.return_value = {}
        result = boto_iot.delete_thing_type(thingTypeName=thing_type_name, **conn_parameters)

        self.assertTrue(result.get('deleted'))
        self.assertEqual(result.get('error'), None)

    def test_that_when_deleting_a_thing_type_fails_the_delete_thing_type_method_returns_error(self):
        '''
        tests False when delete thing type fails
        '''
        self.conn.delete_thing_type.side_effect = ClientError(error_content, 'delete_thing_type')
        result = boto_iot.delete_thing_type(thingTypeName=thing_type_name, **conn_parameters)
        self.assertFalse(result.get('deleted'))
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('delete_thing_type'))


class BotoIoTPolicyTestCase(BotoIoTTestCaseBase, BotoIoTTestCaseMixin):
    '''
    TestCase for salt.modules.boto_iot module
    '''

    def test_that_when_checking_if_a_policy_exists_and_a_policy_exists_the_policy_exists_method_returns_true(self):
        '''
        Tests checking iot policy existence when the iot policy already exists
        '''
        self.conn.get_policy.return_value = {'policy': policy_ret}
        result = boto_iot.policy_exists(policyName=policy_ret['policyName'], **conn_parameters)

        self.assertTrue(result['exists'])

    def test_that_when_checking_if_a_policy_exists_and_a_policy_does_not_exist_the_policy_exists_method_returns_false(self):
        '''
        Tests checking iot policy existence when the iot policy does not exist
        '''
        self.conn.get_policy.side_effect = not_found_error
        result = boto_iot.policy_exists(policyName='mypolicy', **conn_parameters)

        self.assertFalse(result['exists'])

    def test_that_when_checking_if_a_policy_exists_and_boto3_returns_an_error_the_policy_exists_method_returns_error(self):
        '''
        Tests checking iot policy existence when boto returns an error
        '''
        self.conn.get_policy.side_effect = ClientError(error_content, 'get_policy')
        result = boto_iot.policy_exists(policyName='mypolicy', **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'), error_message.format('get_policy'))

    def test_that_when_creating_a_policy_succeeds_the_create_policy_method_returns_true(self):
        '''
        tests True policy created.
        '''
        self.conn.create_policy.return_value = policy_ret
        result = boto_iot.create_policy(policyName=policy_ret['policyName'],
                                        policyDocument=policy_ret['policyDocument'],
                                        **conn_parameters)

        self.assertTrue(result['created'])

    def test_that_when_creating_a_policy_fails_the_create_policy_method_returns_error(self):
        '''
        tests False policy not created.
        '''
        self.conn.create_policy.side_effect = ClientError(error_content, 'create_policy')
        result = boto_iot.create_policy(policyName=policy_ret['policyName'],
                                        policyDocument=policy_ret['policyDocument'],
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('create_policy'))

    def test_that_when_deleting_a_policy_succeeds_the_delete_policy_method_returns_true(self):
        '''
        tests True policy deleted.
        '''
        result = boto_iot.delete_policy(policyName='testpolicy',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_a_policy_fails_the_delete_policy_method_returns_false(self):
        '''
        tests False policy not deleted.
        '''
        self.conn.delete_policy.side_effect = ClientError(error_content, 'delete_policy')
        result = boto_iot.delete_policy(policyName='testpolicy',
                                        **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_describing_policy_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if policy exists
        '''
        self.conn.get_policy.return_value = {'policy': policy_ret}

        result = boto_iot.describe_policy(policyName=policy_ret['policyName'], **conn_parameters)

        self.assertTrue(result['policy'])

    def test_that_when_describing_policy_it_returns_the_dict_of_properties_returns_false(self):
        '''
        Tests describing parameters if policy does not exist
        '''
        self.conn.get_policy.side_effect = not_found_error
        result = boto_iot.describe_policy(policyName='testpolicy', **conn_parameters)

        self.assertFalse(result['policy'])

    def test_that_when_describing_policy_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.get_policy.side_effect = ClientError(error_content, 'get_policy')
        result = boto_iot.describe_policy(policyName='testpolicy', **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_checking_if_a_policy_version_exists_and_a_policy_version_exists_the_policy_version_exists_method_returns_true(self):
        '''
        Tests checking iot policy existence when the iot policy version already exists
        '''
        self.conn.get_policy.return_value = {'policy': policy_ret}
        result = boto_iot.policy_version_exists(policyName=policy_ret['policyName'],
                                                policyVersionId=1,
                                                **conn_parameters)

        self.assertTrue(result['exists'])

    def test_that_when_checking_if_a_policy_version_exists_and_a_policy_version_does_not_exist_the_policy_version_exists_method_returns_false(self):
        '''
        Tests checking iot policy_version existence when the iot policy_version does not exist
        '''
        self.conn.get_policy_version.side_effect = not_found_error
        result = boto_iot.policy_version_exists(policyName=policy_ret['policyName'],
                                                policyVersionId=1,
                                                **conn_parameters)

        self.assertFalse(result['exists'])

    def test_that_when_checking_if_a_policy_version_exists_and_boto3_returns_an_error_the_policy_version_exists_method_returns_error(self):
        '''
        Tests checking iot policy_version existence when boto returns an error
        '''
        self.conn.get_policy_version.side_effect = ClientError(error_content, 'get_policy_version')
        result = boto_iot.policy_version_exists(policyName=policy_ret['policyName'],
                                                policyVersionId=1,
                                                **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'), error_message.format('get_policy_version'))

    def test_that_when_creating_a_policy_version_succeeds_the_create_policy_version_method_returns_true(self):
        '''
        tests True policy_version created.
        '''
        self.conn.create_policy_version.return_value = policy_ret
        result = boto_iot.create_policy_version(policyName=policy_ret['policyName'],
                                        policyDocument=policy_ret['policyDocument'],
                                        **conn_parameters)

        self.assertTrue(result['created'])

    def test_that_when_creating_a_policy_version_fails_the_create_policy_version_method_returns_error(self):
        '''
        tests False policy_version not created.
        '''
        self.conn.create_policy_version.side_effect = ClientError(error_content, 'create_policy_version')
        result = boto_iot.create_policy_version(policyName=policy_ret['policyName'],
                                        policyDocument=policy_ret['policyDocument'],
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('create_policy_version'))

    def test_that_when_deleting_a_policy_version_succeeds_the_delete_policy_version_method_returns_true(self):
        '''
        tests True policy_version deleted.
        '''
        result = boto_iot.delete_policy_version(policyName='testpolicy',
                                        policyVersionId=1,
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_a_policy_version_fails_the_delete_policy_version_method_returns_false(self):
        '''
        tests False policy_version not deleted.
        '''
        self.conn.delete_policy_version.side_effect = ClientError(error_content, 'delete_policy_version')
        result = boto_iot.delete_policy_version(policyName='testpolicy',
                                        policyVersionId=1,
                                        **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_describing_policy_version_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if policy_version exists
        '''
        self.conn.get_policy_version.return_value = {'policy': policy_ret}

        result = boto_iot.describe_policy_version(policyName=policy_ret['policyName'],
                                        policyVersionId=1,
                                        **conn_parameters)

        self.assertTrue(result['policy'])

    def test_that_when_describing_policy_version_it_returns_the_dict_of_properties_returns_false(self):
        '''
        Tests describing parameters if policy_version does not exist
        '''
        self.conn.get_policy_version.side_effect = not_found_error
        result = boto_iot.describe_policy_version(policyName=policy_ret['policyName'],
                                        policyVersionId=1,
                                        **conn_parameters)

        self.assertFalse(result['policy'])

    def test_that_when_describing_policy_version_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.get_policy_version.side_effect = ClientError(error_content, 'get_policy_version')
        result = boto_iot.describe_policy_version(policyName=policy_ret['policyName'],
                                        policyVersionId=1,
                                        **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_listing_policies_succeeds_the_list_policies_method_returns_true(self):
        '''
        tests True policies listed.
        '''
        self.conn.list_policies.return_value = {'policies': [policy_ret]}
        result = boto_iot.list_policies(**conn_parameters)

        self.assertTrue(result['policies'])

    def test_that_when_listing_policy_fails_the_list_policy_method_returns_false(self):
        '''
        tests False no policy listed.
        '''
        self.conn.list_policies.return_value = {'policies': []}
        result = boto_iot.list_policies(**conn_parameters)
        self.assertFalse(result['policies'])

    def test_that_when_listing_policy_fails_the_list_policy_method_returns_error(self):
        '''
        tests False policy error.
        '''
        self.conn.list_policies.side_effect = ClientError(error_content, 'list_policies')
        result = boto_iot.list_policies(**conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('list_policies'))

    def test_that_when_listing_policy_versions_succeeds_the_list_policy_versions_method_returns_true(self):
        '''
        tests True policy versions listed.
        '''
        self.conn.list_policy_versions.return_value = {'policyVersions': [policy_ret]}
        result = boto_iot.list_policy_versions(policyName='testpolicy',
                                               **conn_parameters)

        self.assertTrue(result['policyVersions'])

    def test_that_when_listing_policy_versions_fails_the_list_policy_versions_method_returns_false(self):
        '''
        tests False no policy versions listed.
        '''
        self.conn.list_policy_versions.return_value = {'policyVersions': []}
        result = boto_iot.list_policy_versions(policyName='testpolicy',
                                               **conn_parameters)
        self.assertFalse(result['policyVersions'])

    def test_that_when_listing_policy_versions_fails_the_list_policy_versions_method_returns_error(self):
        '''
        tests False policy versions error.
        '''
        self.conn.list_policy_versions.side_effect = ClientError(error_content, 'list_policy_versions')
        result = boto_iot.list_policy_versions(policyName='testpolicy',
                                               **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('list_policy_versions'))

    def test_that_when_setting_default_policy_version_succeeds_the_set_default_policy_version_method_returns_true(self):
        '''
        tests True policy version set.
        '''
        result = boto_iot.set_default_policy_version(policyName='testpolicy',
                                               policyVersionId=1,
                                               **conn_parameters)

        self.assertTrue(result['changed'])

    def test_that_when_set_default_policy_version_fails_the_set_default_policy_version_method_returns_error(self):
        '''
        tests False policy version error.
        '''
        self.conn.set_default_policy_version.side_effect = \
                                ClientError(error_content, 'set_default_policy_version')
        result = boto_iot.set_default_policy_version(policyName='testpolicy',
                                               policyVersionId=1,
                                               **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('set_default_policy_version'))

    def test_that_when_list_principal_policies_succeeds_the_list_principal_policies_method_returns_true(self):
        '''
        tests True policies listed.
        '''
        self.conn.list_principal_policies.return_value = {'policies': [policy_ret]}
        result = boto_iot.list_principal_policies(principal='us-east-1:GUID-GUID-GUID',
                                               **conn_parameters)

        self.assertTrue(result['policies'])

    def test_that_when_list_principal_policies_fails_the_list_principal_policies_method_returns_error(self):
        '''
        tests False policy version error.
        '''
        self.conn.list_principal_policies.side_effect = \
                                ClientError(error_content, 'list_principal_policies')
        result = boto_iot.list_principal_policies(principal='us-east-1:GUID-GUID-GUID',
                                               **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('list_principal_policies'))

    def test_that_when_attach_principal_policy_succeeds_the_attach_principal_policy_method_returns_true(self):
        '''
        tests True policy attached.
        '''
        result = boto_iot.attach_principal_policy(policyName='testpolicy',
                                               principal='us-east-1:GUID-GUID-GUID',
                                               **conn_parameters)

        self.assertTrue(result['attached'])

    def test_that_when_attach_principal_policy_version_fails_the_attach_principal_policy_version_method_returns_error(self):
        '''
        tests False policy version error.
        '''
        self.conn.attach_principal_policy.side_effect = \
                                ClientError(error_content, 'attach_principal_policy')
        result = boto_iot.attach_principal_policy(policyName='testpolicy',
                                               principal='us-east-1:GUID-GUID-GUID',
                                               **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('attach_principal_policy'))

    def test_that_when_detach_principal_policy_succeeds_the_detach_principal_policy_method_returns_true(self):
        '''
        tests True policy detached.
        '''
        result = boto_iot.detach_principal_policy(policyName='testpolicy',
                                               principal='us-east-1:GUID-GUID-GUID',
                                               **conn_parameters)

        self.assertTrue(result['detached'])

    def test_that_when_detach_principal_policy_version_fails_the_detach_principal_policy_version_method_returns_error(self):
        '''
        tests False policy version error.
        '''
        self.conn.detach_principal_policy.side_effect = \
                                ClientError(error_content, 'detach_principal_policy')
        result = boto_iot.detach_principal_policy(policyName='testpolicy',
                                               principal='us-east-1:GUID-GUID-GUID',
                                               **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('detach_principal_policy'))


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}.  The botocore'
                                       ' module must be greater than or equal to'
                                       ' version {1}.'
        .format(required_boto3_version, required_botocore_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoIoTTopicRuleTestCase(BotoIoTTestCaseBase, BotoIoTTestCaseMixin):
    '''
    TestCase for salt.modules.boto_iot module
    '''

    def test_that_when_checking_if_a_topic_rule_exists_and_a_topic_rule_exists_the_topic_rule_exists_method_returns_true(self):
        '''
        Tests checking iot topic_rule existence when the iot topic_rule already exists
        '''
        self.conn.get_topic_rule.return_value = {'rule': topic_rule_ret}
        result = boto_iot.topic_rule_exists(ruleName=topic_rule_ret['ruleName'],
                                            **conn_parameters)

        self.assertTrue(result['exists'])

    def test_that_when_checking_if_a_rule_exists_and_a_rule_does_not_exist_the_topic_rule_exists_method_returns_false(self):
        '''
        Tests checking iot rule existence when the iot rule does not exist
        '''
        self.conn.get_topic_rule.side_effect = topic_rule_not_found_error
        result = boto_iot.topic_rule_exists(ruleName='mypolicy', **conn_parameters)

        self.assertFalse(result['exists'])

    def test_that_when_checking_if_a_topic_rule_exists_and_boto3_returns_an_error_the_topic_rule_exists_method_returns_error(self):
        '''
        Tests checking iot topic_rule existence when boto returns an error
        '''
        self.conn.get_topic_rule.side_effect = ClientError(error_content, 'get_topic_rule')
        result = boto_iot.topic_rule_exists(ruleName='myrule', **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'),
                                      error_message.format('get_topic_rule'))

    def test_that_when_creating_a_topic_rule_succeeds_the_create_topic_rule_method_returns_true(self):
        '''
        tests True topic_rule created.
        '''
        self.conn.create_topic_rule.return_value = topic_rule_ret
        result = boto_iot.create_topic_rule(ruleName=topic_rule_ret['ruleName'],
                                        sql=topic_rule_ret['sql'],
                                        description=topic_rule_ret['description'],
                                        actions=topic_rule_ret['actions'],
                                        **conn_parameters)

        self.assertTrue(result['created'])

    def test_that_when_creating_a_topic_rule_fails_the_create_topic_rule_method_returns_error(self):
        '''
        tests False topic_rule not created.
        '''
        self.conn.create_topic_rule.side_effect = ClientError(error_content, 'create_topic_rule')
        result = boto_iot.create_topic_rule(ruleName=topic_rule_ret['ruleName'],
                                        sql=topic_rule_ret['sql'],
                                        description=topic_rule_ret['description'],
                                        actions=topic_rule_ret['actions'],
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('create_topic_rule'))

    def test_that_when_replacing_a_topic_rule_succeeds_the_replace_topic_rule_method_returns_true(self):
        '''
        tests True topic_rule replaced.
        '''
        self.conn.replace_topic_rule.return_value = topic_rule_ret
        result = boto_iot.replace_topic_rule(ruleName=topic_rule_ret['ruleName'],
                                        sql=topic_rule_ret['sql'],
                                        description=topic_rule_ret['description'],
                                        actions=topic_rule_ret['actions'],
                                        **conn_parameters)

        self.assertTrue(result['replaced'])

    def test_that_when_replacing_a_topic_rule_fails_the_replace_topic_rule_method_returns_error(self):
        '''
        tests False topic_rule not replaced.
        '''
        self.conn.replace_topic_rule.side_effect = ClientError(error_content, 'replace_topic_rule')
        result = boto_iot.replace_topic_rule(ruleName=topic_rule_ret['ruleName'],
                                        sql=topic_rule_ret['sql'],
                                        description=topic_rule_ret['description'],
                                        actions=topic_rule_ret['actions'],
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('replace_topic_rule'))

    def test_that_when_deleting_a_topic_rule_succeeds_the_delete_topic_rule_method_returns_true(self):
        '''
        tests True topic_rule deleted.
        '''
        result = boto_iot.delete_topic_rule(ruleName='testrule',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_a_topic_rule_fails_the_delete_topic_rule_method_returns_false(self):
        '''
        tests False topic_rule not deleted.
        '''
        self.conn.delete_topic_rule.side_effect = ClientError(error_content, 'delete_topic_rule')
        result = boto_iot.delete_topic_rule(ruleName='testrule',
                                        **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_describing_topic_rule_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if topic_rule exists
        '''
        self.conn.get_topic_rule.return_value = {'rule': topic_rule_ret}

        result = boto_iot.describe_topic_rule(ruleName=topic_rule_ret['ruleName'],
                                              **conn_parameters)

        self.assertTrue(result['rule'])

    def test_that_when_describing_topic_rule_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.get_topic_rule.side_effect = ClientError(error_content, 'get_topic_rule')
        result = boto_iot.describe_topic_rule(ruleName='testrule', **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_listing_topic_rules_succeeds_the_list_topic_rules_method_returns_true(self):
        '''
        tests True topic_rules listed.
        '''
        self.conn.list_topic_rules.return_value = {'rules': [topic_rule_ret]}
        result = boto_iot.list_topic_rules(**conn_parameters)

        self.assertTrue(result['rules'])

    def test_that_when_listing_topic_rules_fails_the_list_topic_rules_method_returns_error(self):
        '''
        tests False policy error.
        '''
        self.conn.list_topic_rules.side_effect = ClientError(error_content, 'list_topic_rules')
        result = boto_iot.list_topic_rules(**conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('list_topic_rules'))

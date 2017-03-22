# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import logging
import random
import string

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch

# Import Salt libs
import salt.config
import salt.loader
from salt.utils.versions import LooseVersion
import salt.states.boto_iot as boto_iot

# Import test suite libs

# pylint: disable=import-error,no-name-in-module,unused-import
from tests.unit.modules.test_boto_iot import BotoIoTTestCaseMixin

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
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
                      actions=[{'iot': {'functionArn': 'arn:aws:::function'}}],
                      ruleDisabled=True)
    principal = 'arn:aws:iot:us-east-1:1234:cert/21fc104aaaf6043f5756c1b57bda84ea8395904c43f28517799b19e4c42514'

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
            creationDate='2010-08-01 15:54:49.699000+00:00'
        )
    )
    deprecated_thing_type_ret = dict(
        thingTypeName=thing_type_name,
        thingTypeProperties=dict(
            thingTypeDescription=thing_type_desc,
            searchableAttributes=[thing_type_attr_1],
        ),
        thingTypeMetadata=dict(
            deprecated=True,
            creationDate='2010-08-01 15:54:49.699000+00:00',
            deprecationDate='2010-08-02 15:54:49.699000+00:00'
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
class BotoIoTStateTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    def setup_loader_modules(self):
        ctx = {}
        utils = salt.loader.utils(self.opts, whitelist=['boto3'], context=ctx)
        serializers = salt.loader.serializers(self.opts)
        self.funcs = funcs = salt.loader.minion_mods(self.opts, context=ctx, utils=utils, whitelist=['boto_iot'])
        self.salt_states = salt.loader.states(opts=self.opts, functions=funcs, utils=utils, whitelist=['boto_iot'],
                                              serializers=serializers)
        return {
            boto_iot: {
                '__opts__': self.opts,
                '__salt__': funcs,
                '__utils__': utils,
                '__states__': self.salt_states,
                '__serializers__': serializers,
            }
        }

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.DEFAULT_MINION_OPTS
        cls.opts['grains'] = salt.loader.grains(cls.opts)

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def setUp(self):
        self.addCleanup(delattr, self, 'funcs')
        self.addCleanup(delattr, self, 'salt_states')
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


class BotoIoTThingTypeTestCase(BotoIoTStateTestCaseBase, BotoIoTTestCaseMixin):
    '''
    TestCase for salt.modules.boto_iot state.module
    '''

    def test_present_when_thing_type_does_not_exist(self):
        '''
        tests present on a thing type that does not exist.
        '''
        self.conn.describe_thing_type.side_effect = [not_found_error, thing_type_ret]
        self.conn.create_thing_type.return_value = create_thing_type_ret
        result = self.salt_states['boto_iot.thing_type_present'](
            'thing type present',
            thingTypeName=thing_type_name,
            thingTypeDescription=thing_type_desc,
            searchableAttributesList=[thing_type_attr_1],
            **conn_parameters
        )
        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['thing_type']['thingTypeName'],
                         thing_type_name)

    def test_present_when_thing_type_exists(self):
        self.conn.describe_thing_type.return_value = thing_type_ret
        result = self.salt_states['boto_iot.thing_type_present'](
            'thing type present',
            thingTypeName=thing_type_name,
            thingTypeDescription=thing_type_desc,
            searchableAttributesList=[thing_type_attr_1],
            **conn_parameters
        )
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})
        self.assertTrue(self.conn.create_thing_type.call_count == 0)

    def test_present_with_failure(self):
        self.conn.describe_thing_type.side_effect = [not_found_error, thing_type_ret]
        self.conn.create_thing_type.side_effect = ClientError(error_content, 'create_thing_type')
        result = self.salt_states['boto_iot.thing_type_present'](
            'thing type present',
            thingTypeName=thing_type_name,
            thingTypeDescription=thing_type_desc,
            searchableAttributesList=[thing_type_attr_1],
            **conn_parameters
        )
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])

    def test_absent_when_thing_type_does_not_exist(self):
        '''
        Tests absent on a thing type does not exist
        '''
        self.conn.describe_thing_type.side_effect = not_found_error
        result = self.salt_states['boto_iot.thing_type_absent']('test', 'mythingtype', **conn_parameters)
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_absent_when_thing_type_exists(self):
        '''
        Tests absent on a thing type
        '''
        self.conn.describe_thing_type.return_value = deprecated_thing_type_ret
        result = self.salt_states['boto_iot.thing_type_absent']('test', thing_type_name, **conn_parameters)
        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['thing_type'], None)
        self.assertTrue(self.conn.deprecate_thing_type.call_count == 0)

    def test_absent_with_deprecate_failure(self):
        self.conn.describe_thing_type.return_value = thing_type_ret
        self.conn.deprecate_thing_type.side_effect = ClientError(error_content, 'deprecate_thing_type')
        result = self.salt_states['boto_iot.thing_type_absent']('test', thing_type_name, **conn_parameters)
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])
        self.assertTrue('deprecate_thing_type' in result['comment'])
        self.assertTrue(self.conn.delete_thing_type.call_count == 0)

    def test_absent_with_delete_failure(self):
        self.conn.describe_thing_type.return_value = deprecated_thing_type_ret
        self.conn.delete_thing_type.side_effect = ClientError(error_content, 'delete_thing_type')
        result = self.salt_states['boto_iot.thing_type_absent']('test', thing_type_name, **conn_parameters)
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])
        self.assertTrue('delete_thing_type' in result['comment'])
        self.assertTrue(self.conn.deprecate_thing_type.call_count == 0)


class BotoIoTPolicyTestCase(BotoIoTStateTestCaseBase, BotoIoTTestCaseMixin):
    '''
    TestCase for salt.modules.boto_iot state.module
    '''

    def test_present_when_policy_does_not_exist(self):
        '''
        Tests present on a policy that does not exist.
        '''
        self.conn.get_policy.side_effect = [not_found_error, policy_ret]
        self.conn.create_policy.return_value = policy_ret
        result = self.salt_states['boto_iot.policy_present'](
                         'policy present',
                         policyName=policy_ret['policyName'],
                         policyDocument=policy_ret['policyDocument'])

        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['policy']['policyName'],
                         policy_ret['policyName'])

    def test_present_when_policy_exists(self):
        self.conn.get_policy.return_value = policy_ret
        self.conn.create_policy_version.return_value = policy_ret
        result = self.salt_states['boto_iot.policy_present'](
                         'policy present',
                         policyName=policy_ret['policyName'],
                         policyDocument=policy_ret['policyDocument'])
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_present_with_failure(self):
        self.conn.get_policy.side_effect = [not_found_error, policy_ret]
        self.conn.create_policy.side_effect = ClientError(error_content, 'create_policy')
        result = self.salt_states['boto_iot.policy_present'](
                         'policy present',
                         policyName=policy_ret['policyName'],
                         policyDocument=policy_ret['policyDocument'])
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])

    def test_absent_when_policy_does_not_exist(self):
        '''
        Tests absent on a policy that does not exist.
        '''
        self.conn.get_policy.side_effect = not_found_error
        result = self.salt_states['boto_iot.policy_absent']('test', 'mypolicy')
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_absent_when_policy_exists(self):
        self.conn.get_policy.return_value = policy_ret
        self.conn.list_policy_versions.return_value = {'policyVersions': []}
        result = self.salt_states['boto_iot.policy_absent']('test', policy_ret['policyName'])
        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['policy'], None)

    def test_absent_with_failure(self):
        self.conn.get_policy.return_value = policy_ret
        self.conn.list_policy_versions.return_value = {'policyVersions': []}
        self.conn.delete_policy.side_effect = ClientError(error_content, 'delete_policy')
        result = self.salt_states['boto_iot.policy_absent']('test', policy_ret['policyName'])
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])

    def test_attached_when_policy_not_attached(self):
        '''
        Tests attached on a policy that is not attached.
        '''
        self.conn.list_principal_policies.return_value = {'policies': []}
        result = self.salt_states['boto_iot.policy_attached']('test', 'myfunc', principal)
        self.assertTrue(result['result'])
        self.assertTrue(result['changes']['new']['attached'])

    def test_attached_when_policy_attached(self):
        '''
        Tests attached on a policy that is attached.
        '''
        self.conn.list_principal_policies.return_value = {'policies': [policy_ret]}
        result = self.salt_states['boto_iot.policy_attached']('test', policy_ret['policyName'], principal)
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_attached_with_failure(self):
        '''
        Tests attached on a policy that is attached.
        '''
        self.conn.list_principal_policies.return_value = {'policies': []}
        self.conn.attach_principal_policy.side_effect = ClientError(error_content, 'attach_principal_policy')
        result = self.salt_states['boto_iot.policy_attached']('test', policy_ret['policyName'], principal)
        self.assertFalse(result['result'])
        self.assertEqual(result['changes'], {})

    def test_detached_when_policy_not_detached(self):
        '''
        Tests detached on a policy that is not detached.
        '''
        self.conn.list_principal_policies.return_value = {'policies': [policy_ret]}
        result = self.salt_states['boto_iot.policy_detached']('test', policy_ret['policyName'], principal)
        self.assertTrue(result['result'])
        log.warning(result)
        self.assertFalse(result['changes']['new']['attached'])

    def test_detached_when_policy_detached(self):
        '''
        Tests detached on a policy that is detached.
        '''
        self.conn.list_principal_policies.return_value = {'policies': []}
        result = self.salt_states['boto_iot.policy_detached']('test', policy_ret['policyName'], principal)
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_detached_with_failure(self):
        '''
        Tests detached on a policy that is detached.
        '''
        self.conn.list_principal_policies.return_value = {'policies': [policy_ret]}
        self.conn.detach_principal_policy.side_effect = ClientError(error_content, 'detach_principal_policy')
        result = self.salt_states['boto_iot.policy_detached']('test', policy_ret['policyName'], principal)
        self.assertFalse(result['result'])
        self.assertEqual(result['changes'], {})


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}.  The botocore'
                                       ' module must be greater than or equal to'
                                       ' version {1}.'
        .format(required_boto3_version, required_botocore_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoIoTTopicRuleTestCase(BotoIoTStateTestCaseBase, BotoIoTTestCaseMixin):
    '''
    TestCase for salt.modules.boto_iot state.module rules
    '''

    def test_present_when_topic_rule_does_not_exist(self):
        '''
        Tests present on a topic_rule that does not exist.
        '''
        self.conn.get_topic_rule.side_effect = [topic_rule_not_found_error, {'rule': topic_rule_ret}]
        self.conn.create_topic_rule.return_value = {'created': True}
        result = self.salt_states['boto_iot.topic_rule_present'](
                         'topic rule present',
                         ruleName=topic_rule_ret['ruleName'],
                         sql=topic_rule_ret['sql'],
                         description=topic_rule_ret['description'],
                         actions=topic_rule_ret['actions'],
                         ruleDisabled=topic_rule_ret['ruleDisabled'])

        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['rule']['ruleName'],
                         topic_rule_ret['ruleName'])

    def test_present_when_policy_exists(self):
        self.conn.get_topic_rule.return_value = {'rule': topic_rule_ret}
        self.conn.create_topic_rule.return_value = {'created': True}
        result = self.salt_states['boto_iot.topic_rule_present'](
                         'topic rule present',
                         ruleName=topic_rule_ret['ruleName'],
                         sql=topic_rule_ret['sql'],
                         description=topic_rule_ret['description'],
                         actions=topic_rule_ret['actions'],
                         ruleDisabled=topic_rule_ret['ruleDisabled'])
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_present_with_failure(self):
        self.conn.get_topic_rule.side_effect = [topic_rule_not_found_error, {'rule': topic_rule_ret}]
        self.conn.create_topic_rule.side_effect = ClientError(error_content, 'create_topic_rule')
        result = self.salt_states['boto_iot.topic_rule_present'](
                         'topic rule present',
                         ruleName=topic_rule_ret['ruleName'],
                         sql=topic_rule_ret['sql'],
                         description=topic_rule_ret['description'],
                         actions=topic_rule_ret['actions'],
                         ruleDisabled=topic_rule_ret['ruleDisabled'])
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])

    def test_absent_when_topic_rule_does_not_exist(self):
        '''
        Tests absent on a topic rule that does not exist.
        '''
        self.conn.get_topic_rule.side_effect = topic_rule_not_found_error
        result = self.salt_states['boto_iot.topic_rule_absent']('test', 'myrule')
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_absent_when_topic_rule_exists(self):
        self.conn.get_topic_rule.return_value = topic_rule_ret
        result = self.salt_states['boto_iot.topic_rule_absent']('test', topic_rule_ret['ruleName'])
        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['rule'], None)

    def test_absent_with_failure(self):
        self.conn.get_topic_rule.return_value = topic_rule_ret
        self.conn.delete_topic_rule.side_effect = ClientError(error_content, 'delete_topic_rule')
        result = self.salt_states['boto_iot.topic_rule_absent']('test', topic_rule_ret['ruleName'])
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])

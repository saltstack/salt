# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import random
import string

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch

# Import Salt libs
import salt.config
import salt.loader

# Import 3rd-party libs
import logging

# Import Mock libraries
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# pylint: disable=import-error,no-name-in-module
from tests.unit.modules.test_boto_cloudwatch_event import BotoCloudWatchEventTestCaseMixin

# pylint: disable=unused-import
# Import 3rd-party libs
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False
# pylint: enable=unused-import

from salt.ext.six.moves import range

# pylint: enable=import-error,no-name-in-module

region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key, 'keyid': secret_key, 'profile': {}}
error_message = 'An error occurred (101) when calling the {0} operation: Test-defined error'
error_content = {
  'Error': {
    'Code': 101,
    'Message': "Test-defined error"
  }
}
if HAS_BOTO:
    not_found_error = ClientError({
        'Error': {
            'Code': 'ResourceNotFoundException',
            'Message': "Test-defined error"
        }
    }, 'msg')
rule_name = 'test_thing_type'
rule_desc = 'test_thing_type_desc'
rule_sched = 'rate(20 min)'
rule_arn = 'arn:::::rule/arn'
rule_ret = dict(
    Arn=rule_arn,
    Description=rule_desc,
    EventPattern=None,
    Name=rule_name,
    RoleArn=None,
    ScheduleExpression=rule_sched,
    State='ENABLED'
)


log = logging.getLogger(__name__)

opts = salt.config.DEFAULT_MINION_OPTS
context = {}
utils = salt.loader.utils(opts, whitelist=['boto3'], context=context)
serializers = salt.loader.serializers(opts)
funcs = salt.loader.minion_mods(opts, context=context, utils=utils, whitelist=['boto_cloudwatch_event'])
salt_states = salt.loader.states(opts=opts, functions=funcs, utils=utils, whitelist=['boto_cloudwatch_event'], serializers=serializers)


def _has_required_boto():
    '''
    Returns True/False boolean depending on if Boto is installed and correct
    version.
    '''
    if not HAS_BOTO:
        return False
    else:
        return True


class BotoCloudWatchEventStateTestCaseBase(TestCase):
    conn = None

    # Set up MagicMock to replace the boto3 session
    def setUp(self):
        context.clear()
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        conn_parameters['key'] = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(50))

        self.patcher = patch('boto3.session.Session')
        self.addCleanup(self.patcher.stop)
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        session_instance.client.return_value = self.conn


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoCloudWatchEventTestCase(BotoCloudWatchEventStateTestCaseBase, BotoCloudWatchEventTestCaseMixin):
    def test_present_when_failing_to_describe_rule(self):
        '''
        Tests exceptions when checking rule existence
        '''
        self.conn.list_rules.side_effect = ClientError(error_content, 'error on list rules')
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('error on list rules' in result.get('comment', {}))

    def test_present_when_failing_to_create_a_new_rule(self):
        '''
        Tests present on a rule name that doesn't exist and
        an error is thrown on creation.
        '''
        self.conn.list_rules.return_value = {'Rules': []}
        self.conn.put_rule.side_effect = ClientError(error_content, 'put_rule')
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('put_rule' in result.get('comment', ''))

    def test_present_when_failing_to_describe_the_new_rule(self):
        '''
        Tests present on a rule name that doesn't exist and
        an error is thrown when adding targets.
        '''
        self.conn.list_rules.return_value = {'Rules': []}
        self.conn.put_rule.return_value = rule_ret
        self.conn.describe_rule.side_effect = ClientError(error_content, 'describe_rule')
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('describe_rule' in result.get('comment', ''))

    def test_present_when_failing_to_create_a_new_rules_targets(self):
        '''
        Tests present on a rule name that doesn't exist and
        an error is thrown when adding targets.
        '''
        self.conn.list_rules.return_value = {'Rules': []}
        self.conn.put_rule.return_value = rule_ret
        self.conn.describe_rule.return_value = rule_ret
        self.conn.put_targets.side_effect = ClientError(error_content, 'put_targets')
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('put_targets' in result.get('comment', ''))

    def test_present_when_rule_does_not_exist(self):
        '''
        Tests the successful case of creating a new rule, and updating its
        targets
        '''
        self.conn.list_rules.return_value = {'Rules': []}
        self.conn.put_rule.return_value = rule_ret
        self.conn.describe_rule.return_value = rule_ret
        self.conn.put_targets.return_value = {'FailedEntryCount': 0}
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), True)

    def test_present_when_failing_to_update_an_existing_rule(self):
        '''
        Tests present on an existing rule where an error is thrown on updating the pool properties.
        '''
        self.conn.list_rules.return_value = {'Rules': [rule_ret]}
        self.conn.describe_rule.side_effect = ClientError(error_content, 'describe_rule')
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('describe_rule' in result.get('comment', ''))

    def test_present_when_failing_to_get_targets(self):
        '''
        Tests present on an existing rule where put_rule succeeded, but an error
        is thrown on getting targets
        '''
        self.conn.list_rules.return_value = {'Rules': [rule_ret]}
        self.conn.put_rule.return_value = rule_ret
        self.conn.describe_rule.return_value = rule_ret
        self.conn.list_targets_by_rule.side_effect = ClientError(error_content, 'list_targets')
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('list_targets' in result.get('comment', ''))

    def test_present_when_failing_to_put_targets(self):
        '''
        Tests present on an existing rule where put_rule succeeded, but an error
        is thrown on putting targets
        '''
        self.conn.list_rules.return_value = {'Rules': []}
        self.conn.put_rule.return_value = rule_ret
        self.conn.describe_rule.return_value = rule_ret
        self.conn.list_targets.return_value = {'Targets': []}
        self.conn.put_targets.side_effect = ClientError(error_content, 'put_targets')
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('put_targets' in result.get('comment', ''))

    def test_present_when_putting_targets(self):
        '''
        Tests present on an existing rule where put_rule succeeded, and targets
        must be added
        '''
        self.conn.list_rules.return_value = {'Rules': []}
        self.conn.put_rule.return_value = rule_ret
        self.conn.describe_rule.return_value = rule_ret
        self.conn.list_targets.return_value = {'Targets': []}
        self.conn.put_targets.return_value = {'FailedEntryCount': 0}
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), True)

    def test_present_when_removing_targets(self):
        '''
        Tests present on an existing rule where put_rule succeeded, and targets
        must be removed
        '''
        self.conn.list_rules.return_value = {'Rules': []}
        self.conn.put_rule.return_value = rule_ret
        self.conn.describe_rule.return_value = rule_ret
        self.conn.list_targets.return_value = {'Targets': [{'Id': 'target1'}, {'Id': 'target2'}]}
        self.conn.put_targets.return_value = {'FailedEntryCount': 0}
        result = salt_states['boto_cloudwatch_event.present'](
                             name='test present',
                             Name=rule_name,
                             Description=rule_desc,
                             ScheduleExpression=rule_sched,
                             Targets=[{
                               'Id': 'target1',
                               'Arn': 'arn::::::*',
                             }],
                             **conn_parameters)
        self.assertEqual(result.get('result'), True)

    def test_absent_when_failing_to_describe_rule(self):
        '''
        Tests exceptions when checking rule existence
        '''
        self.conn.list_rules.side_effect = ClientError(error_content, 'error on list rules')
        result = salt_states['boto_cloudwatch_event.absent'](
                             name='test present',
                             Name=rule_name,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('error on list rules' in result.get('comment', {}))

    def test_absent_when_rule_does_not_exist(self):
        '''
        Tests absent on an non-existing rule
        '''
        self.conn.list_rules.return_value = {'Rules': []}
        result = salt_states['boto_cloudwatch_event.absent'](
                             name='test absent',
                             Name=rule_name,
                             **conn_parameters)
        self.assertEqual(result.get('result'), True)
        self.assertEqual(result['changes'], {})

    def test_absent_when_failing_to_list_targets(self):
        '''
        Tests absent on an rule when the list_targets call fails
        '''
        self.conn.list_rules.return_value = {'Rules': [rule_ret]}
        self.conn.list_targets_by_rule.side_effect = ClientError(error_content, 'list_targets')
        result = salt_states['boto_cloudwatch_event.absent'](
                             name='test absent',
                             Name=rule_name,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('list_targets' in result.get('comment', ''))

    def test_absent_when_failing_to_remove_targets_exception(self):
        '''
        Tests absent on an rule when the remove_targets call fails
        '''
        self.conn.list_rules.return_value = {'Rules': [rule_ret]}
        self.conn.list_targets_by_rule.return_value = {'Targets': [{'Id': 'target1'}]}
        self.conn.remove_targets.side_effect = ClientError(error_content, 'remove_targets')
        result = salt_states['boto_cloudwatch_event.absent'](
                             name='test absent',
                             Name=rule_name,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('remove_targets' in result.get('comment', ''))

    def test_absent_when_failing_to_remove_targets_nonexception(self):
        '''
        Tests absent on an rule when the remove_targets call fails
        '''
        self.conn.list_rules.return_value = {'Rules': [rule_ret]}
        self.conn.list_targets_by_rule.return_value = {'Targets': [{'Id': 'target1'}]}
        self.conn.remove_targets.return_value = {'FailedEntryCount': 1}
        result = salt_states['boto_cloudwatch_event.absent'](
                             name='test absent',
                             Name=rule_name,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)

    def test_absent_when_failing_to_delete_rule(self):
        '''
        Tests absent on an rule when the delete_rule call fails
        '''
        self.conn.list_rules.return_value = {'Rules': [rule_ret]}
        self.conn.list_targets_by_rule.return_value = {'Targets': [{'Id': 'target1'}]}
        self.conn.remove_targets.return_value = {'FailedEntryCount': 0}
        self.conn.delete_rule.side_effect = ClientError(error_content, 'delete_rule')
        result = salt_states['boto_cloudwatch_event.absent'](
                             name='test absent',
                             Name=rule_name,
                             **conn_parameters)
        self.assertEqual(result.get('result'), False)
        self.assertTrue('delete_rule' in result.get('comment', ''))

    def test_absent(self):
        '''
        Tests absent on an rule
        '''
        self.conn.list_rules.return_value = {'Rules': [rule_ret]}
        self.conn.list_targets_by_rule.return_value = {'Targets': [{'Id': 'target1'}]}
        self.conn.remove_targets.return_value = {'FailedEntryCount': 0}
        result = salt_states['boto_cloudwatch_event.absent'](
                             name='test absent',
                             Name=rule_name,
                             **conn_parameters)
        self.assertEqual(result.get('result'), True)

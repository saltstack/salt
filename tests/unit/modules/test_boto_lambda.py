# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import platform
import random
import string

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt libs
import salt.config
import salt.ext.six as six
import salt.loader
from salt.modules import boto_lambda
from salt.exceptions import SaltInvocationError
from salt.utils.versions import LooseVersion
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
import salt.utils

# Import 3rd-party libs
from tempfile import NamedTemporaryFile
import logging
import os

# pylint: disable=import-error,no-name-in-module
try:
    import boto3
    from botocore.exceptions import ClientError
    from botocore import __version__ as found_botocore_version
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

ON_SUSE = False
if 'SuSE' in platform.dist():
    ON_SUSE = True

# pylint: enable=import-error,no-name-in-module

# the boto_lambda module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = '1.2.1'
required_botocore_version = '1.5.2'

region = 'us-east-1'
access_key = 'GKTADJGHEIQSXMKKRBJ08H'
secret_key = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
conn_parameters = {'region': region, 'key': access_key,
                   'keyid': secret_key, 'profile': {}}
error_message = 'An error occurred (101) when calling the {0} operation: Test-defined error'
error_content = {
    'Error': {
        'Code': 101,
        'Message': "Test-defined error"
    }
}
function_ret = dict(FunctionName='testfunction',
                    Runtime='python2.7',
                    Role=None,
                    Handler='handler',
                    Description='abcdefg',
                    Timeout=5,
                    MemorySize=128,
                    CodeSha256='abcdef',
                    CodeSize=199,
                    FunctionArn='arn:lambda:us-east-1:1234:Something',
                    LastModified='yes',
                    VpcConfig=None,
                    Environment=None)
alias_ret = dict(AliasArn='arn:lambda:us-east-1:1234:Something',
                 Name='testalias',
                 FunctionVersion='3',
                 Description='Alias description')
event_source_mapping_ret = dict(UUID='1234-1-123',
                                BatchSize=123,
                                EventSourceArn='arn:lambda:us-east-1:1234:Something',
                                FunctionArn='arn:lambda:us-east-1:1234:Something',
                                LastModified='yes',
                                LastProcessingResult='SUCCESS',
                                State='Enabled',
                                StateTransitionReason='Random')

log = logging.getLogger(__name__)

opts = salt.config.DEFAULT_MINION_OPTS
context = {}
utils = salt.loader.utils(opts, whitelist=['boto3'], context=context)

boto_lambda.__utils__ = utils
boto_lambda.__init__(opts)
boto_lambda.__salt__ = {}


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


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False,
        ('The boto3 module must be greater than or equal to version {0}, '
         'and botocore must be greater than or equal to {1}'.format(
             required_boto3_version, required_botocore_version)))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoLambdaTestCaseBase(TestCase):
    conn = None

    # Set up MagicMock to replace the boto3 session
    def setUp(self):
        boto_lambda.__context__ = {}
        context.clear()
        # connections keep getting cached from prior tests, can't find the
        # correct context object to clear it. So randomize the cache key, to prevent any
        # cache hits
        conn_parameters['key'] = ''.join(random.choice(
            string.ascii_lowercase + string.digits) for _ in range(50))

        self.patcher = patch('boto3.session.Session')
        self.addCleanup(self.patcher.stop)
        mock_session = self.patcher.start()

        session_instance = mock_session.return_value
        self.conn = MagicMock()
        session_instance.client.return_value = self.conn


class TempZipFile(object):

    def __enter__(self):
        with NamedTemporaryFile(
                suffix='.zip', prefix='salt_test_', delete=False) as tmp:
            to_write = '###\n'
            if six.PY3:
                to_write = salt.utils.to_bytes(to_write)
            tmp.write(to_write)
            self.zipfile = tmp.name
        return self.zipfile

    def __exit__(self, type, value, traceback):
        os.remove(self.zipfile)


class BotoLambdaTestCaseMixin(object):
    pass


class BotoLambdaFunctionTestCase(BotoLambdaTestCaseBase, BotoLambdaTestCaseMixin):
    '''
    TestCase for salt.modules.boto_lambda module
    '''

    def test_that_when_checking_if_a_function_exists_and_a_function_exists_the_function_exists_method_returns_true(self):
        '''
        Tests checking lambda function existence when the lambda function already exists
        '''
        self.conn.list_functions.return_value = {'Functions': [function_ret]}
        func_exists_result = boto_lambda.function_exists(
            FunctionName=function_ret['FunctionName'], **conn_parameters)

        self.assertTrue(func_exists_result['exists'])

    def test_that_when_checking_if_a_function_exists_and_a_function_does_not_exist_the_function_exists_method_returns_false(self):
        '''
        Tests checking lambda function existence when the lambda function does not exist
        '''
        self.conn.list_functions.return_value = {'Functions': [function_ret]}
        func_exists_result = boto_lambda.function_exists(
            FunctionName='myfunc', **conn_parameters)

        self.assertFalse(func_exists_result['exists'])

    def test_that_when_checking_if_a_function_exists_and_boto3_returns_an_error_the_function_exists_method_returns_error(self):
        '''
        Tests checking lambda function existence when boto returns an error
        '''
        self.conn.list_functions.side_effect = ClientError(
            error_content, 'list_functions')
        func_exists_result = boto_lambda.function_exists(
            FunctionName='myfunc', **conn_parameters)

        self.assertEqual(func_exists_result.get('error', {}).get(
            'message'), error_message.format('list_functions'))

    def test_that_when_creating_a_function_from_zipfile_succeeds_the_create_function_method_returns_true(self):
        '''
        tests True function created.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            with TempZipFile() as zipfile:
                self.conn.create_function.return_value = function_ret
                lambda_creation_result = boto_lambda.create_function(
                    FunctionName='testfunction',
                    Runtime='python2.7',
                    Role='myrole',
                    Handler='file.method',
                    ZipFile=zipfile,
                    **conn_parameters)

        self.assertTrue(lambda_creation_result['created'])

    def test_that_when_creating_a_function_from_s3_succeeds_the_create_function_method_returns_true(self):
        '''
        tests True function created.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.create_function.return_value = function_ret
            lambda_creation_result = boto_lambda.create_function(
                FunctionName='testfunction',
                Runtime='python2.7',
                Role='myrole',
                Handler='file.method',
                S3Bucket='bucket',
                S3Key='key',
                **conn_parameters)

        self.assertTrue(lambda_creation_result['created'])

    def test_that_when_creating_a_function_without_code_raises_a_salt_invocation_error(self):
        '''
        tests Creating a function without code
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            with self.assertRaisesRegexp(SaltInvocationError,
                                         'Either ZipFile must be specified, or S3Bucket and S3Key must be provided.'):
                lambda_creation_result = boto_lambda.create_function(
                    FunctionName='testfunction',
                    Runtime='python2.7',
                    Role='myrole',
                    Handler='file.method',
                    **conn_parameters)

    def test_that_when_creating_a_function_with_zipfile_and_s3_raises_a_salt_invocation_error(self):
        '''
        tests Creating a function without code
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            with self.assertRaisesRegexp(SaltInvocationError,
                                         'Either ZipFile must be specified, or S3Bucket and S3Key must be provided.'):
                with TempZipFile() as zipfile:
                    lambda_creation_result = boto_lambda.create_function(
                        FunctionName='testfunction',
                        Runtime='python2.7',
                        Role='myrole',
                        Handler='file.method',
                        ZipFile=zipfile,
                        S3Bucket='bucket',
                        S3Key='key',
                        **conn_parameters)

    def test_that_when_creating_a_function_fails_the_create_function_method_returns_error(self):
        '''
        tests False function not created.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.create_function.side_effect = ClientError(
                error_content, 'create_function')
            with TempZipFile() as zipfile:
                lambda_creation_result = boto_lambda.create_function(
                    FunctionName='testfunction',
                    Runtime='python2.7',
                    Role='myrole',
                    Handler='file.method',
                    ZipFile=zipfile,
                    **conn_parameters)
        self.assertEqual(lambda_creation_result.get('error', {}).get(
            'message'), error_message.format('create_function'))

    def test_that_when_deleting_a_function_succeeds_the_delete_function_method_returns_true(self):
        '''
        tests True function deleted.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_lambda.delete_function(FunctionName='testfunction',
                                                 Qualifier=1,
                                                 **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_a_function_fails_the_delete_function_method_returns_false(self):
        '''
        tests False function not deleted.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.delete_function.side_effect = ClientError(
                error_content, 'delete_function')
            result = boto_lambda.delete_function(FunctionName='testfunction',
                                                 **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_describing_function_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if function exists
        '''
        self.conn.list_functions.return_value = {'Functions': [function_ret]}

        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_lambda.describe_function(
                FunctionName=function_ret['FunctionName'], **conn_parameters)

        self.assertEqual(result, {'function': function_ret})

    def test_that_when_describing_function_it_returns_the_dict_of_properties_returns_false(self):
        '''
        Tests describing parameters if function does not exist
        '''
        self.conn.list_functions.return_value = {'Functions': []}
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_lambda.describe_function(
                FunctionName='testfunction', **conn_parameters)

        self.assertFalse(result['function'])

    def test_that_when_describing_lambda_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.list_functions.side_effect = ClientError(
            error_content, 'list_functions')
        result = boto_lambda.describe_function(
            FunctionName='testfunction', **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_updating_a_function_succeeds_the_update_function_method_returns_true(self):
        '''
        tests True function updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.update_function_config.return_value = function_ret
            result = boto_lambda.update_function_config(
                FunctionName=function_ret['FunctionName'], Role='myrole', **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_updating_a_function_fails_the_update_function_method_returns_error(self):
        '''
        tests False function not updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.update_function_configuration.side_effect = ClientError(
                error_content, 'update_function')
            result = boto_lambda.update_function_config(FunctionName='testfunction',
                                                        Role='myrole',
                                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('update_function'))

    def test_that_when_updating_function_code_from_zipfile_succeeds_the_update_function_method_returns_true(self):
        '''
        tests True function updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            with TempZipFile() as zipfile:
                self.conn.update_function_code.return_value = function_ret
                result = boto_lambda.update_function_code(
                    FunctionName=function_ret['FunctionName'],
                    ZipFile=zipfile, **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_updating_function_code_from_s3_succeeds_the_update_function_method_returns_true(self):
        '''
        tests True function updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.update_function_code.return_value = function_ret
            result = boto_lambda.update_function_code(
                FunctionName='testfunction',
                S3Bucket='bucket',
                S3Key='key',
                **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_updating_function_code_without_code_raises_a_salt_invocation_error(self):
        '''
        tests Creating a function without code
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            with self.assertRaisesRegexp(
                SaltInvocationError,
                ('Either ZipFile must be specified, or S3Bucket '
                 'and S3Key must be provided.')):
                result = boto_lambda.update_function_code(
                    FunctionName='testfunction',
                    **conn_parameters)

    def test_that_when_updating_function_code_fails_the_update_function_method_returns_error(self):
        '''
        tests False function not updated.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.update_function_code.side_effect = ClientError(
                error_content, 'update_function_code')
            result = boto_lambda.update_function_code(
                FunctionName='testfunction',
                S3Bucket='bucket',
                S3Key='key',
                **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('update_function_code'))

    def test_that_when_listing_function_versions_succeeds_the_list_function_versions_method_returns_true(self):
        '''
        tests True function versions listed.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.list_versions_by_function.return_value = {
                'Versions': [function_ret]}
            result = boto_lambda.list_function_versions(
                FunctionName='testfunction',
                **conn_parameters)

        self.assertTrue(result['Versions'])

    def test_that_when_listing_function_versions_fails_the_list_function_versions_method_returns_false(self):
        '''
        tests False no function versions listed.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.list_versions_by_function.return_value = {'Versions': []}
            result = boto_lambda.list_function_versions(
                FunctionName='testfunction',
                **conn_parameters)
        self.assertFalse(result['Versions'])

    def test_that_when_listing_function_versions_fails_the_list_function_versions_method_returns_error(self):
        '''
        tests False function versions error.
        '''
        with patch.dict(boto_lambda.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            self.conn.list_versions_by_function.side_effect = ClientError(
                error_content, 'list_versions_by_function')
            result = boto_lambda.list_function_versions(
                FunctionName='testfunction',
                **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('list_versions_by_function'))


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoLambdaAliasTestCase(BotoLambdaTestCaseBase, BotoLambdaTestCaseMixin):
    '''
    TestCase for salt.modules.boto_lambda module aliases
    '''

    def test_that_when_creating_an_alias_succeeds_the_create_alias_method_returns_true(self):
        '''
        tests True alias created.
        '''
        self.conn.create_alias.return_value = alias_ret
        result = boto_lambda.create_alias(FunctionName='testfunction',
                                          Name=alias_ret['Name'],
                                          FunctionVersion=alias_ret[
                                              'FunctionVersion'],
                                          **conn_parameters)

        self.assertTrue(result['created'])

    def test_that_when_creating_an_alias_fails_the_create_alias_method_returns_error(self):
        '''
        tests False alias not created.
        '''
        self.conn.create_alias.side_effect = ClientError(
            error_content, 'create_alias')
        result = boto_lambda.create_alias(FunctionName='testfunction',
                                          Name=alias_ret['Name'],
                                          FunctionVersion=alias_ret[
                                              'FunctionVersion'],
                                          **conn_parameters)
        self.assertEqual(result.get('error', {}).get(
            'message'), error_message.format('create_alias'))

    def test_that_when_deleting_an_alias_succeeds_the_delete_alias_method_returns_true(self):
        '''
        tests True alias deleted.
        '''
        result = boto_lambda.delete_alias(FunctionName='testfunction',
                                          Name=alias_ret['Name'],
                                          **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_an_alias_fails_the_delete_alias_method_returns_false(self):
        '''
        tests False alias not deleted.
        '''
        self.conn.delete_alias.side_effect = ClientError(
            error_content, 'delete_alias')
        result = boto_lambda.delete_alias(FunctionName='testfunction',
                                          Name=alias_ret['Name'],
                                          **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_checking_if_an_alias_exists_and_the_alias_exists_the_alias_exists_method_returns_true(self):
        '''
        Tests checking lambda alias existence when the lambda alias already exists
        '''
        self.conn.list_aliases.return_value = {'Aliases': [alias_ret]}
        result = boto_lambda.alias_exists(FunctionName='testfunction',
                                          Name=alias_ret['Name'],
                                          **conn_parameters)
        self.assertTrue(result['exists'])

    def test_that_when_checking_if_an_alias_exists_and_the_alias_does_not_exist_the_alias_exists_method_returns_false(self):
        '''
        Tests checking lambda alias existence when the lambda alias does not exist
        '''
        self.conn.list_aliases.return_value = {'Aliases': [alias_ret]}
        result = boto_lambda.alias_exists(FunctionName='testfunction',
                                          Name='otheralias',
                                          **conn_parameters)

        self.assertFalse(result['exists'])

    def test_that_when_checking_if_an_alias_exists_and_boto3_returns_an_error_the_alias_exists_method_returns_error(self):
        '''
        Tests checking lambda alias existence when boto returns an error
        '''
        self.conn.list_aliases.side_effect = ClientError(
            error_content, 'list_aliases')
        result = boto_lambda.alias_exists(FunctionName='testfunction',
                                          Name=alias_ret['Name'],
                                          **conn_parameters)

        self.assertEqual(result.get('error', {}).get(
            'message'), error_message.format('list_aliases'))

    def test_that_when_describing_alias_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if alias exists
        '''
        self.conn.list_aliases.return_value = {'Aliases': [alias_ret]}

        result = boto_lambda.describe_alias(FunctionName='testfunction',
                                            Name=alias_ret['Name'],
                                            **conn_parameters)

        self.assertEqual(result, {'alias': alias_ret})

    def test_that_when_describing_alias_it_returns_the_dict_of_properties_returns_false(self):
        '''
        Tests describing parameters if alias does not exist
        '''
        self.conn.list_aliases.return_value = {'Aliases': [alias_ret]}
        result = boto_lambda.describe_alias(FunctionName='testfunction',
                                            Name='othername',
                                            **conn_parameters)

        self.assertFalse(result['alias'])

    def test_that_when_describing_lambda_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.list_aliases.side_effect = ClientError(
            error_content, 'list_aliases')
        result = boto_lambda.describe_alias(FunctionName='testfunction',
                                            Name=alias_ret['Name'],
                                            **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_updating_an_alias_succeeds_the_update_alias_method_returns_true(self):
        '''
        tests True alias updated.
        '''
        self.conn.update_alias.return_value = alias_ret
        result = boto_lambda.update_alias(FunctionName='testfunctoin',
                                          Name=alias_ret['Name'],
                                          Description=alias_ret['Description'],
                                          **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_updating_an_alias_fails_the_update_alias_method_returns_error(self):
        '''
        tests False alias not updated.
        '''
        self.conn.update_alias.side_effect = ClientError(
            error_content, 'update_alias')
        result = boto_lambda.update_alias(FunctionName='testfunction',
                                          Name=alias_ret['Name'],
                                          **conn_parameters)
        self.assertEqual(result.get('error', {}).get(
            'message'), error_message.format('update_alias'))


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoLambdaEventSourceMappingTestCase(BotoLambdaTestCaseBase, BotoLambdaTestCaseMixin):
    '''
    TestCase for salt.modules.boto_lambda module mappings
    '''

    def test_that_when_creating_a_mapping_succeeds_the_create_event_source_mapping_method_returns_true(self):
        '''
        tests True mapping created.
        '''
        self.conn.create_event_source_mapping.return_value = event_source_mapping_ret
        result = boto_lambda.create_event_source_mapping(
            EventSourceArn=event_source_mapping_ret['EventSourceArn'],
            FunctionName=event_source_mapping_ret['FunctionArn'],
            StartingPosition='LATEST',
            **conn_parameters)

        self.assertTrue(result['created'])

    def test_that_when_creating_an_event_source_mapping_fails_the_create_event_source_mapping_method_returns_error(self):
        '''
        tests False mapping not created.
        '''
        self.conn.create_event_source_mapping.side_effect = ClientError(
            error_content, 'create_event_source_mapping')
        result = boto_lambda.create_event_source_mapping(
            EventSourceArn=event_source_mapping_ret['EventSourceArn'],
            FunctionName=event_source_mapping_ret['FunctionArn'],
            StartingPosition='LATEST',
            **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('create_event_source_mapping'))

    def test_that_when_listing_mapping_ids_succeeds_the_get_event_source_mapping_ids_method_returns_true(self):
        '''
        tests True mapping ids listed.
        '''
        self.conn.list_event_source_mappings.return_value = {
            'EventSourceMappings': [event_source_mapping_ret]}
        result = boto_lambda.get_event_source_mapping_ids(
            EventSourceArn=event_source_mapping_ret['EventSourceArn'],
            FunctionName=event_source_mapping_ret['FunctionArn'],
            **conn_parameters)

        self.assertTrue(result)

    def test_that_when_listing_event_source_mapping_ids_fails_the_get_event_source_mapping_ids_versions_method_returns_false(self):
        '''
        tests False no mapping ids listed.
        '''
        self.conn.list_event_source_mappings.return_value = {
            'EventSourceMappings': []}
        result = boto_lambda.get_event_source_mapping_ids(
            EventSourceArn=event_source_mapping_ret['EventSourceArn'],
            FunctionName=event_source_mapping_ret['FunctionArn'],
            **conn_parameters)
        self.assertFalse(result)

    def test_that_when_listing_event_source_mapping_ids_fails_the_get_event_source_mapping_ids_method_returns_error(self):
        '''
        tests False mapping ids error.
        '''
        self.conn.list_event_source_mappings.side_effect = ClientError(
            error_content, 'list_event_source_mappings')
        result = boto_lambda.get_event_source_mapping_ids(
            EventSourceArn=event_source_mapping_ret['EventSourceArn'],
            FunctionName=event_source_mapping_ret['FunctionArn'],
            **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('list_event_source_mappings'))

    def test_that_when_deleting_an_event_source_mapping_by_UUID_succeeds_the_delete_event_source_mapping_method_returns_true(self):
        '''
        tests True mapping deleted.
        '''
        result = boto_lambda.delete_event_source_mapping(
            UUID=event_source_mapping_ret['UUID'],
            **conn_parameters)
        self.assertTrue(result['deleted'])

    @skipIf(True, 'This appears to leak memory and crash the unit test suite')
    def test_that_when_deleting_an_event_source_mapping_by_name_succeeds_the_delete_event_source_mapping_method_returns_true(self):
        '''
        tests True mapping deleted.
        '''
        self.conn.list_event_source_mappings.return_value = {
            'EventSourceMappings': [event_source_mapping_ret]}
        result = boto_lambda.delete_event_source_mapping(
            EventSourceArn=event_source_mapping_ret['EventSourceArn'],
            FunctionName=event_source_mapping_ret['FunctionArn'],
            **conn_parameters)
        self.assertTrue(result['deleted'])

    def test_that_when_deleting_an_event_source_mapping_without_identifier_the_delete_event_source_mapping_method_raises_saltinvocationexception(self):
        '''
        tests Deleting a mapping without identifier
        '''
        with self.assertRaisesRegexp(
            SaltInvocationError,
            ('Either UUID must be specified, or EventSourceArn '
             'and FunctionName must be provided.')):
            result = boto_lambda.delete_event_source_mapping(**conn_parameters)

    def test_that_when_deleting_an_event_source_mapping_fails_the_delete_event_source_mapping_method_returns_false(self):
        '''
        tests False mapping not deleted.
        '''
        self.conn.delete_event_source_mapping.side_effect = ClientError(
            error_content, 'delete_event_source_mapping')
        result = boto_lambda.delete_event_source_mapping(UUID=event_source_mapping_ret['UUID'],
                                                         **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_checking_if_an_event_source_mapping_exists_and_the_event_source_mapping_exists_the_event_source_mapping_exists_method_returns_true(self):
        '''
        Tests checking lambda event_source_mapping existence when the lambda
        event_source_mapping already exists
        '''
        self.conn.get_event_source_mapping.return_value = event_source_mapping_ret
        result = boto_lambda.event_source_mapping_exists(
            UUID=event_source_mapping_ret['UUID'],
            **conn_parameters)
        self.assertTrue(result['exists'])

    def test_that_when_checking_if_an_event_source_mapping_exists_and_the_event_source_mapping_does_not_exist_the_event_source_mapping_exists_method_returns_false(self):
        '''
        Tests checking lambda event_source_mapping existence when the lambda
        event_source_mapping does not exist
        '''
        self.conn.get_event_source_mapping.return_value = None
        result = boto_lambda.event_source_mapping_exists(
            UUID='other_UUID',
            **conn_parameters)
        self.assertFalse(result['exists'])

    def test_that_when_checking_if_an_event_source_mapping_exists_and_boto3_returns_an_error_the_event_source_mapping_exists_method_returns_error(self):
        '''
        Tests checking lambda event_source_mapping existence when boto returns an error
        '''
        self.conn.get_event_source_mapping.side_effect = ClientError(
            error_content, 'list_event_source_mappings')
        result = boto_lambda.event_source_mapping_exists(
            UUID=event_source_mapping_ret['UUID'],
            **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('list_event_source_mappings'))

    def test_that_when_describing_event_source_mapping_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if event_source_mapping exists
        '''
        self.conn.get_event_source_mapping.return_value = event_source_mapping_ret
        result = boto_lambda.describe_event_source_mapping(
            UUID=event_source_mapping_ret['UUID'],
            **conn_parameters)
        self.assertEqual(
            result, {'event_source_mapping': event_source_mapping_ret})

    def test_that_when_describing_event_source_mapping_it_returns_the_dict_of_properties_returns_false(self):
        '''
        Tests describing parameters if event_source_mapping does not exist
        '''
        self.conn.get_event_source_mapping.return_value = None
        result = boto_lambda.describe_event_source_mapping(
            UUID=event_source_mapping_ret['UUID'],
            **conn_parameters)
        self.assertFalse(result['event_source_mapping'])

    def test_that_when_describing_event_source_mapping_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.get_event_source_mapping.side_effect = ClientError(
            error_content, 'get_event_source_mapping')
        result = boto_lambda.describe_event_source_mapping(
            UUID=event_source_mapping_ret['UUID'],
            **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_updating_an_event_source_mapping_succeeds_the_update_event_source_mapping_method_returns_true(self):
        '''
        tests True event_source_mapping updated.
        '''
        self.conn.update_event_source_mapping.return_value = event_source_mapping_ret
        result = boto_lambda.update_event_source_mapping(
            UUID=event_source_mapping_ret['UUID'],
            FunctionName=event_source_mapping_ret['FunctionArn'],
            **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_updating_an_event_source_mapping_fails_the_update_event_source_mapping_method_returns_error(self):
        '''
        tests False event_source_mapping not updated.
        '''
        self.conn.update_event_source_mapping.side_effect = ClientError(
            error_content, 'update_event_source_mapping')
        result = boto_lambda.update_event_source_mapping(
            UUID=event_source_mapping_ret['UUID'],
            FunctionName=event_source_mapping_ret['FunctionArn'],
            **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                         error_message.format('update_event_source_mapping'))

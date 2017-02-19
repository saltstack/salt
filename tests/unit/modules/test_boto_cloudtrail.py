# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
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
from salt.modules import boto_cloudtrail
from salt.utils.versions import LooseVersion
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,unused-import
try:
    import boto
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module,unused-import

# the boto_cloudtrail module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = '1.2.1'

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
            'Code': 'TrailNotFoundException',
            'Message': "Test-defined error"
        }
    }, 'msg')
    error_content = {
      'Error': {
        'Code': 101,
        'Message': "Test-defined error"
      }
    }
    trail_ret = dict(Name='testtrail',
                     IncludeGlobalServiceEvents=True,
                     KmsKeyId=None,
                     LogFileValidationEnabled=False,
                     S3BucketName='auditinfo',
                     TrailARN='arn:aws:cloudtrail:us-east-1:214351231622:trail/testtrail')
    status_ret = dict(IsLogging=False,
                      LatestCloudWatchLogsDeliveryError=None,
                      LatestCloudWatchLogsDeliveryTime=None,
                      LatestDeliveryError=None,
                      LatestDeliveryTime=None,
                      LatestDigestDeliveryError=None,
                      LatestDigestDeliveryTime=None,
                      LatestNotificationError=None,
                      LatestNotificationTime=None,
                      StartLoggingTime=None,
                      StopLoggingTime=None)


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoCloudTrailTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    loader_module = boto_cloudtrail

    def loader_module_globals(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS
        utils = salt.loader.utils(opts, whitelist=['boto3'], context={})
        return {
            '__utils__': utils,
        }

    def setUp(self):
        super(BotoCloudTrailTestCaseBase, self).setUp()
        boto_cloudtrail.__init__(self.opts)
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


class BotoCloudTrailTestCaseMixin(object):
    pass


class BotoCloudTrailTestCase(BotoCloudTrailTestCaseBase, BotoCloudTrailTestCaseMixin):
    '''
    TestCase for salt.modules.boto_cloudtrail module
    '''

    def test_that_when_checking_if_a_trail_exists_and_a_trail_exists_the_trail_exists_method_returns_true(self):
        '''
        Tests checking cloudtrail trail existence when the cloudtrail trail already exists
        '''
        self.conn.get_trail_status.return_value = trail_ret
        result = boto_cloudtrail.exists(Name=trail_ret['Name'], **conn_parameters)

        self.assertTrue(result['exists'])

    def test_that_when_checking_if_a_trail_exists_and_a_trail_does_not_exist_the_trail_exists_method_returns_false(self):
        '''
        Tests checking cloudtrail trail existence when the cloudtrail trail does not exist
        '''
        self.conn.get_trail_status.side_effect = not_found_error
        result = boto_cloudtrail.exists(Name='mytrail', **conn_parameters)

        self.assertFalse(result['exists'])

    def test_that_when_checking_if_a_trail_exists_and_boto3_returns_an_error_the_trail_exists_method_returns_error(self):
        '''
        Tests checking cloudtrail trail existence when boto returns an error
        '''
        self.conn.get_trail_status.side_effect = ClientError(error_content, 'get_trail_status')
        result = boto_cloudtrail.exists(Name='mytrail', **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'), error_message.format('get_trail_status'))

    def test_that_when_creating_a_trail_succeeds_the_create_trail_method_returns_true(self):
        '''
        tests True trail created.
        '''
        self.conn.create_trail.return_value = trail_ret
        result = boto_cloudtrail.create(Name=trail_ret['Name'],
                                        S3BucketName=trail_ret['S3BucketName'],
                                        **conn_parameters)

        self.assertTrue(result['created'])

    def test_that_when_creating_a_trail_fails_the_create_trail_method_returns_error(self):
        '''
        tests False trail not created.
        '''
        self.conn.create_trail.side_effect = ClientError(error_content, 'create_trail')
        result = boto_cloudtrail.create(Name=trail_ret['Name'],
                                        S3BucketName=trail_ret['S3BucketName'],
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('create_trail'))

    def test_that_when_deleting_a_trail_succeeds_the_delete_trail_method_returns_true(self):
        '''
        tests True trail deleted.
        '''
        result = boto_cloudtrail.delete(Name='testtrail',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_a_trail_fails_the_delete_trail_method_returns_false(self):
        '''
        tests False trail not deleted.
        '''
        self.conn.delete_trail.side_effect = ClientError(error_content, 'delete_trail')
        result = boto_cloudtrail.delete(Name='testtrail',
                                        **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_describing_trail_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if trail exists
        '''
        self.conn.describe_trails.return_value = {'trailList': [trail_ret]}

        result = boto_cloudtrail.describe(Name=trail_ret['Name'], **conn_parameters)

        self.assertTrue(result['trail'])

    def test_that_when_describing_trail_it_returns_the_dict_of_properties_returns_false(self):
        '''
        Tests describing parameters if trail does not exist
        '''
        self.conn.describe_trails.side_effect = not_found_error
        result = boto_cloudtrail.describe(Name='testtrail', **conn_parameters)

        self.assertFalse(result['trail'])

    def test_that_when_describing_trail_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.describe_trails.side_effect = ClientError(error_content, 'get_trail')
        result = boto_cloudtrail.describe(Name='testtrail', **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_getting_status_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests getting status if trail exists
        '''
        self.conn.get_trail_status.return_value = status_ret

        result = boto_cloudtrail.status(Name=trail_ret['Name'], **conn_parameters)

        self.assertTrue(result['trail'])

    def test_that_when_getting_status_it_returns_the_dict_of_properties_returns_false(self):
        '''
        Tests getting status if trail does not exist
        '''
        self.conn.get_trail_status.side_effect = not_found_error
        result = boto_cloudtrail.status(Name='testtrail', **conn_parameters)

        self.assertFalse(result['trail'])

    def test_that_when_getting_status_on_client_error_it_returns_error(self):
        '''
        Tests getting status failure
        '''
        self.conn.get_trail_status.side_effect = ClientError(error_content, 'get_trail_status')
        result = boto_cloudtrail.status(Name='testtrail', **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_listing_trails_succeeds_the_list_trails_method_returns_true(self):
        '''
        tests True trails listed.
        '''
        self.conn.describe_trails.return_value = {'trailList': [trail_ret]}
        result = boto_cloudtrail.list(**conn_parameters)

        self.assertTrue(result['trails'])

    def test_that_when_listing_trail_fails_the_list_trail_method_returns_false(self):
        '''
        tests False no trail listed.
        '''
        self.conn.describe_trails.return_value = {'trailList': []}
        result = boto_cloudtrail.list(**conn_parameters)
        self.assertFalse(result['trails'])

    def test_that_when_listing_trail_fails_the_list_trail_method_returns_error(self):
        '''
        tests False trail error.
        '''
        self.conn.describe_trails.side_effect = ClientError(error_content, 'list_trails')
        result = boto_cloudtrail.list(**conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('list_trails'))

    def test_that_when_updating_a_trail_succeeds_the_update_trail_method_returns_true(self):
        '''
        tests True trail updated.
        '''
        self.conn.update_trail.return_value = trail_ret
        result = boto_cloudtrail.update(Name=trail_ret['Name'],
                                        S3BucketName=trail_ret['S3BucketName'],
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_updating_a_trail_fails_the_update_trail_method_returns_error(self):
        '''
        tests False trail not updated.
        '''
        self.conn.update_trail.side_effect = ClientError(error_content, 'update_trail')
        result = boto_cloudtrail.update(Name=trail_ret['Name'],
                                        S3BucketName=trail_ret['S3BucketName'],
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('update_trail'))

    def test_that_when_starting_logging_succeeds_the_start_logging_method_returns_true(self):
        '''
        tests True logging started.
        '''
        result = boto_cloudtrail.start_logging(Name=trail_ret['Name'], **conn_parameters)

        self.assertTrue(result['started'])

    def test_that_when_start_logging_fails_the_start_logging_method_returns_false(self):
        '''
        tests False logging not started.
        '''
        self.conn.describe_trails.return_value = {'trailList': []}
        self.conn.start_logging.side_effect = ClientError(error_content, 'start_logging')
        result = boto_cloudtrail.start_logging(Name=trail_ret['Name'], **conn_parameters)
        self.assertFalse(result['started'])

    def test_that_when_stopping_logging_succeeds_the_stop_logging_method_returns_true(self):
        '''
        tests True logging stopped.
        '''
        result = boto_cloudtrail.stop_logging(Name=trail_ret['Name'], **conn_parameters)

        self.assertTrue(result['stopped'])

    def test_that_when_stop_logging_fails_the_stop_logging_method_returns_false(self):
        '''
        tests False logging not stopped.
        '''
        self.conn.describe_trails.return_value = {'trailList': []}
        self.conn.stop_logging.side_effect = ClientError(error_content, 'stop_logging')
        result = boto_cloudtrail.stop_logging(Name=trail_ret['Name'], **conn_parameters)
        self.assertFalse(result['stopped'])

    def test_that_when_adding_tags_succeeds_the_add_tags_method_returns_true(self):
        '''
        tests True tags added.
        '''
        with patch.dict(boto_cloudtrail.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_cloudtrail.add_tags(Name=trail_ret['Name'], a='b', **conn_parameters)

        self.assertTrue(result['tagged'])

    def test_that_when_adding_tags_fails_the_add_tags_method_returns_false(self):
        '''
        tests False tags not added.
        '''
        self.conn.add_tags.side_effect = ClientError(error_content, 'add_tags')
        with patch.dict(boto_cloudtrail.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_cloudtrail.add_tags(Name=trail_ret['Name'], a='b', **conn_parameters)
        self.assertFalse(result['tagged'])

    def test_that_when_removing_tags_succeeds_the_remove_tags_method_returns_true(self):
        '''
        tests True tags removed.
        '''
        with patch.dict(boto_cloudtrail.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_cloudtrail.remove_tags(Name=trail_ret['Name'], a='b', **conn_parameters)

        self.assertTrue(result['tagged'])

    def test_that_when_removing_tags_fails_the_remove_tags_method_returns_false(self):
        '''
        tests False tags not removed.
        '''
        self.conn.remove_tags.side_effect = ClientError(error_content, 'remove_tags')
        with patch.dict(boto_cloudtrail.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_cloudtrail.remove_tags(Name=trail_ret['Name'], a='b', **conn_parameters)
        self.assertFalse(result['tagged'])

    def test_that_when_listing_tags_succeeds_the_list_tags_method_returns_true(self):
        '''
        tests True tags listed.
        '''
        with patch.dict(boto_cloudtrail.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_cloudtrail.list_tags(Name=trail_ret['Name'], **conn_parameters)

        self.assertEqual(result['tags'], {})

    def test_that_when_listing_tags_fails_the_list_tags_method_returns_false(self):
        '''
        tests False tags not listed.
        '''
        self.conn.list_tags.side_effect = ClientError(error_content, 'list_tags')
        with patch.dict(boto_cloudtrail.__salt__, {'boto_iam.get_account_id': MagicMock(return_value='1234')}):
            result = boto_cloudtrail.list_tags(Name=trail_ret['Name'], **conn_parameters)
        self.assertTrue(result['error'])

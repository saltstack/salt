# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import random
import string
import logging
from copy import deepcopy

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
import salt.loader
from salt.modules import boto_s3_bucket
from salt.utils.versions import LooseVersion

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# pylint: disable=import-error,no-name-in-module,unused-import
try:
    import boto
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module,unused-import

# the boto_s3_bucket module relies on the connect_to_region() method
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
    e404_error = ClientError({
        'Error': {
            'Code': '404',
            'Message': "Test-defined error"
        }
    }, 'msg')
    not_found_error = ClientError({
        'Error': {
            'Code': 'NoSuchBucket',
            'Message': "Test-defined error"
        }
    }, 'msg')
    error_content = {
      'Error': {
        'Code': 101,
        'Message': "Test-defined error"
      }
    }
    create_ret = {
        'Location': 'nowhere',
    }
    list_ret = {
        'Buckets': [{
            'Name': 'mybucket',
            'CreationDate': None
        }],
        'Owner': {
            'DisplayName': 'testuser',
            'ID': '12341234123'
        },
        'ResponseMetadata': {'Key': 'Value'}
    }
    config_ret = {
        'get_bucket_acl': {
            'Grants': [{
                'Grantee': {
                    'DisplayName': 'testowner',
                    'ID': 'sdfghjklqwertyuiopzxcvbnm'
                },
                'Permission': 'FULL_CONTROL'
            }, {
                'Grantee': {
                    'URI': 'http://acs.amazonaws.com/groups/global/AllUsers'
                },
                'Permission': 'READ'
            }],
            'Owner': {
                'DisplayName': 'testowner',
                'ID': 'sdfghjklqwertyuiopzxcvbnm'
            }
        },
        'get_bucket_cors': {
            'CORSRules': [{
                'AllowedMethods': ["GET"],
                'AllowedOrigins': ["*"],
            }]
        },
        'get_bucket_lifecycle_configuration': {
            'Rules': [{
                'Expiration': {
                    'Days': 1
                },
                'Prefix': 'prefix',
                'Status': 'Enabled',
                'ID': 'asdfghjklpoiuytrewq'
            }]
        },
        'get_bucket_location': {
            'LocationConstraint': 'EU'
        },
        'get_bucket_logging': {
            'LoggingEnabled': {
                'TargetBucket': 'my-bucket',
                'TargetPrefix': 'prefix'
            }
        },
        'get_bucket_notification_configuration': {
            'LambdaFunctionConfigurations': [{
                'LambdaFunctionArn': 'arn:aws:lambda:us-east-1:111111222222:function:my-function',
                'Id': 'zxcvbnmlkjhgfdsa',
                'Events': ["s3:ObjectCreated:*"],
                'Filter': {
                    'Key': {
                        'FilterRules': [{
                            'Name': 'prefix',
                            'Value': 'string'
                        }]
                    }
                }
            }]
        },
        'get_bucket_policy': {
            'Policy':
                '{"Version":"2012-10-17","Statement":[{"Sid":"","Effect":"Allow","Principal":{"AWS":"arn:aws:iam::111111222222:root"},"Action":"s3:PutObject","Resource":"arn:aws:s3:::my-bucket/*"}]}'
        },
        'get_bucket_replication': {
            'ReplicationConfiguration': {
                'Role': 'arn:aws:iam::11111222222:my-role',
                'Rules': [{
                    'ID': "r1",
                    'Prefix': "prefix",
                    'Status': "Enabled",
                    'Destination': {
                        'Bucket': "arn:aws:s3:::my-bucket"
                    }
                }]
            }
        },
        'get_bucket_request_payment': {'Payer': 'Requester'},
        'get_bucket_tagging': {
            'TagSet': [{
                'Key': 'c',
                'Value': 'd'
            }, {
                'Key': 'a',
                'Value': 'b',
            }]
        },
        'get_bucket_versioning': {
            'Status': 'Enabled'
        },
        'get_bucket_website': {
            'ErrorDocument': {
                'Key': 'error.html'
            },
            'IndexDocument': {
                'Suffix': 'index.html'
            }
        }
    }


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoS3BucketTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    loader_module = boto_s3_bucket

    def loader_module_globals(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS
        utils = salt.loader.utils(opts, whitelist=['boto3'], context={})
        return {
            '__utils__': utils,
        }

    def setUp(self):
        super(BotoS3BucketTestCaseBase, self).setUp()
        boto_s3_bucket.__init__(self.opts)
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


class BotoS3BucketTestCaseMixin(object):
    pass


class BotoS3BucketTestCase(BotoS3BucketTestCaseBase, BotoS3BucketTestCaseMixin):
    '''
    TestCase for salt.modules.boto_s3_bucket module
    '''

    def test_that_when_checking_if_a_bucket_exists_and_a_bucket_exists_the_bucket_exists_method_returns_true(self):
        '''
        Tests checking s3 bucket existence when the s3 bucket already exists
        '''
        self.conn.head_bucket.return_value = None
        result = boto_s3_bucket.exists(Bucket='mybucket', **conn_parameters)

        self.assertTrue(result['exists'])

    def test_that_when_checking_if_a_bucket_exists_and_a_bucket_does_not_exist_the_bucket_exists_method_returns_false(self):
        '''
        Tests checking s3 bucket existence when the s3 bucket does not exist
        '''
        self.conn.head_bucket.side_effect = e404_error
        result = boto_s3_bucket.exists(Bucket='mybucket', **conn_parameters)

        self.assertFalse(result['exists'])

    def test_that_when_checking_if_a_bucket_exists_and_boto3_returns_an_error_the_bucket_exists_method_returns_error(self):
        '''
        Tests checking s3 bucket existence when boto returns an error
        '''
        self.conn.head_bucket.side_effect = ClientError(error_content, 'head_bucket')
        result = boto_s3_bucket.exists(Bucket='mybucket', **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'), error_message.format('head_bucket'))

    def test_that_when_creating_a_bucket_succeeds_the_create_bucket_method_returns_true(self):
        '''
        tests True bucket created.
        '''
        self.conn.create_bucket.return_value = create_ret
        result = boto_s3_bucket.create(Bucket='mybucket',
                                       LocationConstraint='nowhere',
                                        **conn_parameters)

        self.assertTrue(result['created'])

    def test_that_when_creating_a_bucket_fails_the_create_bucket_method_returns_error(self):
        '''
        tests False bucket not created.
        '''
        self.conn.create_bucket.side_effect = ClientError(error_content, 'create_bucket')
        result = boto_s3_bucket.create(Bucket='mybucket',
                                       LocationConstraint='nowhere',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('create_bucket'))

    def test_that_when_deleting_a_bucket_succeeds_the_delete_bucket_method_returns_true(self):
        '''
        tests True bucket deleted.
        '''
        result = boto_s3_bucket.delete(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_a_bucket_fails_the_delete_bucket_method_returns_false(self):
        '''
        tests False bucket not deleted.
        '''
        self.conn.delete_bucket.side_effect = ClientError(error_content, 'delete_bucket')
        result = boto_s3_bucket.delete(Bucket='mybucket',
                                        **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_describing_bucket_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if bucket exists
        '''
        for key, value in six.iteritems(config_ret):
            getattr(self.conn, key).return_value = deepcopy(value)

        result = boto_s3_bucket.describe(Bucket='mybucket', **conn_parameters)

        self.assertTrue(result['bucket'])

    def test_that_when_describing_bucket_it_returns_the_dict_of_properties_returns_false(self):
        '''
        Tests describing parameters if bucket does not exist
        '''
        self.conn.get_bucket_acl.side_effect = not_found_error
        result = boto_s3_bucket.describe(Bucket='mybucket', **conn_parameters)

        self.assertFalse(result['bucket'])

    def test_that_when_describing_bucket_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.get_bucket_acl.side_effect = ClientError(error_content, 'get_bucket_acl')
        result = boto_s3_bucket.describe(Bucket='mybucket', **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_listing_buckets_succeeds_the_list_buckets_method_returns_true(self):
        '''
        tests True buckets listed.
        '''
        self.conn.list_buckets.return_value = deepcopy(list_ret)
        result = boto_s3_bucket.list(**conn_parameters)

        self.assertTrue(result['Buckets'])

    def test_that_when_listing_bucket_fails_the_list_bucket_method_returns_false(self):
        '''
        tests False no bucket listed.
        '''
        ret = deepcopy(list_ret)
        log.info(ret)
        ret['Buckets'] = list()
        self.conn.list_buckets.return_value = ret
        result = boto_s3_bucket.list(**conn_parameters)
        self.assertFalse(result['Buckets'])

    def test_that_when_listing_bucket_fails_the_list_bucket_method_returns_error(self):
        '''
        tests False bucket error.
        '''
        self.conn.list_buckets.side_effect = ClientError(error_content, 'list_buckets')
        result = boto_s3_bucket.list(**conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('list_buckets'))

    def test_that_when_putting_acl_succeeds_the_put_acl_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_acl(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_acl_fails_the_put_acl_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_acl.side_effect = ClientError(error_content,
                       'put_bucket_acl')
        result = boto_s3_bucket.put_acl(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_acl'))

    def test_that_when_putting_cors_succeeds_the_put_cors_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_cors(Bucket='mybucket', CORSRules='[]',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_cors_fails_the_put_cors_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_cors.side_effect = ClientError(error_content,
                       'put_bucket_cors')
        result = boto_s3_bucket.put_cors(Bucket='mybucket', CORSRules='[]',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_cors'))

    def test_that_when_putting_lifecycle_configuration_succeeds_the_put_lifecycle_configuration_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_lifecycle_configuration(Bucket='mybucket',
                                        Rules='[]',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_lifecycle_configuration_fails_the_put_lifecycle_configuration_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_lifecycle_configuration.side_effect = ClientError(error_content,
                       'put_bucket_lifecycle_configuration')
        result = boto_s3_bucket.put_lifecycle_configuration(Bucket='mybucket',
                                        Rules='[]',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_lifecycle_configuration'))

    def test_that_when_putting_logging_succeeds_the_put_logging_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_logging(Bucket='mybucket',
                                        TargetBucket='arn:::::',
                                        TargetPrefix='asdf',
                                        TargetGrants='[]',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_logging_fails_the_put_logging_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_logging.side_effect = ClientError(error_content,
                       'put_bucket_logging')
        result = boto_s3_bucket.put_logging(Bucket='mybucket',
                                        TargetBucket='arn:::::',
                                        TargetPrefix='asdf',
                                        TargetGrants='[]',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_logging'))

    def test_that_when_putting_notification_configuration_succeeds_the_put_notification_configuration_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_notification_configuration(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_notification_configuration_fails_the_put_notification_configuration_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_notification_configuration.side_effect = ClientError(error_content,
                       'put_bucket_notification_configuration')
        result = boto_s3_bucket.put_notification_configuration(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_notification_configuration'))

    def test_that_when_putting_policy_succeeds_the_put_policy_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_policy(Bucket='mybucket',
                                        Policy='{}',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_policy_fails_the_put_policy_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_policy.side_effect = ClientError(error_content,
                       'put_bucket_policy')
        result = boto_s3_bucket.put_policy(Bucket='mybucket',
                                        Policy='{}',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_policy'))

    def test_that_when_putting_replication_succeeds_the_put_replication_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_replication(Bucket='mybucket',
                                        Role='arn:aws:iam:::',
                                        Rules='[]',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_replication_fails_the_put_replication_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_replication.side_effect = ClientError(error_content,
                       'put_bucket_replication')
        result = boto_s3_bucket.put_replication(Bucket='mybucket',
                                        Role='arn:aws:iam:::',
                                        Rules='[]',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_replication'))

    def test_that_when_putting_request_payment_succeeds_the_put_request_payment_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_request_payment(Bucket='mybucket',
                                        Payer='Requester',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_request_payment_fails_the_put_request_payment_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_request_payment.side_effect = ClientError(error_content,
                       'put_bucket_request_payment')
        result = boto_s3_bucket.put_request_payment(Bucket='mybucket',
                                        Payer='Requester',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_request_payment'))

    def test_that_when_putting_tagging_succeeds_the_put_tagging_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_tagging(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_tagging_fails_the_put_tagging_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_tagging.side_effect = ClientError(error_content,
                       'put_bucket_tagging')
        result = boto_s3_bucket.put_tagging(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_tagging'))

    def test_that_when_putting_versioning_succeeds_the_put_versioning_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_versioning(Bucket='mybucket',
                                        Status='Enabled',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_versioning_fails_the_put_versioning_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_versioning.side_effect = ClientError(error_content,
                       'put_bucket_versioning')
        result = boto_s3_bucket.put_versioning(Bucket='mybucket',
                                        Status='Enabled',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_versioning'))

    def test_that_when_putting_website_succeeds_the_put_website_method_returns_true(self):
        '''
        tests True bucket updated.
        '''
        result = boto_s3_bucket.put_website(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['updated'])

    def test_that_when_putting_website_fails_the_put_website_method_returns_error(self):
        '''
        tests False bucket not updated.
        '''
        self.conn.put_bucket_website.side_effect = ClientError(error_content,
                       'put_bucket_website')
        result = boto_s3_bucket.put_website(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('put_bucket_website'))

    def test_that_when_deleting_cors_succeeds_the_delete_cors_method_returns_true(self):
        '''
        tests True bucket attribute deleted.
        '''
        result = boto_s3_bucket.delete_cors(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_cors_fails_the_delete_cors_method_returns_error(self):
        '''
        tests False bucket attribute not deleted.
        '''
        self.conn.delete_bucket_cors.side_effect = ClientError(error_content,
                       'delete_bucket_cors')
        result = boto_s3_bucket.delete_cors(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('delete_bucket_cors'))

    def test_that_when_deleting_lifecycle_configuration_succeeds_the_delete_lifecycle_configuration_method_returns_true(self):
        '''
        tests True bucket attribute deleted.
        '''
        result = boto_s3_bucket.delete_lifecycle_configuration(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_lifecycle_configuration_fails_the_delete_lifecycle_configuration_method_returns_error(self):
        '''
        tests False bucket attribute not deleted.
        '''
        self.conn.delete_bucket_lifecycle.side_effect = ClientError(error_content,
                       'delete_bucket_lifecycle_configuration')
        result = boto_s3_bucket.delete_lifecycle_configuration(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('delete_bucket_lifecycle_configuration'))

    def test_that_when_deleting_policy_succeeds_the_delete_policy_method_returns_true(self):
        '''
        tests True bucket attribute deleted.
        '''
        result = boto_s3_bucket.delete_policy(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_policy_fails_the_delete_policy_method_returns_error(self):
        '''
        tests False bucket attribute not deleted.
        '''
        self.conn.delete_bucket_policy.side_effect = ClientError(error_content,
                       'delete_bucket_policy')
        result = boto_s3_bucket.delete_policy(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('delete_bucket_policy'))

    def test_that_when_deleting_replication_succeeds_the_delete_replication_method_returns_true(self):
        '''
        tests True bucket attribute deleted.
        '''
        result = boto_s3_bucket.delete_replication(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_replication_fails_the_delete_replication_method_returns_error(self):
        '''
        tests False bucket attribute not deleted.
        '''
        self.conn.delete_bucket_replication.side_effect = ClientError(error_content,
                       'delete_bucket_replication')
        result = boto_s3_bucket.delete_replication(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('delete_bucket_replication'))

    def test_that_when_deleting_tagging_succeeds_the_delete_tagging_method_returns_true(self):
        '''
        tests True bucket attribute deleted.
        '''
        result = boto_s3_bucket.delete_tagging(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_tagging_fails_the_delete_tagging_method_returns_error(self):
        '''
        tests False bucket attribute not deleted.
        '''
        self.conn.delete_bucket_tagging.side_effect = ClientError(error_content,
                       'delete_bucket_tagging')
        result = boto_s3_bucket.delete_tagging(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('delete_bucket_tagging'))

    def test_that_when_deleting_website_succeeds_the_delete_website_method_returns_true(self):
        '''
        tests True bucket attribute deleted.
        '''
        result = boto_s3_bucket.delete_website(Bucket='mybucket',
                                        **conn_parameters)

        self.assertTrue(result['deleted'])

    def test_that_when_deleting_website_fails_the_delete_website_method_returns_error(self):
        '''
        tests False bucket attribute not deleted.
        '''
        self.conn.delete_bucket_website.side_effect = ClientError(error_content,
                       'delete_bucket_website')
        result = boto_s3_bucket.delete_website(Bucket='mybucket',
                                        **conn_parameters)
        self.assertEqual(result.get('error', {}).get('message'),
                        error_message.format('delete_bucket_website'))

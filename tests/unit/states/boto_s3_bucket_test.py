# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module
from copy import deepcopy
import random
import string

# Import Salt Testing libs
from salttesting.unit import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
import salt.config
import salt.loader

# Import 3rd-party libs
import logging

# Import Mock libraries
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# pylint: disable=import-error,no-name-in-module,unused-import
from unit.modules.boto_s3_bucket_test import BotoS3BucketTestCaseMixin

# Import 3rd-party libs
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

opts = salt.config.DEFAULT_MINION_OPTS
context = {}
utils = salt.loader.utils(opts, whitelist=['boto3'], context=context)
serializers = salt.loader.serializers(opts)
funcs = salt.loader.minion_mods(opts, context=context, utils=utils, whitelist=['boto_s3_bucket'])
salt_states = salt.loader.states(opts=opts, functions=funcs, utils=utils, whitelist=['boto_s3_bucket'], serializers=serializers)


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
            'Code': '404',
            'Message': "Test-defined error"
        }
    }, 'msg')
    error_content = {
      'Error': {
        'Code': 101,
        'Message': "Test-defined error"
      }
    }
    list_ret = {
        'Buckets': [{
            'Name': 'mybucket',
            'CreationDate': None
        }],
        'Owner': {
            'DisplayName': 'testuser',
            'ID': '111111222222'
        },
        'ResponseMetadata': {'Key': 'Value'}
    }
    config_in = {
        'LocationConstraint': 'EU',
        'ACL': {
            'ACL': 'public-read'
        },
        'CORSRules': [{
            'AllowedMethods': ["GET"],
            'AllowedOrigins': ["*"],
        }],
        'LifecycleConfiguration': [{
            'Expiration': {
                'Days': 1
            },
            'Prefix': 'prefix',
            'Status': 'Enabled',
            'ID': 'asdfghjklpoiuytrewq'
        }],
        'Logging': {
            'TargetBucket': 'my-bucket',
            'TargetPrefix': 'prefix'
        },
        'NotificationConfiguration': {
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
        'Policy': {
            'Version': "2012-10-17",
            'Statement': [{
                'Sid': "",
                'Effect': "Allow",
                'Principal': {
                    'AWS': "arn:aws:iam::111111222222:root"
                },
                'Action': "s3:PutObject",
                'Resource': "arn:aws:s3:::my-bucket/*"
            }]
        },
        'Replication': {
            'Role': 'arn:aws:iam::11111222222:my-role',
            'Rules': [{
                'ID': "r1",
                'Prefix': "prefix",
                'Status': "Enabled",
                'Destination': {
                    'Bucket': "arn:aws:s3:::my-bucket"
                }
            }]
        },
        'RequestPayment': {
            'Payer': 'Requester'
        },
        'Tagging': {
            'a': 'b',
            'c': 'd'
        },
        'Versioning': {
            'Status': 'Enabled'
        },
        'Website': {
            'ErrorDocument': {
                'Key': 'error.html'
            },
            'IndexDocument': {
                'Suffix': 'index.html'
            }
        }
    }
    config_ret = {
        'get_bucket_acl': {
            'Grants': [{
                'Grantee': {
                    'Type': 'Group',
                    'URI': 'http://acs.amazonaws.com/groups/global/AllUsers'
                },
                'Permission': 'READ'
            }],
            'Owner': {
                'DisplayName': 'testuser',
                'ID': '111111222222'
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
    bucket_ret = {
        'Location': 'EU'
    }


class BotoS3BucketStateTestCaseBase(TestCase):
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
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoS3BucketTestCase(BotoS3BucketStateTestCaseBase, BotoS3BucketTestCaseMixin):
    '''
    TestCase for salt.modules.boto_s3_bucket state.module
    '''

    def test_present_when_bucket_does_not_exist(self):
        '''
        Tests present on a bucket that does not exist.
        '''
        self.conn.head_bucket.side_effect = [not_found_error, None]
        self.conn.list_buckets.return_value = deepcopy(list_ret)
        self.conn.create_bucket.return_value = bucket_ret
        for key, value in config_ret.iteritems():
            getattr(self.conn, key).return_value = deepcopy(value)
        with patch.dict(funcs, {'boto_iam.get_account_id': MagicMock(return_value='111111222222')}):
            result = salt_states['boto_s3_bucket.present'](
                         'bucket present',
                         Bucket='testbucket',
                         **config_in
                     )

        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['bucket']['Location'], config_ret['get_bucket_location'])

    def test_present_when_bucket_exists_no_mods(self):
        self.conn.list_buckets.return_value = deepcopy(list_ret)
        for key, value in config_ret.iteritems():
            getattr(self.conn, key).return_value = deepcopy(value)
        with patch.dict(funcs, {'boto_iam.get_account_id': MagicMock(return_value='111111222222')}):
            result = salt_states['boto_s3_bucket.present'](
                         'bucket present',
                         Bucket='testbucket',
                         **config_in
                     )

        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_present_when_bucket_exists_all_mods(self):
        self.conn.list_buckets.return_value = deepcopy(list_ret)
        for key, value in config_ret.iteritems():
            getattr(self.conn, key).return_value = deepcopy(value)
        with patch.dict(funcs, {'boto_iam.get_account_id': MagicMock(return_value='111111222222')}):
            result = salt_states['boto_s3_bucket.present'](
                         'bucket present',
                         Bucket='testbucket',
                         LocationConstraint=config_in['LocationConstraint']
                     )

        self.assertTrue(result['result'])
        self.assertNotEqual(result['changes'], {})

    def test_present_with_failure(self):
        self.conn.head_bucket.side_effect = [not_found_error, None]
        self.conn.list_buckets.return_value = deepcopy(list_ret)
        self.conn.create_bucket.side_effect = ClientError(error_content, 'create_bucket')
        with patch.dict(funcs, {'boto_iam.get_account_id': MagicMock(return_value='111111222222')}):
            result = salt_states['boto_s3_bucket.present'](
                         'bucket present',
                         Bucket='testbucket',
                         **config_in
                     )
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])

    def test_absent_when_bucket_does_not_exist(self):
        '''
        Tests absent on a bucket that does not exist.
        '''
        self.conn.head_bucket.side_effect = [not_found_error, None]
        result = salt_states['boto_s3_bucket.absent']('test', 'mybucket')
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_absent_when_bucket_exists(self):
        result = salt_states['boto_s3_bucket.absent']('test', 'testbucket')
        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['bucket'], None)

    def test_absent_with_failure(self):
        self.conn.delete_bucket.side_effect = ClientError(error_content, 'delete_bucket')
        result = salt_states['boto_s3_bucket.absent']('test', 'testbucket')
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])

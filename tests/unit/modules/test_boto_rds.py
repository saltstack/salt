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
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
import salt.loader
import salt.modules.boto_rds as boto_rds
from salt.utils.versions import LooseVersion

# Import 3rd-party libs
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

required_boto3_version = '1.3.1'

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
            'Code': 'DBClusterNotFound',
            'Message': "Test-defined error"
        }
    }, 'msg')
    error_content = ClientError({
      'Error': {
        'Code': 101,
        'Message': "Test-defined error"
      }
    }, 'msg')


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoRdsTestCaseBase(TestCase, LoaderModuleMockMixin):
    '''
    Base class for boto_rds testcases
    '''
    conn = None

    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS
        utils = salt.loader.utils(opts, whitelist=['boto3'], context={})
        return {boto_rds: {'__utils__': utils}}

    def setUp(self):
        super(BotoRdsTestCaseBase, self).setUp()
        boto_rds.__init__(self.opts)
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
        self.name = 'my-db-cluster'
        self.engine = 'MySQL'
        self.master_username = 'sqlusr'
        self.master_user_password = 'sqlpassw'


class BotoRdsTestCaseMixin(object):
    '''
    Class BotoRdsTestCaseMixin
    '''
    pass


class BotoRdsTestCase(BotoRdsTestCaseBase, BotoRdsTestCaseMixin):
    '''
    TestCase for salt.modules.boto_rds module
    '''

    def test_db_cluster_exists_when_describe_db_clusters_returns_false(self):
        '''
        Tests checking db cluster existence when the db cluster already exists
        '''
        self.conn.describe_db_clusters.return_value = None
        result = boto_rds.db_cluster_exists(name='mydbcluster', **conn_parameters)

        self.assertFalse(result['exists'])

    def test_db_cluster_exists_when_describe_db_clusters_raises_not_found(self):
        '''
        Tests checking db cluster existence with an exception not found raised
        '''
        self.conn.describe_db_clusters.side_effect = not_found_error
        result = boto_rds.db_cluster_exists(name='mydbcluster', **conn_parameters)

        self.assertFalse(result['exists'])

    def test_db_cluster_exists_when_describe_db_clusters_raises_an_error(self):
        '''
        Tests checking db cluster existence with an exception raised
        '''
        self.conn.describe_db_clusters.side_effect = error_content
        result = boto_rds.db_cluster_exists(name='mydbcluster', **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'), error_message.format('msg'))

    def test_create_cluster_db_when_db_cluster_exists_returns_exists(self):
        '''
        Tests create cluster db when db_cluster_exists returns exists
        '''
        mock_exists = MagicMock(return_value={'exists': True})
        with patch.dict(boto_rds.__salt__, {
            'boto_rds.db_cluster_exists': mock_exists,
        }):
            self.assertDictEqual(
                boto_rds.create_db_cluster(
                    self.name,
                    self.engine,
                    self.master_username,
                    self.master_user_password,
                ),
                {
                    'exists': True,
                },
            )

    def test_create_cluster_db_failed(self):
        '''
        Tests create cluster db when it fails
        '''
        mock_exists = MagicMock(return_value={'exists': False})
        with patch.dict(boto_rds.__salt__, {
            'boto_rds.db_cluster_exists': mock_exists,
        }):
            self.conn.create_db_cluster.return_value = None
            self.assertDictEqual(
                boto_rds.create_db_cluster(
                    self.name,
                    self.engine,
                    self.master_username,
                    self.master_user_password,
                ),
                {
                    'created': False,
                    'message': 'Failed to create RDS db cluster {0}'.format(self.name),
                },
            )

    def test_create_cluster_db_return_true(self):
        '''
        Tests create cluster db when it succeeds
        '''
        mock_exists = MagicMock(return_value={'exists': False})
        with patch.dict(boto_rds.__salt__, {
            'boto_rds.db_cluster_exists': mock_exists,
        }):
            self.conn.create_db_cluster.return_value = {'results': True}
            self.assertDictEqual(
                boto_rds.create_db_cluster(
                    self.name,
                    self.engine,
                    self.master_username,
                    self.master_user_password,
                ),
                {
                    'exists': True,
                    'message': 'Created RDS db cluster {0}'.format(self.name),
                },
            )

    def test_create_cluster_db_returns_error(self):
        '''
        Tests create cluster db when it raises an exception
        '''
        mock_exists = MagicMock(return_value={'exists': False})
        with patch.dict(boto_rds.__salt__, {
            'boto_rds.db_cluster_exists': mock_exists,
        }):
            self.conn.create_db_cluster.side_effect = error_content
            result = boto_rds.create_db_cluster(
                self.name,
                self.engine,
                self.master_username,
                self.master_user_password,
            )
            self.assertEqual(result.get('error', {}).get('message'), error_message.format('msg'))

# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import random
import string

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch

# Import Salt libs
from salt.ext import six
import salt.loader
from salt.utils.versions import LooseVersion
import salt.states.boto_elasticsearch_domain as boto_elasticsearch_domain

# Import test suite libs

# pylint: disable=import-error,no-name-in-module,unused-import
from tests.unit.modules.test_boto_elasticsearch_domain import BotoElasticsearchDomainTestCaseMixin

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
try:
    import boto
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

# pylint: enable=import-error,no-name-in-module,unused-import

# the boto_elasticsearch_domain module relies on the connect_to_region() method
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
            'Code': 'ResourceNotFoundException',
            'Message': "Test-defined error"
        }
    }, 'msg')
    error_content = {
      'Error': {
        'Code': 101,
        'Message': "Test-defined error"
      }
    }
    domain_ret = dict(DomainName='testdomain',
                  ElasticsearchClusterConfig={},
                  EBSOptions={},
                  AccessPolicies={},
                  SnapshotOptions={},
                  AdvancedOptions={},
                  ElasticsearchVersion='1.5',
                  )


class BotoElasticsearchDomainStateTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    def setup_loader_modules(self):
        ctx = {}
        utils = salt.loader.utils(self.opts, whitelist=['boto3'], context=ctx)
        serializers = salt.loader.serializers(self.opts)
        self.funcs = funcs = salt.loader.minion_mods(self.opts, context=ctx, utils=utils, whitelist=['boto_elasticsearch_domain'])
        self.salt_states = salt.loader.states(opts=self.opts, functions=funcs, utils=utils, whitelist=['boto_elasticsearch_domain'],
                                              serializers=serializers)
        return {
            boto_elasticsearch_domain: {
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

    # Set up MagicMock to replace the boto3 session
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


@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoElasticsearchDomainTestCase(BotoElasticsearchDomainStateTestCaseBase, BotoElasticsearchDomainTestCaseMixin):
    '''
    TestCase for salt.modules.boto_elasticsearch_domain state.module
    '''

    def test_present_when_domain_does_not_exist(self):
        '''
        Tests present on a domain that does not exist.
        '''
        self.conn.describe_elasticsearch_domain.side_effect = not_found_error
        self.conn.describe_elasticsearch_domain_config.return_value = {'DomainConfig': domain_ret}
        self.conn.create_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        result = self.salt_states['boto_elasticsearch_domain.present'](
                         'domain present',
                         **domain_ret)

        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['domain']['ElasticsearchClusterConfig'], None)

    def test_present_when_domain_exists(self):
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        cfg = {}
        for k, v in six.iteritems(domain_ret):
            cfg[k] = {'Options': v}
        cfg['AccessPolicies'] = {'Options': '{"a": "b"}'}
        self.conn.describe_elasticsearch_domain_config.return_value = {'DomainConfig': cfg}
        self.conn.update_elasticsearch_domain_config.return_value = {'DomainConfig': cfg}
        result = self.salt_states['boto_elasticsearch_domain.present'](
                         'domain present',
                         **domain_ret)
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {'new': {'AccessPolicies': {}}, 'old': {'AccessPolicies': {'a': 'b'}}})

    def test_present_with_failure(self):
        self.conn.describe_elasticsearch_domain.side_effect = not_found_error
        self.conn.describe_elasticsearch_domain_config.return_value = {'DomainConfig': domain_ret}
        self.conn.create_elasticsearch_domain.side_effect = ClientError(error_content, 'create_domain')
        result = self.salt_states['boto_elasticsearch_domain.present'](
                         'domain present',
                         **domain_ret)
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])

    def test_absent_when_domain_does_not_exist(self):
        '''
        Tests absent on a domain that does not exist.
        '''
        self.conn.describe_elasticsearch_domain.side_effect = not_found_error
        result = self.salt_states['boto_elasticsearch_domain.absent']('test', 'mydomain')
        self.assertTrue(result['result'])
        self.assertEqual(result['changes'], {})

    def test_absent_when_domain_exists(self):
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        self.conn.describe_elasticsearch_domain_config.return_value = {'DomainConfig': domain_ret}
        result = self.salt_states['boto_elasticsearch_domain.absent']('test', domain_ret['DomainName'])
        self.assertTrue(result['result'])
        self.assertEqual(result['changes']['new']['domain'], None)

    def test_absent_with_failure(self):
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        self.conn.describe_elasticsearch_domain_config.return_value = {'DomainConfig': domain_ret}
        self.conn.delete_elasticsearch_domain.side_effect = ClientError(error_content, 'delete_domain')
        result = self.salt_states['boto_elasticsearch_domain.absent']('test', domain_ret['DomainName'])
        self.assertFalse(result['result'])
        self.assertTrue('An error occurred' in result['comment'])

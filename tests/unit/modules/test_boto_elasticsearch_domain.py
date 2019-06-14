# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import logging
import random
import string

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt libs
from salt.ext import six
import salt.loader
from salt.utils.versions import LooseVersion
import salt.modules.boto_elasticsearch_domain as boto_elasticsearch_domain

# Import 3rd-party libs

# pylint: disable=import-error,no-name-in-module
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

from salt.ext.six.moves import range

# pylint: enable=import-error,no-name-in-module

# the boto_elasticsearch_domain module relies on the connect_to_region() method
# which was added in boto 2.8.0
# https://github.com/boto/boto/commit/33ac26b416fbb48a60602542b4ce15dcc7029f12
required_boto3_version = '1.2.1'


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
    error_content = {
      'Error': {
        'Code': 101,
        'Message': "Test-defined error"
      }
    }
    not_found_error = ClientError({
        'Error': {
            'Code': 'ResourceNotFoundException',
            'Message': "Test-defined error"
        }
    }, 'msg')
    domain_ret = dict(DomainName='testdomain',
                      ElasticsearchClusterConfig={},
                      EBSOptions={},
                      AccessPolicies={},
                      SnapshotOptions={},
                      AdvancedOptions={})

log = logging.getLogger(__name__)


class BotoElasticsearchDomainTestCaseBase(TestCase, LoaderModuleMockMixin):
    conn = None

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            self.opts,
            whitelist=['boto3', 'args', 'systemd', 'path', 'platform'],
            context={})
        return {boto_elasticsearch_domain: {'__utils__': utils}}

    def setUp(self):
        super(BotoElasticsearchDomainTestCaseBase, self).setUp()
        boto_elasticsearch_domain.__init__(self.opts)
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


class BotoElasticsearchDomainTestCaseMixin(object):
    pass


@skipIf(True, 'Skip these tests while investigating failures')
@skipIf(HAS_BOTO is False, 'The boto module must be installed.')
@skipIf(_has_required_boto() is False, 'The boto3 module must be greater than'
                                       ' or equal to version {0}'
        .format(required_boto3_version))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class BotoElasticsearchDomainTestCase(BotoElasticsearchDomainTestCaseBase, BotoElasticsearchDomainTestCaseMixin):
    '''
    TestCase for salt.modules.boto_elasticsearch_domain module
    '''

    def test_that_when_checking_if_a_domain_exists_and_a_domain_exists_the_domain_exists_method_returns_true(self):
        '''
        Tests checking domain existence when the domain already exists
        '''
        result = boto_elasticsearch_domain.exists(DomainName='testdomain', **conn_parameters)

        self.assertTrue(result['exists'])

    def test_that_when_checking_if_a_domain_exists_and_a_domain_does_not_exist_the_domain_exists_method_returns_false(self):
        '''
        Tests checking domain existence when the domain does not exist
        '''
        self.conn.describe_elasticsearch_domain.side_effect = not_found_error
        result = boto_elasticsearch_domain.exists(DomainName='mydomain', **conn_parameters)

        self.assertFalse(result['exists'])

    def test_that_when_checking_if_a_domain_exists_and_boto3_returns_an_error_the_domain_exists_method_returns_error(self):
        '''
        Tests checking domain existence when boto returns an error
        '''
        self.conn.describe_elasticsearch_domain.side_effect = ClientError(error_content, 'list_domains')
        result = boto_elasticsearch_domain.exists(DomainName='mydomain', **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'), error_message.format('list_domains'))

    def test_that_when_checking_domain_status_and_a_domain_exists_the_domain_status_method_returns_info(self):
        '''
        Tests checking domain existence when the domain already exists
        '''
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        result = boto_elasticsearch_domain.status(DomainName='testdomain', **conn_parameters)

        self.assertTrue(result['domain'])

    def test_that_when_checking_domain_status_and_boto3_returns_an_error_the_domain_status_method_returns_error(self):
        '''
        Tests checking domain existence when boto returns an error
        '''
        self.conn.describe_elasticsearch_domain.side_effect = ClientError(error_content, 'list_domains')
        result = boto_elasticsearch_domain.status(DomainName='mydomain', **conn_parameters)

        self.assertEqual(result.get('error', {}).get('message'), error_message.format('list_domains'))

    def test_that_when_describing_domain_it_returns_the_dict_of_properties_returns_true(self):
        '''
        Tests describing parameters if domain exists
        '''
        domainconfig = {}
        for k, v in six.iteritems(domain_ret):
            if k == 'DomainName':
                continue
            domainconfig[k] = {'Options': v}
        self.conn.describe_elasticsearch_domain_config.return_value = {'DomainConfig': domainconfig}

        result = boto_elasticsearch_domain.describe(DomainName=domain_ret['DomainName'], **conn_parameters)

        log.warning(result)
        desired_ret = copy.copy(domain_ret)
        desired_ret.pop('DomainName')
        self.assertEqual(result, {'domain': desired_ret})

    def test_that_when_describing_domain_on_client_error_it_returns_error(self):
        '''
        Tests describing parameters failure
        '''
        self.conn.describe_elasticsearch_domain_config.side_effect = ClientError(error_content, 'list_domains')
        result = boto_elasticsearch_domain.describe(DomainName='testdomain', **conn_parameters)
        self.assertTrue('error' in result)

    def test_that_when_creating_a_domain_succeeds_the_create_domain_method_returns_true(self):
        '''
        tests True domain created.
        '''
        self.conn.create_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        args = copy.copy(domain_ret)
        args.update(conn_parameters)
        result = boto_elasticsearch_domain.create(**args)

        self.assertTrue(result['created'])

    def test_that_when_creating_a_domain_fails_the_create_domain_method_returns_error(self):
        '''
        tests False domain not created.
        '''
        self.conn.create_elasticsearch_domain.side_effect = ClientError(error_content, 'create_domain')
        args = copy.copy(domain_ret)
        args.update(conn_parameters)
        result = boto_elasticsearch_domain.create(**args)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('create_domain'))

    def test_that_when_deleting_a_domain_succeeds_the_delete_domain_method_returns_true(self):
        '''
        tests True domain deleted.
        '''
        result = boto_elasticsearch_domain.delete(DomainName='testdomain',
                                                    **conn_parameters)
        self.assertTrue(result['deleted'])

    def test_that_when_deleting_a_domain_fails_the_delete_domain_method_returns_false(self):
        '''
        tests False domain not deleted.
        '''
        self.conn.delete_elasticsearch_domain.side_effect = ClientError(error_content, 'delete_domain')
        result = boto_elasticsearch_domain.delete(DomainName='testdomain',
                                                    **conn_parameters)
        self.assertFalse(result['deleted'])

    def test_that_when_updating_a_domain_succeeds_the_update_domain_method_returns_true(self):
        '''
        tests True domain updated.
        '''
        self.conn.update_elasticsearch_domain_config.return_value = {'DomainConfig': domain_ret}
        args = copy.copy(domain_ret)
        args.update(conn_parameters)
        result = boto_elasticsearch_domain.update(**args)

        self.assertTrue(result['updated'])

    def test_that_when_updating_a_domain_fails_the_update_domain_method_returns_error(self):
        '''
        tests False domain not updated.
        '''
        self.conn.update_elasticsearch_domain_config.side_effect = ClientError(error_content, 'update_domain')
        args = copy.copy(domain_ret)
        args.update(conn_parameters)
        result = boto_elasticsearch_domain.update(**args)
        self.assertEqual(result.get('error', {}).get('message'), error_message.format('update_domain'))

    def test_that_when_adding_tags_succeeds_the_add_tags_method_returns_true(self):
        '''
        tests True tags added.
        '''
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        result = boto_elasticsearch_domain.add_tags(DomainName='testdomain', a='b', **conn_parameters)

        self.assertTrue(result['tagged'])

    def test_that_when_adding_tags_fails_the_add_tags_method_returns_false(self):
        '''
        tests False tags not added.
        '''
        self.conn.add_tags.side_effect = ClientError(error_content, 'add_tags')
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        result = boto_elasticsearch_domain.add_tags(DomainName=domain_ret['DomainName'], a='b', **conn_parameters)
        self.assertFalse(result['tagged'])

    def test_that_when_removing_tags_succeeds_the_remove_tags_method_returns_true(self):
        '''
        tests True tags removed.
        '''
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        result = boto_elasticsearch_domain.remove_tags(DomainName=domain_ret['DomainName'], TagKeys=['a'], **conn_parameters)

        self.assertTrue(result['tagged'])

    def test_that_when_removing_tags_fails_the_remove_tags_method_returns_false(self):
        '''
        tests False tags not removed.
        '''
        self.conn.remove_tags.side_effect = ClientError(error_content, 'remove_tags')
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        result = boto_elasticsearch_domain.remove_tags(DomainName=domain_ret['DomainName'], TagKeys=['b'], **conn_parameters)
        self.assertFalse(result['tagged'])

    def test_that_when_listing_tags_succeeds_the_list_tags_method_returns_true(self):
        '''
        tests True tags listed.
        '''
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        result = boto_elasticsearch_domain.list_tags(DomainName=domain_ret['DomainName'], **conn_parameters)

        self.assertEqual(result['tags'], {})

    def test_that_when_listing_tags_fails_the_list_tags_method_returns_false(self):
        '''
        tests False tags not listed.
        '''
        self.conn.list_tags.side_effect = ClientError(error_content, 'list_tags')
        self.conn.describe_elasticsearch_domain.return_value = {'DomainStatus': domain_ret}
        result = boto_elasticsearch_domain.list_tags(DomainName=domain_ret['DomainName'], **conn_parameters)
        self.assertTrue(result['error'])


# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import pkg_resources
import os.path
import sys

# Import Salt Libs
import salt.config
from salt.ext import six
import salt.loader
import salt.modules.boto3_route53 as boto3_route53
import salt.utils.versions

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, NO_MOCK, NO_MOCK_REASON, patch
from tests.support.runtests import RUNTIME_VARS

# import Python Third Party Libs
# pylint: disable=import-error
try:
    import boto
    boto.ENDPOINTS_PATH = os.path.join(RUNTIME_VARS.TESTS_DIR, 'unit/files/endpoints.json')
    from moto import mock_route53_deprecated
    HAS_MOTO = True
except ImportError:
    HAS_MOTO = False

    def mock_route53_deprecated(self):
        '''
        if the mock_route53_deprecated function is not available due to import failure
        this replaces the decorated function with stub_function.
        Allows boto_route53 unit tests to use the @mock_route53_deprecated decorator
        without a "NameError: name 'mock_route53_deprecated' is not defined" error.
        '''
        def stub_function(self):
            pass
        return stub_function
# pylint: enable=import-error

log = logging.getLogger(__name__)

required_moto = '0.3.7'
required_moto_py3 = '1.0.1'


def _has_required_moto():
    '''
    Returns True or False depending on if ``moto`` is installed and at the correct version,
    depending on what version of Python is running these tests.
    '''
    if not HAS_MOTO:
        return False
    else:
        moto_version = salt.utils.versions.LooseVersion(pkg_resources.get_distribution('moto').version)
        if moto_version < salt.utils.versions.LooseVersion(required_moto):
            return False
        elif six.PY3 and moto_version < salt.utils.versions.LooseVersion(required_moto_py3):
            return False

    return True


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(HAS_MOTO is False, 'The moto module must be installed.')
@skipIf(_has_required_moto() is False, 'The moto module must be >= to {0} for '
                                       'PY2 or {1} for PY3.'.format(required_moto, required_moto_py3))
class Boto3Route53TestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.boto_route53 module
    '''
    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        self.opts['route53.keyid'] = 'GKTADJGHEIQSXMKKRBJ08H'
        self.opts['route53.key'] = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
        utils = salt.loader.utils(self.opts)
        funcs = salt.loader.minion_mods(self.opts, utils=utils, whitelist=['boto3_route53', 'config'])
        return {
            boto3_route53: {
                '__opts__': self.opts,
                '__utils__': utils,
                '__salt__': funcs
            },
        }

    def setUp(self):
        TestCase.setUp(self)
        # __virtual__ must be caller in order for _get_conn to be injected
        boto3_route53.__virtual__()
        boto3_route53.__init__(self.opts)

#        self.patcher = patch('boto3.session.Session')
#        self.addCleanup(self.patcher.stop)
#        self.addCleanup(delattr, self, 'patcher')
#        mock_session = self.patcher.start()
#
#        session_instance = mock_session.return_value
#        self.conn = MagicMock()
#        self.addCleanup(delattr, self, 'conn3')
#        session_instance.client.return_value = self.conn

    def tearDown(self):
        del self.opts

    @mock_route53_deprecated
    def test_create_healthcheck(self):
        '''
        tests that given valid healhcheck data creates it.
        '''
        expected = {
            'result': {
                        'HealthCheckConfig': {
                            'FailureThreshold': 3,
                            'IPAddress': '10.0.0.1',
                            'ResourcePath': '/',
                            'RequestInterval': 30,
                            'Type': 'HTTPS',
                            'Port': 443,
                            'FullyQualifiedDomainName': 'blog.saltstack.furniture',
                        },
                        'HealthCheckVersion': 1
            },
        }
        healthcheck = boto3_route53.create_health_check(
            'ANAme',
            IPAddress='10.0.0.1',
            FullyQualifiedDomainName='blog.saltstack.furniture',
            Type='HTTPS',
            Port=443,
            RequestInterval=30,
            FailureThreshold=3,
            ResourcePath='/',
        )
        del healthcheck['result']['CallerReference']
        del healthcheck['result']['Id']
        self.assertEqual(healthcheck, expected)

    @mock_route53_deprecated
    def test_delete_health_check(self):
        '''
        test that deletes an existing health check by id.
        '''
        expected = {'result': True}
        res = boto3_route53.delete_health_check(
            'FAKE-ID'
        )
        self.assertEqual(res, expected)

    @mock_route53_deprecated
    @skipIf(True, 'TODO: moto does not yet implement update_health_check.')
    def test_update_health_check(self):
        '''
        test that updates an existing health check.
        '''
        expected = {}
        res = boto3_route53.update_health_check(
            'FAKE-ID',
            {'IPAddress': '10.0.0.2'}
        )
        self.assertEqual(res, expected)

    @mock_route53_deprecated
    @skipIf(True, 'TODO: moto does not yet implement get_health_check.')
    def test_get_health_check_version(self):
        '''
        test getting a health check's version.
        '''
        expected = 1
        res = boto3_route53.create_health_check(
            'A-Name',
            Type='HTTP',
            Port=443,
            RequestInterval=30,
            FailureThreshold=3
        )
        res = boto3_route53.get_health_check_version(
            res['result']['Id']
        )
        self.assertEqual(res, expected)

    @mock_route53_deprecated
    def test_list_health_checks(self):
        '''
        test listing of health checks.
        '''
        res0 = boto3_route53.create_health_check(
            'HC1',
            Type='HTTP',
            Port=443,
            RequestInterval=30,
            FailureThreshold=3
        )
        res1 = boto3_route53.create_health_check(
            'HC2',
            Type='HTTP',
            Port=443,
            RequestInterval=30,
            FailureThreshold=3
        )
        res = boto3_route53.list_health_checks()
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['Id'], res0['result']['Id'])
        self.assertEqual(res[1]['Id'], res1['result']['Id'])


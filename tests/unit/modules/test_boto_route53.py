
# -*- coding: utf-8 -*-

# import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import pkg_resources
import os.path

# Import Salt Libs
import salt.config
from salt.ext import six
import salt.loader
import salt.modules.boto_route53 as boto_route53
import salt.utils.versions

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON
from tests.support.paths import TESTS_DIR

# import Python Third Party Libs
# pylint: disable=import-error
try:
    import boto
    boto.ENDPOINTS_PATH = os.path.join(TESTS_DIR, 'unit/files/endpoints.json')
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
class BotoRoute53TestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.boto_route53 module
    '''
    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MINION_OPTS
        self.opts['route53.keyid'] = 'GKTADJGHEIQSXMKKRBJ08H'
        self.opts['route53.key'] = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'
        utils = salt.loader.utils(self.opts)
        funcs = salt.loader.minion_mods(self.opts, utils=utils, whitelist=['boto_route53', 'config'])
        return {
            boto_route53: {
                '__opts__': self.opts,
                '__utils__': utils,
                '__salt__': funcs
            },
        }

    def setUp(self):
        TestCase.setUp(self)
        # __virtual__ must be caller in order for _get_conn to be injected
        boto_route53.__virtual__()
        boto_route53.__init__(self.opts)

    def tearDown(self):
        del self.opts

    @mock_route53_deprecated
    def test_create_healthcheck(self):
        '''
        tests that given a valid instance id and valid ELB that
        register_instances returns True.
        '''
        expected = {
            'result': {
                'CreateHealthCheckResponse': {
                    'HealthCheck': {
                        'HealthCheckConfig': {
                            'FailureThreshold': '3',
                            'IPAddress': '10.0.0.1',
                            'ResourcePath': '/',
                            'RequestInterval': '30',
                            'Type': 'HTTPS',
                            'Port': '443',
                            'FullyQualifiedDomainName': 'blog.saltstack.furniture',
                        },
                        'HealthCheckVersion': '1',
                    },
                },
            },
        }
        healthcheck = boto_route53.create_healthcheck(
            '10.0.0.1',
            fqdn='blog.saltstack.furniture',
            hc_type='HTTPS',
            port=443,
            resource_path='/',
        )
        del healthcheck['result']['CreateHealthCheckResponse']['HealthCheck']['CallerReference']
        del healthcheck['result']['CreateHealthCheckResponse']['HealthCheck']['Id']
        self.assertEqual(healthcheck, expected)

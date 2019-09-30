# -*- coding: utf-8 -*-
'''
    :codeauthor: `Tyler Johnson <tjohnson@saltstack.com>`

    tests.unit.cloud.clouds.openstack_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.cloud.clouds import openstack

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch


@skipIf(NO_MOCK, NO_MOCK_REASON)
class OpenstackTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Unit TestCase for salt.cloud.clouds.openstack module.
    '''
    def setup_loader_modules(self):
        return {
            openstack: {
                '__active_provider_name__': '',
                '__opts__': {
                    'providers': {
                        'my-openstack-cloud': {
                            'openstack': {
                                'auth': 'daenerys',
                                'region_name': 'westeros',
                                'cloud': 'openstack',
                            }
                        }
                    }
                }
            }
        }

    def test_get_configured_provider_bad(self):
        with patch.dict(openstack.__opts__, {'providers': {}}):
            result = openstack.get_configured_provider()
            self.assertEqual(result, False)

    def test_get_configured_provider_auth(self):
        config = {
            'region_name': 'westeros',
            'auth': 'daenerys',
        }
        with patch.dict(openstack.__opts__, {'providers': {'my-openstack-cloud': {'openstack': config}}}):
            result = openstack.get_configured_provider()
            self.assertEqual(config, result)

    def test_get_configured_provider_cloud(self):
        config = {
            'region_name': 'westeros',
            'cloud': 'foo',
        }
        with patch.dict(openstack.__opts__, {'providers': {'my-openstack-cloud': {'openstack': config}}}):
            result = openstack.get_configured_provider()
            self.assertEqual(config, result)

    def test_get_dependencies(self):
        HAS_SHADE = (True, 'Please install newer version of shade: >= 1.19.0')
        with patch('salt.cloud.clouds.openstack.HAS_SHADE', HAS_SHADE):
            result = openstack.get_dependencies()
            self.assertEqual(result, True)

    def test_get_dependencies_no_shade(self):
        HAS_SHADE = (False, 'Install pypi module shade >= 1.19.0')
        with patch('salt.cloud.clouds.openstack.HAS_SHADE', HAS_SHADE):
            result = openstack.get_dependencies()
            self.assertEqual(result, False)


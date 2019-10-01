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


class MockImage(object):
    name = 'image name'
    id = 'image id'


class MockNode(object):
    name = 'node name'
    id = 'node id'
    flavor = MockImage()
    status = 'node status'

    def __init__(self, image):
        self.image = image

    def __iter__(self):
        return iter(())


class MockConn(object):
    def __init__(self, image):
        self.node = MockNode(image)

    def get_image(self, *args, **kwargs):
        return self.node.image

    def get_flavor(self, *args, **kwargs):
        return self.node.flavor

    def get_server(self, *args, **kwargs):
        return self.node

    def list_servers(self, *args, **kwargs):
        return [self.node]


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

    def test_list_nodes_full_image_str(self):
        node_image = 'node image'
        conn = MockConn(node_image)
        with patch('salt.cloud.clouds.openstack._get_ips', return_value=[]):
            ret = openstack.list_nodes_full(conn=conn)
            self.assertEqual(ret[conn.node.name]['image'], node_image)

    def test_list_nodes_full_image_obj(self):
        conn = MockConn(MockImage())
        with patch('salt.cloud.clouds.openstack._get_ips', return_value=[]):
            ret = openstack.list_nodes_full(conn=conn)
            self.assertEqual(ret[conn.node.name]['image'], MockImage.name)

    def test_show_instance(self):
        conn = MockConn(MockImage())
        with patch('salt.cloud.clouds.openstack._get_ips', return_value=[]):
            ret = openstack.show_instance(conn.node.name, conn=conn, call='action')
            self.assertEqual(ret['image'], MockImage.name)

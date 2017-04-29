# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)
import salt.modules.libcloud_compute as libcloud_compute

from libcloud.compute.base import BaseDriver, Node, NodeSize, NodeState, NodeLocation


class MockComputeDriver(BaseDriver):
    def __init__(self):
        self._TEST_SIZE = NodeSize(id='test_id', name='test_size',
            ram=4096, disk=10240, bandwidth=100000, price=0,
            driver=self)
        self._TEST_NODE = Node(id='test_id', name='test_node',
            state=NodeState.RUNNING, public_ips=['1.2.3.4'],
            private_ips=['2.3.4.5'], driver=self,
            size=self._TEST_SIZE, extra={
                'ex_key': 'ex_value'
            })
        self._TEST_LOCATION = NodeLocation(id='test_location',
            name='location1', country='Australia', driver=self)
    
    def list_nodes(self):
        return [self._TEST_NODE]

    def list_sizes(self, location=None):
        if location:
            assert location.id == 'test_location'
        return [self._TEST_SIZE]

    def list_locations(self):
        return [self._TEST_LOCATION]

    def reboot_node(self, node):
        assert node.id == 'test_id'
        return True

    def destroy_node(self, node):
        assert node.id == 'test_id'
        return True


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.libcloud_compute._get_driver',
       MagicMock(return_value=MockComputeDriver()))
class LibcloudComputeModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        module_globals = {
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                })
            }
        }
        if libcloud_compute.HAS_LIBCLOUD is False:
            module_globals['sys.modules'] = {'libcloud': MagicMock()}

        return {libcloud_compute: module_globals}

    def test_module_creation(self):
        client = libcloud_compute._get_driver('test')
        self.assertFalse(client is None)

    def test_init(self):
        with patch('salt.utils.compat.pack_dunder', return_value=False) as dunder:
            libcloud_compute.__init__(None)
            dunder.assert_called_with('salt.modules.libcloud_compute')

    def _validate_node(self, node):
        self.assertEqual(node['name'], 'test_node')
        self.assertEqual(node['id'], 'test_id')
        self.assertEqual(node['private_ips'], ['2.3.4.5'])
        self.assertEqual(node['public_ips'], ['1.2.3.4'])
        self.assertEqual(node['size']['name'], 'test_size')

    def _validate_size(self, size):
        self.assertEqual(size['id'], 'test_id')
        self.assertEqual(size['name'], 'test_size')
        self.assertEqual(size['ram'], 4096)

    def _validate_location(self, location):
        self.assertEqual(location['id'], 'test_location')
        self.assertEqual(location['name'], 'location1')
        self.assertEqual(location['country'], 'Australia')

    def test_list_nodes(self):
        nodes = libcloud_compute.list_nodes('test')
        self.assertEqual(len(nodes), 1)
        self._validate_node(nodes[0])

    def test_list_sizes(self):
        sizes = libcloud_compute.list_sizes('test')
        self.assertEqual(len(sizes), 1)
        self._validate_size(sizes[0])

    def test_list_sizes_location(self):
        sizes = libcloud_compute.list_sizes('test', location_id='test_location')
        self.assertEqual(len(sizes), 1)
        self._validate_size(sizes[0])

    def test_list_locations(self):
        locations = libcloud_compute.list_locations('test')
        self.assertEqual(len(locations), 1)
        self._validate_location(locations[0])

    def test_reboot_node(self):
        result = libcloud_compute.reboot_node('test_id', 'test')
        self.assertTrue(result)

    def test_reboot_node_invalid(self):
        with self.assertRaises(ValueError):
            libcloud_compute.reboot_node('foo_node', 'test')

    def test_destroy_node(self):
        result = libcloud_compute.destroy_node('test_id', 'test')
        self.assertTrue(result)

    def test_destroy_node_invalid(self):
        with self.assertRaises(ValueError):
            libcloud_compute.destroy_node('foo_node', 'test')

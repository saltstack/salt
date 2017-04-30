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

from libcloud.compute.base import (BaseDriver, Node, 
    NodeSize, NodeState, NodeLocation, 
    StorageVolume, StorageVolumeState,
    VolumeSnapshot, NodeImage)


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
        self._TEST_LOCATION = NodeLocation(
            id='test_location',
            name='location1',
            country='Australia',
            driver=self)
        self._TEST_VOLUME = StorageVolume(
            id='vol1',
            name='vol_name',
            size=40960,
            driver=self,
            state=StorageVolumeState.AVAILABLE,
            extra={
                'ex_key': 'ex_value'
            }
        )
        self._TEST_VOLUME_SNAPSHOT = VolumeSnapshot(
            id='snap1',
            name='snap_name',
            size=80960,
            driver=self
        )
        self._TEST_IMAGE = NodeImage(
            id='image1',
            name='test_image',
            extra={
                'ex_key': 'ex_value'
            },
            driver=self
        )

    
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

    def list_volumes(self):
        return [self._TEST_VOLUME]

    def list_volume_snapshots(self, volume):
        assert volume.id == 'vol1'
        return [self._TEST_VOLUME_SNAPSHOT]

    def create_volume(self, size, name, location=None, snapshot=None):
        assert size == 9000
        assert name == 'test_new_volume'
        if location:
            assert location.country == 'Australia'
        return self._TEST_VOLUME

    def create_volume_snapshot(self, volume, name=None):
        assert volume.id == 'vol1'
        if name:
            assert name == 'test_snapshot'
        return self._TEST_VOLUME_SNAPSHOT

    def attach_volume(self, node, volume, device=None):
        assert node.id == 'test_id'
        assert volume.id == 'vol1'
        if device:
            assert device == '/dev/sdc'
        return True

    def detach_volume(self, volume):
        assert volume.id  == 'vol1'
        return True

    def destroy_volume(self, volume):
        assert volume.id == 'vol1'
        return True

    def destroy_volume_snapshot(self, snapshot):
        assert snapshot.id == 'snap1'
        return True

    def list_images(self, location=None):
        if location:
            assert location.id == 'test_location'
        return [self._TEST_IMAGE]


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

    def _validate_volume(self, volume):
        self.assertEqual(volume['id'], 'vol1')
        self.assertEqual(volume['name'], 'vol_name')
        self.assertEqual(volume['size'], 40960)
        self.assertEqual(volume['state'], 'available')
        self.assertEqual(volume['extra'], {'ex_key': 'ex_value'})

    def _validate_volume_snapshot(self, volume):
        self.assertEqual(volume['id'], 'snap1')
        self.assertEqual(volume['name'], 'snap_name')
        self.assertEqual(volume['size'], 80960)

    def _validate_image(self, image):
        self.assertEqual(image['id'], 'image1')
        self.assertEqual(image['name'], 'test_image')
        self.assertEqual(image['extra'], {'ex_key': 'ex_value'})

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

    def test_list_volumes(self):
        volumes = libcloud_compute.list_volumes('test')
        self.assertEqual(len(volumes), 1)
        self._validate_volume(volumes[0])

    def test_list_volume_snapshots(self):
        volumes = libcloud_compute.list_volume_snapshots('vol1', 'test')
        self.assertEqual(len(volumes), 1)
        self._validate_volume_snapshot(volumes[0])

    def test_create_volume(self):
        volume = libcloud_compute.create_volume(9000, 'test_new_volume', 'test')
        self._validate_volume(volume)
    
    def test_create_volume_in_location(self):
        volume = libcloud_compute.create_volume(9000, 'test_new_volume', 'test', location_id='test_location')
        self._validate_volume(volume)

    def test_create_volume_snapshot(self):
        snapshot = libcloud_compute.create_volume_snapshot('vol1', 'test')
        self._validate_volume_snapshot(snapshot)

    def test_create_volume_snapshot_named(self):
        snapshot = libcloud_compute.create_volume_snapshot('vol1', 'test', name='test_snapshot')
        self._validate_volume_snapshot(snapshot)

    def test_attach_volume(self):
        result = libcloud_compute.attach_volume('test_id', 'vol1', 'test')
        self.assertTrue(result)

    def test_detatch_volume(self):
        result = libcloud_compute.detach_volume('vol1', 'test')
        self.assertTrue(result)

    def test_destroy_volume(self):
        result = libcloud_compute.destroy_volume('vol1', 'test')
        self.assertTrue(result)

    def test_destroy_volume_snapshot(self):
        result = libcloud_compute.destroy_volume_snapshot('vol1', 'snap1', 'test')
        self.assertTrue(result)

    def test_list_images(self):
        images = libcloud_compute.list_images('test')
        self.assertEqual(len(images), 1)
        self._validate_image(images[0])

    def test_list_images_in_location(self):
        images = libcloud_compute.list_images('test', location_id='test_location')
        self.assertEqual(len(images), 1)
        self._validate_image(images[0])

# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import logging

from salt.utils.versions import LooseVersion as _LooseVersion

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
)
import salt.modules.libcloud_compute as libcloud_compute

REQUIRED_LIBCLOUD_VERSION = '2.0.0'
try:
    import libcloud
    from libcloud.compute.base import (
        BaseDriver, Node,
        NodeSize, NodeState, NodeLocation,
        StorageVolume, StorageVolumeState,
        VolumeSnapshot, NodeImage, KeyPair)
    if hasattr(libcloud, '__version__') and _LooseVersion(libcloud.__version__) < _LooseVersion(REQUIRED_LIBCLOUD_VERSION):
        raise ImportError()
    logging.getLogger('libcloud').setLevel(logging.CRITICAL)
    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False


if HAS_LIBCLOUD:
    class MockComputeDriver(BaseDriver):
        def __init__(self):  # pylint: disable=W0231
            self._TEST_SIZE = NodeSize(
                id='test_id', name='test_size',
                ram=4096, disk=10240, bandwidth=100000, price=0,
                driver=self)
            self._TEST_NODE = Node(
                id='test_id', name='test_node',
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
            self._TEST_KEY_PAIR = KeyPair(
                name='test_key',
                fingerprint='abc123',
                public_key='pub123',
                private_key='priv123',
                driver=self,
                extra={
                    'ex_key': 'ex_value'
                }
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
            assert volume.id == 'vol1'
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

        def create_image(self, node, name, description=None):
            assert node.id == 'test_id'
            return self._TEST_IMAGE

        def delete_image(self, node_image):
            return True

        def get_image(self, image_id):
            assert image_id == 'image1'
            return self._TEST_IMAGE

        def copy_image(self, source_region, node_image, name, description=None):
            assert source_region == 'us-east1'
            assert node_image.id == 'image1'
            assert name == 'copy_test'
            return self._TEST_IMAGE

        def list_key_pairs(self):
            return [self._TEST_KEY_PAIR]

        def get_key_pair(self, name):
            assert name == 'test_key'
            return self._TEST_KEY_PAIR

        def create_key_pair(self, name):
            assert name == 'test_key'
            return self._TEST_KEY_PAIR

        def import_key_pair_from_string(self, name, key_material):
            assert name == 'test_key'
            assert key_material == 'test_key_value'
            return self._TEST_KEY_PAIR

        def import_key_pair_from_file(self, name, key_file_path):
            assert name == 'test_key'
            assert key_file_path == '/path/to/key'
            return self._TEST_KEY_PAIR

        def delete_key_pair(self, key_pair):
            assert key_pair.name == 'test_key'
            return True


else:
    MockComputeDriver = object


@skipIf(not HAS_LIBCLOUD, 'No libcloud installed')
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
        self.assertEqual(volume['size'], 80960)

    def _validate_image(self, image):
        self.assertEqual(image['id'], 'image1')
        self.assertEqual(image['name'], 'test_image')
        self.assertEqual(image['extra'], {'ex_key': 'ex_value'})

    def _validate_key_pair(self, key):
        self.assertEqual(key['name'], 'test_key')
        self.assertEqual(key['fingerprint'], 'abc123')
        self.assertEqual(key['extra'], {'ex_key': 'ex_value'})

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

    def test_create_image(self):
        image = libcloud_compute.create_image('test_id', 'new_image', 'test')
        self._validate_image(image)

    def test_delete_image(self):
        result = libcloud_compute.delete_image('image1', 'test')
        self.assertTrue(result)

    def test_get_image(self):
        image = libcloud_compute.get_image('image1', 'test')
        self._validate_image(image)

    def test_copy_image(self):
        new_image = libcloud_compute.copy_image('us-east1', 'image1', 'copy_test', 'test')
        self._validate_image(new_image)

    def test_list_key_pairs(self):
        keys = libcloud_compute.list_key_pairs('test')
        self.assertEqual(len(keys), 1)
        self._validate_key_pair(keys[0])

    def test_get_key_pair(self):
        key = libcloud_compute.get_key_pair('test_key', 'test')
        self._validate_key_pair(key)

    def test_create_key_pair(self):
        key = libcloud_compute.create_key_pair('test_key', 'test')
        self._validate_key_pair(key)

    def test_import_key_string(self):
        key = libcloud_compute.import_key_pair('test_key', 'test_key_value', 'test')
        self._validate_key_pair(key)

    def test_import_key_file(self):
        key = libcloud_compute.import_key_pair('test_key', '/path/to/key', 'test', key_type='FILE')
        self._validate_key_pair(key)

    def test_delete_key_pair(self):
        result = libcloud_compute.delete_key_pair('test_key', 'test')
        self.assertTrue(result)

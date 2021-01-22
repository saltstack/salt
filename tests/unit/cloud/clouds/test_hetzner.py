"""
    :codeauthor: Florian Kantelberg <florian.kantelberg@initos.com>
"""

from salt.cloud.clouds import hetzner
from salt.exceptions import SaltCloudException, SaltCloudSystemExit
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

KEY = "abcdefgh"

VM_NAME = "myserver"
IMAGES = {"ubuntu-20.04": {"name": "ubuntu-20.04", "id": 15512617}}
LOCATIONS = {"fsn1": {"city": "Falkenstein", "name": "fsn1", "id": 1}}
SIZES = {"cpx21": {"name": "cpx21", "cores": 3, "id": 32}}
SSH_KEYS = {"myssh": {"name": "myssh"}}
VM = {
    "name": VM_NAME,
    "driver": "hetzner",
    "size": "cpx21",
    "image": "ubuntu-20.04",
}


class ModelMock(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = MagicMock()
        self.model.__slots__ = list(self)

        for attr, value in self.items():
            setattr(self, attr, value)


class HetznerTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.cloud.clouds.hetzner
    """

    LOCAL_OPTS = {
        "providers": {"hetzner1": {"hetzner": {"driver": "hetzner", "key": KEY}}},
        "profiles": {},
        "sock_dir": "/var/sockxxx",
        "transport": "tcp",
        "update_cachedir": True,
    }

    def setup_loader_modules(self):
        return {
            hetzner: {
                "__active_provider_name__": "",
                "__utils__": {
                    "cloud.bootstrap": MagicMock(),
                    "cloud.cache_node": MagicMock(),
                    "cloud.delete_minion_cachedir": MagicMock(),
                    "cloud.filter_event": MagicMock(),
                    "cloud.fire_event": MagicMock(),
                },
                "__opts__": self.LOCAL_OPTS,
            },
        }

    @patch("salt.cloud.clouds.hetzner.get_configured_provider")
    @patch("salt.cloud.clouds.hetzner.get_dependencies")
    def test_virtual(self, dependency, config):
        config.return_value = False
        dependency.return_value = False
        self.assertFalse(hetzner.__virtual__())

        config.return_value = True
        self.assertFalse(hetzner.__virtual__())

        dependency.return_value = True
        self.assertEqual(hetzner.__virtual__(), hetzner.__virtualname__)

    def test_object_to_dict(self):
        mock = MagicMock()
        mock.attr1 = "abc"
        mock.attr2 = "def"

        self.assertEqual(
            hetzner._object_to_dict(mock, ["attr1", "attr2"]),
            {"attr1": "abc", "attr2": "def"},
        )

    def test_dependencies(self):
        with patch("salt.cloud.clouds.hetzner.HAS_HCLOUD", True):
            self.assertTrue(hetzner.get_dependencies())
        with patch("salt.cloud.clouds.hetzner.HAS_HCLOUD", False):
            self.assertFalse(hetzner.get_dependencies())

    @skipIf(not hetzner.HAS_HCLOUD, "Install hcloud to be able to run this test.")
    def test_connect_client(self):
        with patch("salt.cloud.clouds.hetzner.hcloud"):
            hetzner._connect_client()
            hetzner.hcloud.Client.assert_called_once_with(KEY)

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    def test_avail_images_action(self, connect):
        self.assertRaises(SaltCloudSystemExit, hetzner.avail_images, "action")

        connect.return_value.images.get_all.return_value = map(
            ModelMock, IMAGES.values()
        )
        self.assertEqual(hetzner.avail_images(), IMAGES)

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    def test_avail_locations(self, connect):
        self.assertRaises(SaltCloudSystemExit, hetzner.avail_locations, "action")

        connect.return_value.locations.get_all.return_value = map(
            ModelMock, LOCATIONS.values()
        )
        self.assertEqual(hetzner.avail_locations(), LOCATIONS)

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    def test_avail_sizes(self, connect):
        self.assertRaises(SaltCloudSystemExit, hetzner.avail_sizes, "action")

        connect.return_value.server_types.get_all.return_value = map(
            ModelMock, SIZES.values()
        )
        self.assertEqual(hetzner.avail_sizes(), SIZES)

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    def test_list_ssh_keys(self, connect):
        self.assertRaises(SaltCloudSystemExit, hetzner.list_ssh_keys, "action")

        connect.return_value.ssh_keys.get_all.return_value = map(
            ModelMock, SSH_KEYS.values()
        )
        self.assertEqual(hetzner.list_ssh_keys(), SSH_KEYS)

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    def test_list_nodes_full(self, connect):
        """ Test the list_nodes_full function by using a mock """
        self.assertRaises(SaltCloudSystemExit, hetzner.list_nodes_full, "action")

        mock = MagicMock()
        mock.id = 123456
        mock.name = "abc"
        mock.public_net.ipv4.ip = "127.0.0.1/32"
        mock.public_net.ipv6.ip = "::1/64"
        mock.private_net = []
        mock.labels = "abc"
        connect.return_value.servers.get_all.return_value = [mock]

        nodes = hetzner.list_nodes_full()
        self.assertEqual(nodes[mock.name]["id"], mock.id)
        # Labels shouldn't be filtered
        self.assertIn("labels", nodes[mock.name])

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    def test_list_nodes(self, connect):
        """ Test the list_nodes function by using a mock """
        self.assertRaises(SaltCloudSystemExit, hetzner.list_nodes, "action")

        mock = MagicMock()
        mock.id = 123456
        mock.name = "abc"
        mock.public_net.ipv4.ip = "127.0.0.1/32"
        mock.public_net.ipv6.ip = "::1/64"
        mock.private_net = []
        mock.labels = "abc"
        connect.return_value.servers.get_all.return_value = [mock]

        nodes = hetzner.list_nodes()
        self.assertEqual(nodes[mock.name]["id"], mock.id)
        # Labels should be filtered
        self.assertNotIn("labels", nodes[mock.name])

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    def test_show_instance(self, connect):
        """ Test the show_instance function by using a mock """
        self.assertRaises(SaltCloudSystemExit, hetzner.show_instance, VM_NAME, "action")

        mock = MagicMock()
        mock.id = 123456
        mock.name = "abc"
        mock.public_net.ipv4.ip = "127.0.0.1/32"
        mock.public_net.ipv6.ip = "::1/64"
        mock.private_net = []
        mock.labels = "abc"
        connect.return_value.servers.get_all.return_value = [mock]

        nodes = hetzner.show_instance(mock.name)
        self.assertEqual(nodes["id"], mock.id)

        nodes = hetzner.show_instance("not-existing")
        self.assertEqual(nodes, {})

    @patch("salt.cloud.clouds.hetzner.show_instance")
    def test_wait_until(self, show_instance):
        """ Test the wait_until function """

        show_instance.side_effect = [{"state": "done"}, IndexError()]
        self.assertTrue(hetzner.wait_until("abc", "done"))

        show_instance.side_effect = [{"state": "done"}, IndexError()]
        self.assertRaises(IndexError, hetzner.wait_until, "abc", "never")

        show_instance.side_effect = [{"state": "done"}, IndexError()]
        self.assertFalse(hetzner.wait_until("abc", "never", timeout=0))

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    def test_create(self, wait, connect):
        """ Test the overall creation and the required parameters """
        self.assertRaises(SaltCloudException, hetzner.create, {})

        connect.return_value.server_types.get_by_name.return_value = None
        connect.return_value.images.get_by_name.return_value = None
        self.assertRaises(SaltCloudException, hetzner.create, VM)

        connect.return_value.server_types.get_by_name.return_value = ModelMock(
            SIZES["cpx21"]
        )
        self.assertRaises(SaltCloudException, hetzner.create, VM)

        connect.return_value.images.get_by_name.return_value = ModelMock(
            IMAGES["ubuntu-20.04"]
        )

        self.assertTrue(hetzner.create(VM)["created"])
        connect.return_value.servers.create.assert_called_once()
        args = connect.return_value.servers.create.call_args
        self.assertEqual(args.kwargs["name"], VM["name"])
        self.assertEqual(args.kwargs["server_type"], SIZES["cpx21"])
        self.assertEqual(args.kwargs["image"], IMAGES["ubuntu-20.04"])

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    def test_create_location(self, wait, connect):
        """ Test the locations during the creation """
        vm = VM.copy()
        vm["location"] = "abc"

        hetzner.create(vm)
        connect.return_value.servers.create.assert_called_once()
        connect.return_value.locations.get_by_name.assert_called_once_with("abc")

        # The location should be passed to the create
        connect.return_value.locations.get_by_name.return_value = "abc"
        hetzner.create(vm)

        args = connect.return_value.servers.create.call_args
        self.assertEqual(args.kwargs["location"], "abc")

        # Stop if the location is invalid
        connect.return_value.locations.get_by_name.return_value = None
        self.assertRaises(SaltCloudException, hetzner.create, vm)

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    def test_ssh_keys(self, wait, connect):
        """ Test the locations during the creation """
        vm = VM.copy()
        vm["ssh_keys"] = ["me"]
        hetzner.create(vm)
        connect.return_value.ssh_keys.get_by_name.assert_called_once_with("me")

        # The ssh_keys should be passed to the create
        connect.return_value.ssh_keys.get_by_name.return_value = "me"
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        self.assertEqual(args.kwargs["ssh_keys"], ["me"])

        # Invalid keys should be sorted out
        connect.return_value.ssh_keys.get_by_name.return_value = None
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        self.assertEqual(args.kwargs["ssh_keys"], [])

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    def test_create_datacenter(self, wait, connect):
        """ Test the datacenters during the creation """
        vm = VM.copy()
        vm["datacenter"] = "abc"

        hetzner.create(vm)
        connect.return_value.servers.create.assert_called_once()
        connect.return_value.datacenters.get_by_name.assert_called_once_with("abc")

        # The datacenter should be passed to the create
        connect.return_value.datacenters.get_by_name.return_value = "abc"
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        self.assertEqual(args.kwargs["datacenter"], "abc")

        # Stop if the datacenter is invalid
        connect.return_value.datacenters.get_by_name.return_value = None
        self.assertRaises(SaltCloudException, hetzner.create, vm)

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    def test_create_volumes(self, wait, connect):
        """ Test the volumes during the creation """
        vm = VM.copy()
        vm["volumes"] = ["a", "b"]
        connect.return_value.volumes.get_all.return_value = ["a", "c"]

        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        self.assertEqual(args.kwargs["volumes"], ["a"])

        vm["volumes"] = ["a", "b", "c"]
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        self.assertEqual(args.kwargs["volumes"], ["a", "c"])

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    def test_create_networks(self, wait, connect):
        """ Test the networks during the creation """
        vm = VM.copy()
        vm["networks"] = ["a", "b"]
        connect.return_value.networks.get_all.return_value = ["a", "c"]

        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        self.assertEqual(args.kwargs["networks"], ["a"])

        vm["networks"] = ["a", "b", "c"]
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        self.assertEqual(args.kwargs["networks"], ["a", "c"])

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    def test_start(self, wait, connect):
        """ Test the start action """
        self.assertRaises(SaltCloudSystemExit, hetzner.start, VM_NAME, "function")

        connect.return_value.servers.get_by_name.return_value = None
        hetzner.start(VM_NAME, "action")

        server = connect.return_value.servers.get_by_name.return_value = MagicMock()

        self.assertIn("Started", hetzner.start(VM_NAME, "action"))
        server.power_on.assert_called_once()

        wait.return_value = False
        hetzner.start(VM_NAME, "action")

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    def test_stop(self, wait, connect):
        """ Test the stop action """
        self.assertRaises(SaltCloudSystemExit, hetzner.stop, VM_NAME, "function")

        connect.return_value.servers.get_by_name.return_value = None
        hetzner.stop(VM_NAME, "action")

        server = connect.return_value.servers.get_by_name.return_value = MagicMock()

        self.assertIn("Stopped", hetzner.stop(VM_NAME, "action"))
        server.power_off.assert_called_once()

        wait.return_value = False
        hetzner.stop(VM_NAME, "action")

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    def test_reboot(self, wait, connect):
        """ Test the reboot action """
        self.assertRaises(SaltCloudSystemExit, hetzner.reboot, VM_NAME, "function")

        connect.return_value.servers.get_by_name.return_value = None
        hetzner.reboot(VM_NAME, "action")

        server = connect.return_value.servers.get_by_name.return_value = MagicMock()

        self.assertIn("Rebooted", hetzner.reboot(VM_NAME, "action"))
        server.reboot.assert_called_once()

        wait.return_value = False
        hetzner.reboot(VM_NAME, "action")

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    @patch("salt.cloud.clouds.hetzner.show_instance")
    def test_destroy(self, show_instance, wait, connect):
        """ Test the destroy action """
        self.assertRaises(SaltCloudSystemExit, hetzner.destroy, VM_NAME, "function")

        wait.return_value = False
        show_instance.return_value = {"state": "running"}
        connect.return_value.servers.get_by_name.return_value = None
        hetzner.destroy(VM_NAME, "action")

        server = connect.return_value.servers.get_by_name.return_value = MagicMock()

        # Stop the server before shutdown but failed
        hetzner.destroy(VM_NAME, "action")
        server.delete.assert_not_called()
        wait.assert_called_once_with(VM_NAME, "off")

        wait.return_value = True
        hetzner.destroy(VM_NAME, "action")
        server.delete.assert_called_once()

        # Don't stop if the server isn't running
        show_instance.return_value = {"state": "off"}
        wait.reset_mock()
        hetzner.destroy(VM_NAME, "action")
        wait.assert_not_called()

    @patch("salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock())
    @patch("salt.cloud.clouds.hetzner.wait_until", return_value=True)
    @patch("salt.cloud.clouds.hetzner.show_instance")
    def test_resize(self, show_instance, wait, connect):
        """ Test the resize action """
        kwargs = {"size": "cpx21"}
        self.assertRaises(
            SaltCloudSystemExit, hetzner.resize, VM_NAME, kwargs, "function",
        )

        wait.return_value = False
        show_instance.return_value = {"state": "running"}
        connect.return_value.server_types.get_by_name = MagicMock(return_value=None)
        connect.return_value.servers.get_by_name.return_value = None

        hetzner.resize(VM_NAME, kwargs, "action")

        server = connect.return_value.servers.get_by_name.return_value = MagicMock()

        # Invalid server size
        self.assertRaises(SaltCloudException, hetzner.resize, VM_NAME, {}, "action")
        self.assertRaises(SaltCloudException, hetzner.resize, VM_NAME, kwargs, "action")

        connect.return_value.server_types.get_by_name.return_value = True

        # Stop the server before shutdown but failed
        hetzner.resize(VM_NAME, kwargs, "action")
        server.change_type.assert_not_called()
        wait.assert_called_once_with(VM_NAME, "off")

        wait.return_value = True
        hetzner.resize(VM_NAME, kwargs, "action")
        server.change_type.assert_called_once()

        # Don't stop if the server isn't running
        show_instance.return_value = {"state": "off"}
        wait.reset_mock()
        hetzner.resize(VM_NAME, kwargs, "action")
        wait.assert_not_called()

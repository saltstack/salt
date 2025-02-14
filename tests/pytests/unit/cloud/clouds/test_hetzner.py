"""
    :codeauthor: Florian Kantelberg <florian.kantelberg@initos.com>
"""

import pytest

from salt.cloud.clouds import hetzner
from salt.exceptions import SaltCloudException, SaltCloudSystemExit
from tests.support.mock import MagicMock, patch


class ModelMock(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = MagicMock()
        self.model.__slots__ = list(self)

        for attr, value in self.items():
            setattr(self, attr, value)


@pytest.fixture
def configure_loader_modules():
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
            "__opts__": {
                "providers": {
                    "hetzner1": {"hetzner": {"driver": "hetzner", "key": "abcdefg"}},
                },
                "profiles": {},
                "sock_dir": "/var/sockxxx",
                "transport": "tcp",
                "update_cachedir": True,
            },
        },
    }


@pytest.fixture
def images():
    return {"ubuntu-20.04": {"name": "ubuntu-20.04", "id": 15512617}}


@pytest.fixture
def locations():
    return {"fsn1": {"city": "Falkenstein", "name": "fsn1", "id": 1}}


@pytest.fixture
def sizes():
    return {"cpx21": {"name": "cpx21", "cores": 3, "id": 32}}


@pytest.fixture
def ssh_keys():
    return {"myssh": {"name": "myssh"}}


@pytest.fixture
def vm():
    return {
        "name": "myvm",
        "driver": "hetzner",
        "size": "cpx21",
        "image": "ubuntu-20.04",
    }


def test_virtual():
    with patch("salt.cloud.clouds.hetzner.get_configured_provider") as config:
        with patch("salt.cloud.clouds.hetzner.get_dependencies") as dependency:
            config.return_value = False
            dependency.return_value = False
            assert not hetzner.__virtual__()

            config.return_value = True
            assert not hetzner.__virtual__()

            dependency.return_value = True
            assert hetzner.__virtual__() == hetzner.__virtualname__


def test_object_to_dict():
    mock = MagicMock()
    mock.attr1 = "abc"
    mock.attr2 = "def"

    assert hetzner._object_to_dict(mock, ["attr1", "attr2"]) == {
        "attr1": "abc",
        "attr2": "def",
    }


def test_dependencies():
    with patch("salt.cloud.clouds.hetzner.HAS_HCLOUD", True):
        assert hetzner.get_dependencies()
    with patch("salt.cloud.clouds.hetzner.HAS_HCLOUD", False):
        assert not hetzner.get_dependencies()


@pytest.mark.skipif(
    not hetzner.HAS_HCLOUD, reason="Install hcloud to be able to run this test."
)
def test_connect_client():
    with patch("salt.cloud.clouds.hetzner.hcloud"):
        hetzner._connect_client()
        hetzner.hcloud.Client.assert_called_once_with("abcdefgh")


def test_avail_images_action(images):
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with pytest.raises(SaltCloudSystemExit):
            hetzner.avail_images("action")

        connect.return_value.images.get_all.return_value = map(
            ModelMock, images.values()
        )
        assert hetzner.avail_images() == images


def test_avail_locations(locations):
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with pytest.raises(SaltCloudSystemExit):
            hetzner.avail_locations("action")

        connect.return_value.locations.get_all.return_value = map(
            ModelMock, locations.values()
        )
        assert hetzner.avail_locations() == locations


def test_avail_sizes(sizes):
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with pytest.raises(SaltCloudSystemExit):
            hetzner.avail_sizes("action")

        connect.return_value.server_types.get_all.return_value = map(
            ModelMock, sizes.values()
        )
        assert hetzner.avail_sizes() == sizes


def test_list_ssh_keys(ssh_keys):
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with pytest.raises(SaltCloudSystemExit):
            hetzner.list_ssh_keys("action")

        connect.return_value.ssh_keys.get_all.return_value = map(
            ModelMock, ssh_keys.values()
        )
        assert hetzner.list_ssh_keys() == ssh_keys


def test_list_nodes_full():
    """Test the list_nodes_full function by using a mock"""
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with pytest.raises(SaltCloudSystemExit):
            hetzner.list_nodes_full("action")

        mock = MagicMock()
        mock.id = 123456
        mock.name = "abc"
        mock.public_net.ipv4.ip = "127.0.0.1/32"
        mock.public_net.ipv6.ip = "::1/64"

        private_net_mock = MagicMock()
        private_net_mock.ip = "10.0.0.1/16"
        mock.private_net = []
        mock.private_net.append(private_net_mock)

        mock.labels = "abc"
        connect.return_value.servers.get_all.return_value = [mock]

        nodes = hetzner.list_nodes_full()
        assert nodes[mock.name]["id"], mock.id
        # Labels shouldn't be filtered
        assert "labels" in nodes[mock.name]

        assert nodes[mock.name]["public_ips"]["ipv4"] == "127.0.0.1/32"
        assert nodes[mock.name]["public_ips"]["ipv6"] == "::1/64"

        assert nodes[mock.name]["private_ips"][0]["ip"] == "10.0.0.1/16"


def test_list_nodes():
    """Test the list_nodes function by using a mock"""
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with pytest.raises(SaltCloudSystemExit):
            hetzner.list_nodes("action")

        mock = MagicMock()
        mock.id = 123456
        mock.name = "abc"
        mock.public_net.ipv4.ip = "127.0.0.1/32"
        mock.public_net.ipv6.ip = "::1/64"

        private_net_mock = MagicMock()
        private_net_mock.ip = "10.0.0.1/16"
        mock.private_net = []
        mock.private_net.append(private_net_mock)

        mock.labels = "abc"
        connect.return_value.servers.get_all.return_value = [mock]

        nodes = hetzner.list_nodes()
        assert nodes[mock.name]["id"], mock.id
        # Labels should be filtered
        assert "labels" not in nodes[mock.name]

        assert nodes[mock.name]["public_ips"]["ipv4"] == "127.0.0.1/32"
        assert nodes[mock.name]["public_ips"]["ipv6"] == "::1/64"

        assert nodes[mock.name]["private_ips"][0]["ip"] == "10.0.0.1/16"


def test_show_instance():
    """Test the show_instance function by using a mock"""
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with pytest.raises(SaltCloudSystemExit):
            hetzner.show_instance("myvm")

        mock = MagicMock()
        mock.id = 123456
        mock.name = "abc"
        mock.public_net.ipv4.ip = "127.0.0.1/32"
        mock.public_net.ipv6.ip = "::1/64"
        mock.private_net = []
        mock.labels = "abc"
        connect.return_value.servers.get_all.return_value = [mock]

        nodes = hetzner.show_instance(mock.name, "action")
        assert nodes["id"] == mock.id

        nodes = hetzner.show_instance("not-existing", "action")
        assert nodes == {}


def test_wait_until():
    """Test the wait_until function"""

    with patch("salt.cloud.clouds.hetzner.show_instance") as show_instance:
        show_instance.side_effect = [{"state": "done"}, IndexError()]
        assert hetzner.wait_until("abc", "done")

        show_instance.side_effect = [{"state": "done"}, IndexError()]
        with pytest.raises(IndexError):
            hetzner.wait_until("abc", "never")

        show_instance.side_effect = [{"state": "done"}, IndexError()]
        assert not hetzner.wait_until("abc", "never", timeout=0)


def test_create(images, sizes, vm):
    """Test the overall creation and the required parameters"""
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with patch("salt.cloud.clouds.hetzner.wait_until", return_value=True) as wait:
            with pytest.raises(SaltCloudException):
                hetzner.create({})

            connect.return_value.server_types.get_by_name.return_value = None
            connect.return_value.images.get_by_name.return_value = None
            with pytest.raises(SaltCloudException):
                hetzner.create(vm)

            connect.return_value.server_types.get_by_name.return_value = ModelMock(
                sizes["cpx21"]
            )
            with pytest.raises(SaltCloudException):
                hetzner.create(vm)

            connect.return_value.images.get_by_name.return_value = ModelMock(
                images["ubuntu-20.04"]
            )

            assert hetzner.create(vm)["created"]
            connect.return_value.servers.create.assert_called_once()
            args = connect.return_value.servers.create.call_args
            assert args.kwargs["name"] == vm["name"]
            assert args.kwargs["server_type"] == sizes["cpx21"]
            assert args.kwargs["image"] == images["ubuntu-20.04"]


def test_create_location(vm):
    """Test the locations during the creation"""
    vm["location"] = "abc"

    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        hetzner.create(vm)
        connect.return_value.servers.create.assert_called_once()
        connect.return_value.locations.get_by_name.assert_called_once_with("abc")

        # The location should be passed to the create
        connect.return_value.locations.get_by_name.return_value = "abc"
        hetzner.create(vm)

        args = connect.return_value.servers.create.call_args
        assert args.kwargs["location"] == "abc"

        # Stop if the location is invalid
        connect.return_value.locations.get_by_name.return_value = None
        with pytest.raises(SaltCloudException):
            hetzner.create(vm)


def test_ssh_keys(vm):
    """Test the locations during the creation"""
    vm["ssh_keys"] = ["me"]

    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        hetzner.create(vm)
        connect.return_value.ssh_keys.get_by_name.assert_called_once_with("me")

        # The ssh_keys should be passed to the create
        connect.return_value.ssh_keys.get_by_name.return_value = "me"
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        assert args.kwargs["ssh_keys"] == ["me"]

        # Invalid keys should be sorted out
        connect.return_value.ssh_keys.get_by_name.return_value = None
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        assert args.kwargs["ssh_keys"] == []


def test_create_datacenter(vm):
    """Test the datacenters during the creation"""
    vm["datacenter"] = "abc"

    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        hetzner.create(vm)
        connect.return_value.servers.create.assert_called_once()
        connect.return_value.datacenters.get_by_name.assert_called_once_with("abc")

        # The datacenter should be passed to the create
        connect.return_value.datacenters.get_by_name.return_value = "abc"
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        assert args.kwargs["datacenter"] == "abc"

        # Stop if the datacenter is invalid
        connect.return_value.datacenters.get_by_name.return_value = None
        with pytest.raises(SaltCloudException):
            hetzner.create(vm)


def test_create_volumes(vm):
    """Test the volumes during the creation"""
    vm["volumes"] = ["a", "b"]

    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        connect.return_value.volumes.get_all.return_value = ["a", "c"]

        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        assert args.kwargs["volumes"], ["a"]

        vm["volumes"] = ["a", "b", "c"]
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        assert args.kwargs["volumes"] == ["a", "c"]


def test_create_networks(vm):
    """Test the networks during the creation"""
    vm["networks"] = ["a", "b"]

    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        connect.return_value.networks.get_all.return_value = ["a", "c"]

        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        assert args.kwargs["networks"] == ["a"]

        vm["networks"] = ["a", "b", "c"]
        hetzner.create(vm)
        args = connect.return_value.servers.create.call_args
        assert args.kwargs["networks"] == ["a", "c"]


def test_start():
    """Test the start action"""
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with patch("salt.cloud.clouds.hetzner.wait_until", return_value=True) as wait:
            with pytest.raises(SaltCloudSystemExit):
                hetzner.start("myvm", "function")

            connect.return_value.servers.get_by_name.return_value = None
            hetzner.start("myvm", "action")

            server = connect.return_value.servers.get_by_name.return_value = MagicMock()

            assert "Started" in hetzner.start("myvm", "action")
            server.power_on.assert_called_once()

            wait.return_value = False
            hetzner.start("myvm", "action")


def test_stop():
    """Test the stop action"""
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with patch("salt.cloud.clouds.hetzner.wait_until", return_value=True) as wait:
            with pytest.raises(SaltCloudSystemExit):
                hetzner.stop("myvm", "function")

            connect.return_value.servers.get_by_name.return_value = None
            hetzner.stop("myvm", "action")

            server = connect.return_value.servers.get_by_name.return_value = MagicMock()

            assert "Stopped" in hetzner.stop("myvm", "action")
            server.power_off.assert_called_once()

            wait.return_value = False
            hetzner.stop("myvm", "action")


def test_reboot():
    """Test the reboot action"""
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with patch("salt.cloud.clouds.hetzner.wait_until", return_value=True) as wait:
            with pytest.raises(SaltCloudSystemExit):
                hetzner.reboot("myvm", "function")

            connect.return_value.servers.get_by_name.return_value = None
            hetzner.reboot("myvm", "action")

            server = connect.return_value.servers.get_by_name.return_value = MagicMock()

            assert "Rebooted" in hetzner.reboot("myvm", "action")
            server.reboot.assert_called_once()

            wait.return_value = False
            hetzner.reboot("myvm", "action")


def test_destroy():
    """Test the destroy action"""
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with patch("salt.cloud.clouds.hetzner.wait_until", return_value=True) as wait:
            with patch("salt.cloud.clouds.hetzner.show_instance") as show_instance:
                with pytest.raises(SaltCloudSystemExit):
                    hetzner.destroy("myvm", "function")

                wait.return_value = False
                show_instance.return_value = {"state": "running"}
                connect.return_value.servers.get_by_name.return_value = None
                hetzner.destroy("myvm", "action")

                server = connect.return_value.servers.get_by_name.return_value = (
                    MagicMock()
                )

                # Stop the server before shutdown but failed
                hetzner.destroy("myvm", "action")
                server.delete.assert_not_called()
                wait.assert_called_once_with("myvm", "off")

                wait.return_value = True
                hetzner.destroy("myvm", "action")
                server.delete.assert_called_once()

                # Don't stop if the server isn't running
                show_instance.return_value = {"state": "off"}
                wait.reset_mock()
                hetzner.destroy("myvm", "action")
                wait.assert_not_called()


def test_resize():
    """Test the resize action"""
    kwargs = {"size": "cpx21"}

    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as connect:
        with patch("salt.cloud.clouds.hetzner.wait_until", return_value=True) as wait:
            with patch("salt.cloud.clouds.hetzner.show_instance") as show_instance:
                with pytest.raises(SaltCloudSystemExit):
                    hetzner.resize("myvm", kwargs, "function")

                wait.return_value = False
                show_instance.return_value = {"state": "running"}
                connect.return_value.server_types.get_by_name = MagicMock(
                    return_value=None
                )
                connect.return_value.servers.get_by_name.return_value = None

                hetzner.resize("myvm", kwargs, "action")

                server = connect.return_value.servers.get_by_name.return_value = (
                    MagicMock()
                )

                # Invalid server size
                with pytest.raises(SaltCloudException):
                    hetzner.resize("myvm", {}, "action")
                with pytest.raises(SaltCloudException):
                    hetzner.resize("myvm", kwargs, "action")

                connect.return_value.server_types.get_by_name.return_value = True

                # Stop the server before shutdown but failed
                hetzner.resize("myvm", kwargs, "action")
                server.change_type.assert_not_called()
                wait.assert_called_once_with("myvm", "off")

                wait.return_value = True
                hetzner.resize("myvm", kwargs, "action")
                server.change_type.assert_called_once()

                # Don't stop if the server isn't running
                show_instance.return_value = {"state": "off"}
                wait.reset_mock()
                hetzner.resize("myvm", kwargs, "action")
                wait.assert_not_called()


def test_config_loading(vm):
    """Test if usual config parameters are loaded via get_cloud_config_value()"""
    with patch(
        "salt.cloud.clouds.hetzner._connect_client", return_value=MagicMock()
    ) as client:
        with patch(
            "salt.config.get_cloud_config_value", return_value=MagicMock()
        ) as cloud_config:
            hetzner.create(vm)

            config_values = {
                "automount",
                "datacenter",
                "image",
                "labels",
                "location",
                "name",
                "networks",
                "private_key",
                "size",
                "ssh_keys",
                "user_data",
                "volumes",
            }
            calls = set(map(lambda call: call[0][0], cloud_config.call_args_list))
            assert config_values.issubset(calls)

import pytest

import salt.cloud.clouds.openstack as openstack
from salt.utils import dictupdate
from tests.support.mock import MagicMock, call, patch

# pylint: disable=confusing-with-statement


class MockImage:
    name = "image name"
    id = "image id"


class MockNode:
    name = "node name"
    id = "node id"
    flavor = MockImage()
    status = "node status"

    def __init__(self, image):
        self.image = image

    def __iter__(self):
        return iter(())


class MockConn:
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


@pytest.fixture
def configure_loader_modules():
    return {
        openstack: {
            "__active_provider_name__": "",
            "__opts__": {
                "providers": {
                    "my-openstack-cloud": {
                        "openstack": {
                            "auth": "daenerys",
                            "region_name": "westeros",
                            "cloud": "openstack",
                        }
                    }
                }
            },
        }
    }


@pytest.fixture
def expected_config_stuff():
    vm = {"asdf": ...}

    with patch("copy.deepcopy", autospec=True, return_value=42), patch.dict(
        openstack.__opts__, {"foo": "bar"}
    ):
        yield vm


def test_when_getting_cloud_config_values_expected_args_should_be_provided():
    expected_vm = "whatever"
    expected_calls = call(
        "ignore_cidr", expected_vm, openstack.__opts__, default="", search_global=False
    )


@pytest.mark.parametrize(
    "comment,example_ip,ignored_cidr,expected",
    [
        ("ip is in ignore_cidr string", "203.0.113.1", "203.0.113.0/24", True),
        ("ip is not in ignore_cidr string", "192.0.2.1", "203.0.113.0/24", False),
        ("ignore_cidr is empty", "192.0.2.1", "", False),
        ("ignore_cidr is False", "192.0.2.1", False, False),
        ("ignore_cidr is None", "192.0.2.1", None, False),
        (
            "ip is in ignore_cidr list",
            "192.0.2.1",
            ["192.0.2.0/24", "203.0.113.0/24"],
            True,
        ),
        (
            "ip is not in ignore_cidr list",
            "192.0.2.1",
            ["198.51.100.0/24", "203.0.113.0/24"],
            False,
        ),
    ],
)
def test_when_ignore_cidr_is_configured_and_ip_is_provided_result_is_expected(
    comment, example_ip, ignored_cidr, expected
):
    with patch(
        "salt.config.get_cloud_config_value", autospec=True, return_value=ignored_cidr
    ):
        result = openstack.ignore_cidr("fnord", example_ip)

    assert result is expected


@pytest.mark.parametrize(
    "comment,example_ips,ignored_cidr,expected",
    [
        (
            "ignore_cidr matches first 2 ips, expected value will be first ip that"
            " doesn't match cidr.",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2"],
            "203.0.113.0/24",
            "192.0.2.1",
        ),
        (
            "ignore_cidr matches 2nd 2 IPs, expected value will be first ip in list. ",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2"],
            "192.0.2.0/24",
            "203.0.113.1",
        ),
        (
            "ignore_cidr doesn't match any IPs, expected value will be first ip in"
            " list.",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2"],
            "198.51.100.0/24",
            "203.0.113.1",
        ),
        (
            "ignore_cidr matches all IPs, expected value will be False.",
            ["203.0.113.1", "203.0.113.2", "203.0.113.3", "203.0.113.4"],
            "203.0.113.0/24",
            False,
        ),
        (
            "When ignore_cidr is not set, return first ip",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2"],
            None,
            "203.0.113.1",
        ),
    ],
)
def test_preferred_ip_function_returns_expected(
    comment, example_ips, ignored_cidr, expected
):
    with patch(
        "salt.config.get_cloud_config_value", autospec=True, return_value=ignored_cidr
    ):
        result = openstack.preferred_ip("fnord", example_ips)

    assert result is expected


def test_get_configured_provider_bad():
    with patch.dict(openstack.__opts__, {"providers": {}}):
        result = openstack.get_configured_provider()
        assert result is False


def test_get_configured_provider_auth():
    config = {
        "region_name": "westeros",
        "auth": "daenerys",
    }
    with patch.dict(
        openstack.__opts__,
        {"providers": {"my-openstack-cloud": {"openstack": config}}},
    ):
        result = openstack.get_configured_provider()
        assert config == result


def test_get_configured_provider_cloud():
    config = {
        "region_name": "westeros",
        "cloud": "foo",
    }
    with patch.dict(
        openstack.__opts__,
        {"providers": {"my-openstack-cloud": {"openstack": config}}},
    ):
        result = openstack.get_configured_provider()
        assert config == result


def test_get_dependencies():
    HAS_SHADE = (True, "Please install newer version of shade: >= 1.19.0")
    with patch("salt.cloud.clouds.openstack.HAS_SHADE", HAS_SHADE):
        result = openstack.get_dependencies()
        assert result is True


def test_get_dependencies_no_shade():
    HAS_SHADE = (False, "Install pypi module shade >= 1.19.0")
    with patch("salt.cloud.clouds.openstack.HAS_SHADE", HAS_SHADE):
        result = openstack.get_dependencies()
        assert result is False


def test_list_nodes_full_image_str():
    node_image = "node image"
    conn = MockConn(node_image)
    with patch("salt.cloud.clouds.openstack._get_ips", return_value=[]):
        ret = openstack.list_nodes_full(conn=conn)
        assert ret[conn.node.name]["image"] == node_image


def test_list_nodes_full_image_obj():
    conn = MockConn(MockImage())
    with patch("salt.cloud.clouds.openstack._get_ips", return_value=[]):
        ret = openstack.list_nodes_full(conn=conn)
        assert ret[conn.node.name]["image"] == MockImage.name


def test_show_instance():
    conn = MockConn(MockImage())
    with patch("salt.cloud.clouds.openstack._get_ips", return_value=[]):
        ret = openstack.show_instance(conn.node.name, conn=conn, call="action")
        assert ret["image"] == MockImage.name


def test_request_instance_should_use_provided_connection_if_not_None():
    fake_conn = MagicMock()

    patch_get_conn = patch("salt.cloud.clouds.openstack.get_conn", autospec=True)
    patch_utils = patch.dict(
        openstack.__utils__,
        {"cloud.check_name": MagicMock(), "dictupdate.update": dictupdate.update},
    )
    patch_shade = patch.object(
        openstack, "shade.exc.OpenStackCloudException", Exception, create=True
    )

    with patch_get_conn as fake_get_conn, patch_utils, patch_shade:
        openstack.request_instance(
            vm_={"name": "fnord", "driver": "fnord"}, conn=fake_conn
        )

        fake_get_conn.assert_not_called()


def test_request_instance_should_create_conn_if_provided_is_None():
    none_conn = None

    patch_get_conn = patch("salt.cloud.clouds.openstack.get_conn", autospec=True)
    patch_utils = patch.dict(
        openstack.__utils__,
        {"cloud.check_name": MagicMock(), "dictupdate.update": dictupdate.update},
    )
    patch_shade = patch.object(
        openstack, "shade.exc.OpenStackCloudException", Exception, create=True
    )

    with patch_get_conn as fake_get_conn, patch_utils, patch_shade:
        openstack.request_instance(
            vm_={"name": "fnord", "driver": "fnord"}, conn=none_conn
        )

        fake_get_conn.assert_called_once_with()


# According to
# https://docs.openstack.org/shade/latest/user/usage.html#shade.OpenStackCloud.create_server
# the `network` parameter can be:
# (optional) Network dict or name or ID to attach the server to.
# Mutually exclusive with the nics parameter. Can also be be a list of
# network names or IDs or network dicts.
#
# Here we're testing a normal dictionary
def test_request_instance_should_be_able_to_provide_a_dictionary_for_network():
    fake_conn = MagicMock()
    expected_network = {"foo": "bar"}
    vm_ = {"name": "fnord", "driver": "fnord", "network": expected_network}
    patch_utils = patch.dict(
        openstack.__utils__,
        {"cloud.check_name": MagicMock(), "dictupdate.update": dictupdate.update},
    )
    with patch_utils:
        openstack.request_instance(vm_=vm_, conn=fake_conn)

        call_kwargs = fake_conn.create_server.mock_calls[0][-1]
        assert call_kwargs["network"] == expected_network


# Here we're testing the list of dictionaries
def test_request_instance_should_be_able_to_provide_a_list_of_dictionaries_for_network():
    fake_conn = MagicMock()
    expected_network = [{"foo": "bar"}, {"bang": "quux"}]
    vm_ = {"name": "fnord", "driver": "fnord", "network": expected_network}
    patch_utils = patch.dict(
        openstack.__utils__,
        {"cloud.check_name": MagicMock(), "dictupdate.update": dictupdate.update},
    )
    with patch_utils:
        openstack.request_instance(vm_=vm_, conn=fake_conn)

        call_kwargs = fake_conn.create_server.mock_calls[0][-1]
        assert call_kwargs["network"] == expected_network


# Here we're testing for names/IDs
def test_request_instance_should_be_able_to_provide_a_list_of_single_ids_or_names_for_network():
    fake_conn = MagicMock()
    expected_network = ["foo", "bar", "bang", "fnord1", "fnord2"]
    vm_ = {"name": "fnord", "driver": "fnord", "network": expected_network}
    patch_utils = patch.dict(
        openstack.__utils__,
        {"cloud.check_name": MagicMock(), "dictupdate.update": dictupdate.update},
    )
    with patch_utils:
        openstack.request_instance(vm_=vm_, conn=fake_conn)

        call_kwargs = fake_conn.create_server.mock_calls[0][-1]
        assert call_kwargs["network"] == expected_network


# Testing that we get a dict that we expect for create_server
def test__clean_create_kwargs():
    params = {
        "name": "elmer",
        "image": "mirrormirror",
        "flavor": "chocolate",
        "auto_ip": True,
        "ips": ["hihicats"],
        "ip_pool": "olympic",
        "root_volume": "iamgroot",
        "boot_volume": "pussnboots",
        "terminate_volume": False,
        "volumes": ["lots", "of", "books"],
        "meta": {"full": "meta"},
        "files": {"shred": "this"},
        "reservation_id": "licenseandregistration",
        "security_groups": ["wanna", "play", "repeat"],
        "key_name": "clortho",
        "availability_zone": "callmemaybe",
        "block_device_mapping": [{"listof": "dicts"}],
        "block_device_mapping_v2": [{"listof": "dicts"}],
        "nics": ["thats", "me"],
        "scheduler_hints": {"so": "many"},
        "config_drive": True,
        "disk_config": "donkey",
        "admin_pass": "password",
        "wait": False,
        "timeout": 30,
        "reuse_ips": True,
        "network": ["also", "a", "dict"],
        "boot_from_volume": True,
        "volume_size": 30,
        "nat_destination": "albuquerque",
        "group": "ledzeppelin",
        "userdata": "needmoreinput",
        "thisgetsdropped": "yup",
    }
    patch_utils = patch.dict(
        openstack.__utils__,
        {"dictupdate.update": dictupdate.update},
    )
    with patch_utils:
        ret = openstack._clean_create_kwargs(**params)
        params.pop("thisgetsdropped")
        assert params == ret

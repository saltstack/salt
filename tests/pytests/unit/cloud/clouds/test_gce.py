"""
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.pytests.unit.cloud.clouds.test_gce
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import collections

import pytest
from salt.cloud.clouds import gce
from salt.exceptions import SaltCloudSystemExit
from salt.utils.versions import LooseVersion
from tests.support.mock import MagicMock
from tests.support.mock import __version__ as mock_version
from tests.support.mock import patch

VM_NAME = "kings_landing"
DUMMY_TOKEN = {
    "refresh_token": None,
    "client_id": "dany123",
    "client_secret": "lalalalalalala",
    "grant_type": "refresh_token",
}


class DummyGCEConn:
    def __init__(self):
        self.create_node = MagicMock()
        self.ex_create_address = MagicMock(return_value=DummyGCEAddress())

    def __getattr__(self, attr):
        funcs = ["create_node", "ex_create_address"]
        if attr not in funcs:
            # Return back the first thing passed in (i.e. don't call out to get
            # the override value).
            return lambda *args, **kwargs: args[0]


class DummyGCERegion:
    def __init__(self):
        self.name = MagicMock()


class DummyGCEAddress:
    def __init__(self):
        self.id = MagicMock()
        self.name = MagicMock()
        self.address = MagicMock()
        self.region = DummyGCERegion()
        self.driver = MagicMock()
        self.extra = MagicMock()


@pytest.fixture
def configure_loader_modules():

    return {
        gce: {
            "__active_provider_name__": "",
            "__utils__": {
                "cloud.fire_event": MagicMock(),
                "cloud.filter_event": MagicMock(),
            },
            "__opts__": {
                "sock_dir": True,
                "transport": True,
                "providers": {
                    "my-google-cloud": {
                        "gce": {
                            "project": "daenerys-cloud",
                            "service_account_email_address": (
                                "dany@targaryen.westeros.cloud"
                            ),
                            "service_account_private_key": "/home/dany/PRIVKEY.pem",
                            "driver": "gce",
                            "ssh_interface": "public_ips",
                        }
                    }
                },
            },
        }
    }


@pytest.fixture(scope="module")
def location():
    return collections.namedtuple("Location", "name")("chicago")


@pytest.fixture
def config(location):

    return {
        "name": "new",
        "driver": "gce",
        "profile": None,
        "size": 1234,
        "image": "myimage",
        "location": location,
        "ex_network": "mynetwork",
        "ex_subnetwork": "mysubnetwork",
        "ex_tags": "mytags",
        "ex_metadata": "metadata",
    }


@pytest.fixture
def conn():
    return DummyGCEConn()


def test_destroy_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call destroy
    with --function or -f.
    """
    pytest.raises(SaltCloudSystemExit, gce.destroy, vm_name=VM_NAME, call="function")


@pytest.mark.skipif(
    gce.HAS_LIBCLOUD is False, reason="apache-libcloud is not installed"
)
def test_fail_virtual_libcloud_version_too_old():
    # Missing deps
    with patch("libcloud.__version__", "2.4.0"):
        v = gce.__virtual__()
        assert v == (False, "The salt-cloud GCE driver requires apache-libcloud>=2.5.0")


@pytest.mark.skipif(
    gce.HAS_LIBCLOUD is False, reason="apache-libcloud is not installed"
)
def test_fail_virtual_missing_deps():
    # Missing deps
    with patch("salt.config.check_driver_dependencies", return_value=False):
        v = gce.__virtual__()
        assert v is False


@pytest.mark.skipif(
    gce.HAS_LIBCLOUD is False, reason="apache-libcloud is not installed"
)
def test_fail_virtual_deps_missing_config():
    with patch("salt.config.check_driver_dependencies", return_value=True), patch(
        "salt.config.is_provider_configured", return_value=False
    ):
        v = gce.__virtual__()
        assert v is False


def test_import():
    """
    Test that the module picks up installed deps
    """
    with patch("salt.config.check_driver_dependencies", return_value=True) as p:
        get_deps = gce.get_dependencies()
        assert get_deps is True
        if LooseVersion(mock_version) >= LooseVersion("2.0.0"):
            p.assert_called_once()


def test_provider_matches():
    """
    Test that the first configured instance of a gce driver is matched
    """
    p = gce.get_configured_provider()
    assert p is not None


def test_request_instance_with_accelerator(config, location, conn):
    """
    Test requesting an instance with GCE accelerators
    """

    config.update({"ex_accelerator_type": "foo", "ex_accelerator_count": 42})
    call_kwargs = {
        "ex_disk_type": "pd-standard",
        "ex_metadata": {"items": [{"value": None, "key": "salt-cloud-profile"}]},
        "ex_accelerator_count": 42,
        "name": "new",
        "ex_service_accounts": None,
        "external_ip": "ephemeral",
        "ex_accelerator_type": "foo",
        "ex_tags": None,
        "ex_disk_auto_delete": True,
        "ex_network": "default",
        "ex_disks_gce_struct": None,
        "ex_preemptible": False,
        "ex_can_ip_forward": False,
        "ex_on_host_maintenance": "TERMINATE",
        "location": location,
        "ex_subnetwork": None,
        "image": "myimage",
        "size": 1234,
    }

    with patch("salt.cloud.clouds.gce.get_conn", MagicMock(return_value=conn)), patch(
        "salt.cloud.clouds.gce.show_instance", MagicMock()
    ), patch("salt.cloud.clouds.gce.LIBCLOUD_VERSION_INFO", (2, 5, 0)):
        gce.request_instance(config)
        conn.create_node.assert_called_once_with(**call_kwargs)


def test__expand_region():
    """
    Test that _expand_region returns the correct data
    """
    region = DummyGCERegion()
    region.name = "us-central1"

    ret = gce._expand_region(region)
    expected = {"name": "us-central1"}

    assert ret == expected


def test_create_address(conn):
    """
    Test create_address
    """

    region = DummyGCERegion()
    region.name = "us-central1"

    address = DummyGCEAddress()
    address.region = region

    call_args = ("my-ip", region, address)

    with patch("salt.cloud.clouds.gce.get_conn", MagicMock(return_value=conn)), patch(
        "salt.cloud.clouds.gce.LIBCLOUD_VERSION_INFO", (2, 3, 0)
    ):
        kwargs = {"name": "my-ip", "region": region, "address": address}
        gce.create_address(kwargs, "function")
        conn.ex_create_address.assert_called_once_with(*call_args)

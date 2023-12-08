"""
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.pytests.unit.cloud.clouds.test_gce
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import collections

import pytest

from salt.cloud.clouds import gce
from salt.exceptions import SaltCloudSystemExit
from salt.utils.versions import Version
from tests.support.mock import MagicMock
from tests.support.mock import __version__ as mock_version
from tests.support.mock import call, patch


@pytest.fixture
def configure_loader_modules():

    return {
        gce: {
            "show_instance": MagicMock(),
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


@pytest.fixture(
    params=[
        {"expected": "", "image": ""},
        {"expected": None, "image": None},
        {"expected": "debian-10", "image": "debian-10"},
    ]
)
def config_image(request):
    return request.param["expected"], request.param["image"]


@pytest.fixture(
    params=[
        {"expected": None, "label": "{}"},
        {"expected": {"mylabel": "myvalue"}, "label": "{'mylabel': 'myvalue'}"},
    ]
)
def config_labels(request):
    return request.param["expected"], request.param["label"]


@pytest.fixture(
    params=[
        {
            "expected": collections.namedtuple("Location", "name")("chicago"),
            "location": collections.namedtuple("Location", "name")("chicago"),
        },
    ]
)
def config_location(request):
    return request.param["expected"], request.param["location"]


@pytest.fixture(
    params=[
        {
            "expected": {"items": [{"key": "salt-cloud-profile", "value": None}]},
            "metadata": {},
        },
        {
            "expected": {
                "items": [
                    {"key": "mykey", "value": "myvalue"},
                    {"key": "salt-cloud-profile", "value": None},
                ]
            },
            "metadata": "{'mykey': 'myvalue'}",
        },
    ]
)
def config_metadata(request):
    return request.param["expected"], request.param["metadata"]


@pytest.fixture(
    params=[
        {"expected": "mynetwork", "network": "mynetwork"},
    ]
)
def config_network(request):
    return request.param["expected"], request.param["network"]


@pytest.fixture(
    params=[
        {"expected": "e2-standard-2", "size": "e2-standard-2"},
    ]
)
def config_size(request):
    return request.param["expected"], request.param["size"]


@pytest.fixture(
    params=[
        {"expected": "mysubnetwork", "subnetwork": "mysubnetwork"},
    ]
)
def config_subnetwork(request):
    return request.param["expected"], request.param["subnetwork"]


@pytest.fixture(
    params=[
        {"expected": None, "tag": "{}"},
        {"expected": ["mytag", "myvalue"], "tag": "['mytag', 'myvalue']"},
    ]
)
def config_tags(request):
    return request.param["expected"], request.param["tag"]


@pytest.fixture
def config(
    config_image,
    config_labels,
    config_location,
    config_metadata,
    config_network,
    config_size,
    config_subnetwork,
    config_tags,
):
    expected_image, image = config_image
    expected_labels, labels = config_labels
    expected_location, location = config_location
    expected_metadata, metadata = config_metadata
    expected_network, network = config_network
    expected_size, size = config_size
    expected_subnetwork, subnetwork = config_subnetwork
    expected_tags, tags = config_tags
    expected_call_kwargs = {
        "ex_disk_type": "pd-standard",
        "ex_metadata": expected_metadata,
        "ex_accelerator_count": 42,
        "name": "new",
        "ex_service_accounts": None,
        "external_ip": "ephemeral",
        "ex_accelerator_type": "foo",
        "ex_tags": expected_tags,
        "ex_labels": expected_labels,
        "ex_disk_auto_delete": True,
        "ex_network": expected_network,
        "ex_disks_gce_struct": None,
        "ex_preemptible": False,
        "ex_can_ip_forward": False,
        "ex_on_host_maintenance": "TERMINATE",
        "location": expected_location,
        "ex_subnetwork": expected_subnetwork,
        "image": expected_image,
        "size": expected_size,
    }
    config = {
        "name": "new",
        "driver": "gce",
        "profile": None,
        "size": size,
        "image": image,
        "location": location,
        "ex_accelerator_type": "foo",
        "ex_accelerator_count": 42,
        "network": network,
        "subnetwork": subnetwork,
        "ex_labels": labels,
        "tags": tags,
        "metadata": metadata,
    }
    return expected_call_kwargs, config


@pytest.fixture
def fake_libcloud_2_3_0():
    with patch("salt.cloud.clouds.gce.LIBCLOUD_VERSION_INFO", (2, 3, 0)):
        yield


@pytest.fixture
def fake_libcloud_2_5_0():
    with patch("salt.cloud.clouds.gce.LIBCLOUD_VERSION_INFO", (2, 5, 0)):
        yield


@pytest.fixture
def conn():
    def return_first(*args, **kwargs):
        return args[0]

    with patch("salt.cloud.clouds.gce.get_conn", autospec=True) as fake_conn:
        fake_addy = MagicMock()
        fake_addy.extra = {}
        fake_addy.region.name = "fnord town"
        fake_conn.return_value.ex_create_address.return_value = fake_addy
        fake_conn.return_value.ex_get_network.side_effect = return_first
        fake_conn.return_value.ex_get_image.side_effect = return_first
        fake_conn.return_value.ex_get_zone.side_effect = return_first
        fake_conn.return_value.ex_get_size.side_effect = return_first
        yield fake_conn.return_value


@pytest.fixture
def fake_conf_provider():
    with patch("salt.config.is_provider_configured", autospec=True) as fake_conf:
        yield fake_conf


def test_destroy_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call destroy
    with --function or -f.
    """
    pytest.raises(
        SaltCloudSystemExit, gce.destroy, vm_name="kings_landing", call="function"
    )


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
        if Version(mock_version) >= Version("2.0.0"):
            p.assert_called_once()


@pytest.mark.parametrize(
    "active_provider", [("fnord", "fnord"), (None, "gce"), ("", "gce")]
)
def test_get_configured_provider_should_pass_expected_args(
    active_provider, fake_conf_provider
):
    """
    gce delegates the behavior to config.is_provider_configured, and should
    pass on expected args.
    """
    provider_name, expected_provider = active_provider
    with patch(
        "salt.cloud.clouds.gce._get_active_provider_name",
        autospec=True,
        return_value=provider_name,
    ):
        gce.get_configured_provider()
    fake_conf_provider.assert_called_with(
        gce.__opts__,
        expected_provider,
        ("project", "service_account_email_address", "service_account_private_key"),
    )


def test_get_configured_provider_should_return_expected_result(fake_conf_provider):
    """
    Currently get_configured_provider should simply return whatever
    comes back from config.is_provider_configured, no questions asked.
    """
    expected_result = object()
    fake_conf_provider.return_value = expected_result

    actual_result = gce.get_configured_provider()

    assert actual_result is expected_result


def test_request_instance_with_accelerator(config, conn):
    """
    Test requesting an instance with GCE accelerators
    """
    expected_call_kwargs, vm_config = config
    gce.request_instance(vm_config)
    conn.create_node.assert_called_once_with(**expected_call_kwargs)


def test_create_address_should_fire_creating_and_created_events_with_expected_args(
    conn,
):
    region = MagicMock()
    region.name = "antarctica"
    kwargs = {"name": "bob", "region": region, "address": "123 Easy Street"}
    expected_args = {
        "name": "bob",
        "region": {"name": "antarctica"},
        "address": "123 Easy Street",
    }
    expected_creating_call = call(
        "event",
        "create address",
        "salt/cloud/address/creating",
        args=expected_args,
        sock_dir=gce.__opts__["sock_dir"],
        transport=gce.__opts__["transport"],
    )
    expected_created_call = call(
        "event",
        "created address",
        "salt/cloud/address/created",
        args=expected_args,
        sock_dir=gce.__opts__["sock_dir"],
        transport=gce.__opts__["transport"],
    )

    gce.create_address(kwargs, "function")

    gce.__utils__["cloud.fire_event"].assert_has_calls(
        [expected_creating_call, expected_created_call]
    )


def test_create_address_passes_correct_args_to_ex_create_address(
    conn, fake_libcloud_2_3_0
):
    """
    Test create_address
    """
    expected_name = "name mcnameface"
    expected_region = MagicMock(name="fnord")
    expected_address = "addresss mcaddressface"
    expected_call_args = (expected_name, expected_region, expected_address)

    kwargs = {
        "name": expected_name,
        "region": expected_region,
        "address": expected_address,
    }
    gce.create_address(kwargs, "function")

    conn.ex_create_address.assert_called_once_with(*expected_call_args)

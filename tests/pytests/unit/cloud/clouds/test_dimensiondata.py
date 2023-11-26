"""
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.dimensiondata_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import pytest

from salt.cloud.clouds import dimensiondata
from salt.exceptions import SaltCloudSystemExit
from salt.utils.versions import Version
from tests.support.mock import MagicMock
from tests.support.mock import __version__ as mock_version
from tests.support.mock import patch

try:
    import libcloud.security

    HAS_LIBCLOUD = True
except ImportError:
    HAS_LIBCLOUD = False

# Use certifi if installed
try:
    if HAS_LIBCLOUD:
        # This work-around for Issue #32743 is no longer needed for libcloud >=
        # 1.4.0. However, older versions of libcloud must still be supported
        # with this work-around. This work-around can be removed when the
        # required minimum version of libcloud is 2.0.0 (See PR #40837 - which
        # is implemented in Salt 2018.3.0).
        if Version(libcloud.__version__) < Version("1.4.0"):
            import certifi

            libcloud.security.CA_CERTS_PATH.append(certifi.where())
except (ImportError, NameError):
    pass


@pytest.fixture
def vm_name():
    return "winterfell"


def _preferred_ip(ip_set, preferred=None):
    """
    Returns a function that reacts which ip is preferred
    :param ip_set:
    :param private:
    :return:
    """

    def _ip_decider(vm, ips):
        for ip in ips:
            if ip in preferred:
                return ip
        return False

    return _ip_decider


@pytest.fixture
def configure_loader_modules():
    return {
        dimensiondata: {
            "__active_provider_name__": "",
            "__opts__": {
                "providers": {
                    "my-dimensiondata-cloud": {
                        "dimensiondata": {
                            "driver": "dimensiondata",
                            "region": "dd-au",
                            "user_id": "jon_snow",
                            "key": "IKnowNothing",
                        }
                    }
                }
            },
        }
    }


def test_avail_images_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call avail_images
    with --action or -a.
    """
    with pytest.raises(SaltCloudSystemExit):
        dimensiondata.avail_images(call="action")


def test_avail_locations_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call avail_locations
    with --action or -a.
    """
    with pytest.raises(SaltCloudSystemExit):
        dimensiondata.avail_locations(call="action")


def test_avail_sizes_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call avail_sizes
    with --action or -a.
    """
    with pytest.raises(SaltCloudSystemExit):
        dimensiondata.avail_sizes(call="action")


def test_list_nodes_call():
    """
    Tests that a SaltCloudSystemExit is raised when trying to call list_nodes
    with --action or -a.
    """
    with pytest.raises(SaltCloudSystemExit):
        dimensiondata.list_nodes(call="action")


def test_destroy_call(vm_name):
    """
    Tests that a SaltCloudSystemExit is raised when trying to call destroy
    with --function or -f.
    """
    with pytest.raises(SaltCloudSystemExit):
        dimensiondata.destroy(name=vm_name, call="function")


@pytest.mark.skipif(
    HAS_LIBCLOUD is False, reason="Install 'libcloud' to be able to run this unit test."
)
def test_avail_sizes():
    """
    Tests that avail_sizes returns an empty dictionary.
    """
    sizes = dimensiondata.avail_sizes(call="foo")
    assert len(sizes) == 1
    assert sizes["default"]["name"] == "default"


def test_import():
    """
    Test that the module picks up installed deps
    """
    with patch("salt.config.check_driver_dependencies", return_value=True) as p:
        get_deps = dimensiondata.get_dependencies()
        assert get_deps is True
        if Version(mock_version) >= Version("2.0.0"):
            assert p.call_count >= 1


def test_provider_matches():
    """
    Test that the first configured instance of a dimensiondata driver is matched
    """
    p = dimensiondata.get_configured_provider()
    assert p is not None


def test_query_node_data_filter_preferred_ip_addresses():
    """
    Test if query node data is filtering out unpreferred IP addresses.
    """
    zero_ip = "0.0.0.0"
    private_ips = [zero_ip, "1.1.1.1", "2.2.2.2"]
    vm = {"name": None}
    data = MagicMock()
    data.public_ips = []
    # pylint: disable=blacklisted-unmocked-patching
    dimensiondata.NodeState = MagicMock()
    # pylint: enable=blacklisted-unmocked-patching
    dimensiondata.NodeState.RUNNING = True

    with patch(
        "salt.cloud.clouds.dimensiondata.show_instance",
        MagicMock(
            return_value={
                "state": True,
                "name": "foo",
                "public_ips": [],
                "private_ips": private_ips,
            }
        ),
    ):
        with patch(
            "salt.cloud.clouds.dimensiondata.preferred_ip",
            _preferred_ip(private_ips, [zero_ip]),
        ):
            with patch(
                "salt.cloud.clouds.dimensiondata.ssh_interface",
                MagicMock(return_value="private_ips"),
            ):
                assert dimensiondata._query_node_data(vm, data).public_ips == [zero_ip]

import logging

import pytest

from salt.cloud.clouds import vultrpy as vultr
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        vultr: {
            "__utils__": {
                "cloud.fire_event": MagicMock(),
                "cloud.filter_event": MagicMock(),
                "cloud.wait_for_fun": MagicMock(),
                "cloud.bootstrap": MagicMock(),
            },
            "__opts__": {
                "providers": {
                    "vultr01": {
                        "vultr": {
                            "api_key": "super_secret_key",
                            "driver": "vultr",
                        },
                    },
                },
                "sock_dir": "/tmp/sock_dir",
                "transport": "tcp",
            },
            "__active_provider_name__": "my_vultr:vultr",
        }
    }


def test_show_keypair_no_keyname(caplog):
    """
    test salt.cloud.clouds.vultr.show_keypair
    when keyname is not in kwargs
    """
    with caplog.at_level(logging.INFO):
        assert not vultr.show_keypair({})
        assert "A keyname is required." in caplog.text


def test_show_keypair():
    """
    test salt.cloud.clouds.vultr.show_keypair
    when keyname provided
    """
    with patch(
        "salt.cloud.clouds.vultrpy._query", return_value={"test": {"SSHKEYID": "keyID"}}
    ):
        kwargs = {"keyname": "test"}
        assert vultr.show_keypair(kwargs) == {"SSHKEYID": "keyID"}


def test_create_firewall_ssh():
    """
    Test create when setting firewall_group_id and
    ssh_key_names.
    """
    kwargs = {
        "provider": "vultr",
        "enable_private_network": True,
        "ssh_key_names": "key1,key2,key3",
        "startup_script_id": "test_id",
        "firewall_group_id": "f_id",
        "image": 223,
        "size": 13,
        "location": 1,
        "name": "test-vm",
    }
    patch_scripts = patch(
        "salt.cloud.clouds.vultrpy.avail_scripts",
        MagicMock(return_value=["test_id"]),
    )

    patch_firewall = patch(
        "salt.cloud.clouds.vultrpy.avail_firewall_groups",
        MagicMock(return_value=["f_id"]),
    )

    patch_keys = patch(
        "salt.cloud.clouds.vultrpy.avail_keys",
        MagicMock(return_value=["key3", "key2", "key1"]),
    )

    patch_vultrid = patch(
        "salt.cloud.clouds.vultrpy._lookup_vultrid",
        MagicMock(return_value="test_id"),
    )

    mock_query = MagicMock(return_value={"status": 200})
    patch_query = patch("salt.cloud.clouds.vultrpy._query", mock_query)

    patch_show = patch("salt.cloud.clouds.vultrpy.show_instance", MagicMock())

    with patch_scripts, patch_firewall, patch_keys, patch_vultrid, patch_query, patch_show:
        vultr.create(kwargs)
        query_ret = mock_query.call_args.kwargs["data"]
        assert "SSHKEYID=key1%2Ckey2%2Ckey3" in query_ret
        assert "FIREWALLGROUPID=f_id" in query_ret


def test_create_firewall_doesnotexist(caplog):
    """
    Test create when setting firewall_group_id to a firewall
    that does not exist
    """
    kwargs = {
        "provider": "vultr",
        "enable_private_network": True,
        "startup_script_id": "test_id",
        "firewall_group_id": "doesnotexist",
        "image": 223,
        "size": 13,
        "location": 1,
        "name": "test-vm",
    }
    patch_scripts = patch(
        "salt.cloud.clouds.vultrpy.avail_scripts",
        MagicMock(return_value=["test_id"]),
    )

    patch_firewall = patch(
        "salt.cloud.clouds.vultrpy.avail_firewall_groups",
        MagicMock(return_value=["f_id"]),
    )

    patch_keys = patch(
        "salt.cloud.clouds.vultrpy.avail_keys",
        MagicMock(return_value=["key3", "key2", "key1"]),
    )

    patch_vultrid = patch(
        "salt.cloud.clouds.vultrpy._lookup_vultrid",
        MagicMock(return_value="test_id"),
    )

    mock_query = MagicMock(return_value={"status": 200})
    patch_query = patch("salt.cloud.clouds.vultrpy._query", mock_query)

    patch_show = patch("salt.cloud.clouds.vultrpy.show_instance", MagicMock())

    with patch_scripts, patch_firewall, patch_keys, patch_vultrid, patch_query, patch_show:
        with caplog.at_level(logging.INFO):
            ret = vultr.create(kwargs)
            assert (
                "Your Vultr account does not have a firewall group with ID doesnotexist"
                in caplog.text
            )
            assert ret is False


def test_create_ssh_key_ids_doesnotexist(caplog):
    """
    Test create when setting ssh_key_ids that do not
    exist
    """
    kwargs = {
        "provider": "vultr",
        "enable_private_network": True,
        "startup_script_id": "test_id",
        "ssh_key_names": "doesnotexist",
        "image": 223,
        "size": 13,
        "location": 1,
        "name": "test-vm",
    }
    patch_scripts = patch(
        "salt.cloud.clouds.vultrpy.avail_scripts",
        MagicMock(return_value=["test_id"]),
    )

    patch_firewall = patch(
        "salt.cloud.clouds.vultrpy.avail_firewall_groups",
        MagicMock(return_value=["f_id"]),
    )

    patch_keys = patch(
        "salt.cloud.clouds.vultrpy.avail_keys",
        MagicMock(return_value=["key3", "key2", "key1"]),
    )

    patch_vultrid = patch(
        "salt.cloud.clouds.vultrpy._lookup_vultrid",
        MagicMock(return_value="test_id"),
    )

    mock_query = MagicMock(return_value={"status": 200})
    patch_query = patch("salt.cloud.clouds.vultrpy._query", mock_query)

    patch_show = patch("salt.cloud.clouds.vultrpy.show_instance", MagicMock())

    with patch_scripts, patch_firewall, patch_keys, patch_vultrid, patch_query, patch_show:
        with caplog.at_level(logging.INFO):
            ret = vultr.create(kwargs)
            assert (
                "Your Vultr account does not have a key with ID doesnotexist"
                in caplog.text
            )
            assert ret is False

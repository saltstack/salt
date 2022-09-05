"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest

import salt.states.win_network as win_network
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_network: {}}


def test_managed_missing_parameters():
    """
    Test to ensure that the named interface is configured properly.
    """
    ret = {
        "name": "salt",
        "changes": {},
        "result": False,
        "comment": (
            "dns_proto must be one of the following: static, dhcp\n"
            "ip_proto must be one of the following: static, dhcp"
        ),
    }
    assert win_network.managed("salt") == ret


def test_managed_static_enabled_false():
    ret = {
        "name": "salt",
        "changes": {},
        "result": True,
        "comment": "Interface 'salt' is up to date (already disabled)",
    }
    mock_false = MagicMock(return_value=False)
    with patch.dict(win_network.__salt__, {"ip.is_enabled": mock_false}):
        assert (
            win_network.managed(
                "salt", dns_proto="static", ip_proto="static", enabled=False
            )
            == ret
        )


def test_managed_test_true():
    ret = {
        "name": "salt",
        "changes": {},
        "result": False,
        "comment": "Failed to enable interface 'salt' to make changes",
    }
    mock_false = MagicMock(return_value=False)
    with patch.dict(
        win_network.__salt__, {"ip.is_enabled": mock_false, "ip.enable": mock_false}
    ), patch.dict(win_network.__opts__, {"test": False}):
        assert win_network.managed("salt", dns_proto="static", ip_proto="static") == ret


def test_managed_validate_errors():
    ret = {
        "name": "salt",
        "changes": {},
        "result": False,
        "comment": (
            "The following SLS configuration errors were "
            "detected:\n"
            "- First Error\n"
            "- Second Error"
        ),
    }
    mock_true = MagicMock(return_value=True)
    mock_validate = MagicMock(return_value=["First Error", "Second Error"])
    with patch.dict(win_network.__salt__, {"ip.is_enabled": mock_true}), patch.object(
        win_network, "_validate", mock_validate
    ):
        assert win_network.managed("salt", dns_proto="static", ip_proto="static") == ret


def test_managed_get_current_config_failed():
    ret = {
        "name": "salt",
        "changes": {},
        "result": False,
        "comment": "Unable to get current configuration for interface 'salt'",
    }
    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    mock_validate = MagicMock(return_value=[])
    with patch.dict(
        win_network.__salt__,
        {"ip.is_enabled": mock_true, "ip.get_interface": mock_false},
    ), patch.object(win_network, "_validate", mock_validate):

        assert win_network.managed("salt", dns_proto="dhcp", ip_proto="dhcp") == ret


def test_managed_test_true_no_changes():
    ret = {
        "name": "salt",
        "changes": {},
        "result": True,
        "comment": "Interface 'salt' is up to date",
    }
    mock_true = MagicMock(return_value=True)
    mock_validate = MagicMock(return_value=[])
    mock_get_int = MagicMock(
        return_value={
            "DHCP enabled": "yes",
            "DNS servers configured through DHCP": "192.168.0.10",
        }
    )
    with patch.dict(
        win_network.__salt__,
        {"ip.is_enabled": mock_true, "ip.get_interface": mock_get_int},
    ), patch.dict(win_network.__opts__, {"test": True}), patch.object(
        win_network, "_validate", mock_validate
    ):
        assert win_network.managed("salt", dns_proto="dhcp", ip_proto="dhcp") == ret


def test_managed_test_true_changes():
    ret = {
        "name": "salt",
        "changes": {},
        "result": None,
        "comment": (
            "The following changes will be made to interface "
            "'salt':\n"
            "- DNS protocol will be changed to: dhcp"
        ),
    }
    mock_true = MagicMock(return_value=True)
    mock_validate = MagicMock(return_value=[])
    mock_get_int = MagicMock(
        return_value={
            "DHCP enabled": "no",
            "Statically Configured DNS Servers": "192.168.0.10",
        }
    )
    with patch.dict(
        win_network.__salt__,
        {"ip.is_enabled": mock_true, "ip.get_interface": mock_get_int},
    ), patch.dict(win_network.__opts__, {"test": True}), patch.object(
        win_network, "_validate", mock_validate
    ):

        assert win_network.managed("salt", dns_proto="dhcp", ip_proto="dhcp") == ret


def test_managed_failed():
    ret = {
        "name": "salt",
        "changes": {},
        "result": False,
        "comment": "Failed to set desired configuration settings for interface 'salt'",
    }
    mock_true = MagicMock(return_value=True)
    mock_validate = MagicMock(return_value=[])
    mock_get_int = MagicMock(
        return_value={
            "DHCP enabled": "no",
            "Statically Configured DNS Servers": "192.168.0.10",
        }
    )
    with patch.dict(
        win_network.__salt__,
        {
            "ip.is_enabled": mock_true,
            "ip.get_interface": mock_get_int,
            "ip.set_dhcp_dns": mock_true,
            "ip.set_dhcp_ip": mock_true,
        },
    ), patch.dict(win_network.__opts__, {"test": False}), patch.object(
        win_network, "_validate", mock_validate
    ):
        assert win_network.managed("salt", dns_proto="dhcp", ip_proto="dhcp") == ret


def test_managed():
    ret = {
        "name": "salt",
        "changes": {
            "DHCP enabled": {"new": "yes", "old": "no"},
            "DNS servers configured through DHCP": {"new": "192.168.0.10", "old": ""},
            "Statically Configured DNS Servers": {"new": "", "old": "192.168.0.10"},
        },
        "result": True,
        "comment": "Successfully updated configuration for interface 'salt'",
    }
    mock_true = MagicMock(return_value=True)
    mock_validate = MagicMock(return_value=[])
    mock_get_int = MagicMock(
        side_effect=[
            {
                "DHCP enabled": "no",
                "Statically Configured DNS Servers": "192.168.0.10",
            },
            {
                "DHCP enabled": "yes",
                "DNS servers configured through DHCP": "192.168.0.10",
            },
        ]
    )
    with patch.dict(
        win_network.__salt__,
        {
            "ip.is_enabled": mock_true,
            "ip.get_interface": mock_get_int,
            "ip.set_dhcp_dns": mock_true,
            "ip.set_dhcp_ip": mock_true,
        },
    ), patch.dict(win_network.__opts__, {"test": False}), patch.object(
        win_network, "_validate", mock_validate
    ):
        assert win_network.managed("salt", dns_proto="dhcp", ip_proto="dhcp") == ret


def test_managed_static_dns_clear():
    expected = {
        "name": "salt",
        "changes": {
            "Statically Configured DNS Servers": {"new": "None", "old": "192.168.0.10"}
        },
        "result": True,
        "comment": "Successfully updated configuration for interface 'salt'",
    }
    mock_true = MagicMock(return_value=True)
    mock_validate = MagicMock(return_value=[])
    mock_get_int = MagicMock(
        side_effect=[
            {
                "DHCP enabled": "no",
                "Statically Configured DNS Servers": "192.168.0.10",
            },
            {"DHCP enabled": "no", "Statically Configured DNS Servers": "None"},
        ]
    )
    with patch.dict(
        win_network.__salt__,
        {
            "ip.is_enabled": mock_true,
            "ip.get_interface": mock_get_int,
            "ip.set_static_dns": mock_true,
        },
    ), patch.dict(win_network.__opts__, {"test": False}), patch.object(
        win_network, "_validate", mock_validate
    ):
        ret = win_network.managed(
            "salt", dns_proto="static", dns_servers=[], ip_proto="dhcp"
        )
        assert ret == expected


def test_managed_static_dns():
    expected = {
        "name": "salt",
        "changes": {
            "Statically Configured DNS Servers": {"new": "192.168.0.10", "old": "None"}
        },
        "result": True,
        "comment": "Successfully updated configuration for interface 'salt'",
    }
    mock_true = MagicMock(return_value=True)
    mock_validate = MagicMock(return_value=[])
    mock_get_int = MagicMock(
        side_effect=[
            {"DHCP enabled": "no", "Statically Configured DNS Servers": "None"},
            {
                "DHCP enabled": "no",
                "Statically Configured DNS Servers": "192.168.0.10",
            },
        ]
    )
    with patch.dict(
        win_network.__salt__,
        {
            "ip.is_enabled": mock_true,
            "ip.get_interface": mock_get_int,
            "ip.set_static_dns": mock_true,
        },
    ), patch.dict(win_network.__opts__, {"test": False}), patch.object(
        win_network, "_validate", mock_validate
    ):
        ret = win_network.managed(
            "salt",
            dns_proto="static",
            dns_servers=["192.168.0.10"],
            ip_proto="dhcp",
        )
        assert ret == expected


def test_managed_static_dns_no_action():
    expected = {
        "name": "salt",
        "changes": {},
        "result": True,
        "comment": "Interface 'salt' is up to date",
    }
    mock_true = MagicMock(return_value=True)
    mock_validate = MagicMock(return_value=[])
    mock_get_int = MagicMock(
        return_value={
            "DHCP enabled": "no",
            "Statically Configured DNS Servers": "192.168.0.10",
        }
    )
    with patch.dict(
        win_network.__salt__,
        {
            "ip.is_enabled": mock_true,
            "ip.get_interface": mock_get_int,
            "ip.set_static_dns": mock_true,
        },
    ), patch.dict(win_network.__opts__, {"test": False}), patch.object(
        win_network, "_validate", mock_validate
    ):
        # Don't pass dns_servers
        ret = win_network.managed("salt", dns_proto="static", ip_proto="dhcp")
        assert ret == expected
        # Pass dns_servers=None
        ret = win_network.managed(
            "salt", dns_proto="static", dns_servers=None, ip_proto="dhcp"
        )
        assert ret == expected

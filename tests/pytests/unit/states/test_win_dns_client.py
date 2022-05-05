"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest
import salt.states.win_dns_client as win_dns_client
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_dns_client: {}}


def test_dns_exists():
    """
    Test to configure the DNS server list in the specified interface
    """
    ret = {"name": "salt", "changes": {}, "result": False, "comment": ""}
    with patch.dict(win_dns_client.__opts__, {"test": False}):
        ret.update(
            {
                "changes": {
                    "Servers Added": [],
                    "Servers Removed": [],
                    "Servers Reordered": [],
                },
                "comment": "servers entry is not a list !",
            }
        )
        assert win_dns_client.dns_exists("salt") == ret

        mock = MagicMock(return_value=[2, "salt"])
        with patch.dict(
            win_dns_client.__salt__, {"win_dns_client.get_dns_servers": mock}
        ):
            ret.update(
                {
                    "changes": {},
                    "comment": repr([2, "salt"]) + " are already configured",
                    "result": True,
                }
            )
            assert win_dns_client.dns_exists("salt", [2, "salt"]) == ret

            mock = MagicMock(side_effect=[False, True, True])
            with patch.dict(win_dns_client.__salt__, {"win_dns_client.add_dns": mock}):
                ret.update(
                    {
                        "comment": "Failed to add 1 as DNS server number 1",
                        "result": False,
                    }
                )
                assert win_dns_client.dns_exists("salt", [1, "salt"]) == ret

                mock = MagicMock(return_value=False)
                with patch.dict(
                    win_dns_client.__salt__, {"win_dns_client.rm_dns": mock}
                ):
                    ret.update(
                        {
                            "changes": {
                                "Servers Added": ["a"],
                                "Servers Removed": [],
                                "Servers Reordered": [],
                            },
                            "comment": "Failed to remove 2 from DNS server list",
                        }
                    )
                    assert win_dns_client.dns_exists("salt", ["a"], "a", 1) == ret

                ret.update({"comment": "DNS Servers have been updated", "result": True})
                assert win_dns_client.dns_exists("salt", ["a"]) == ret


def test_dns_dhcp():
    """
    Test to configure the DNS server list from DHCP Server
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(side_effect=["dhcp", "salt", "salt"])
    with patch.dict(win_dns_client.__salt__, {"win_dns_client.get_dns_config": mock}):
        ret.update(
            {"comment": "Local Area Connection already configured with DNS from DHCP"}
        )
        assert win_dns_client.dns_dhcp("salt") == ret

        with patch.dict(win_dns_client.__opts__, {"test": True}):
            ret.update(
                {
                    "comment": "",
                    "result": None,
                    "changes": {"dns": "configured from DHCP"},
                }
            )
            assert win_dns_client.dns_dhcp("salt") == ret

        with patch.dict(win_dns_client.__opts__, {"test": False}):
            mock = MagicMock(return_value=True)
            with patch.dict(win_dns_client.__salt__, {"win_dns_client.dns_dhcp": mock}):
                ret.update({"result": True})
                assert win_dns_client.dns_dhcp("salt") == ret


def test_primary_suffix():
    """
    Test to configure the global primary DNS suffix of a DHCP client.
    """
    ret = {"name": "salt", "changes": {}, "result": False, "comment": ""}
    ret.update({"comment": "'updates' must be a boolean value"})
    assert win_dns_client.primary_suffix("salt", updates="a") == ret

    mock = MagicMock(
        side_effect=[
            {"vdata": "a"},
            {"vdata": False},
            {"vdata": "b"},
            {"vdata": False},
        ]
    )
    with patch.dict(win_dns_client.__utils__, {"reg.read_value": mock}):
        ret.update({"comment": "No changes needed", "result": True})
        assert win_dns_client.primary_suffix("salt", "a") == ret

        mock = MagicMock(return_value=True)
        with patch.dict(win_dns_client.__utils__, {"reg.set_value": mock}):
            ret.update(
                {
                    "changes": {"new": {"suffix": "a"}, "old": {"suffix": "b"}},
                    "comment": "Updated primary DNS suffix (a)",
                }
            )
            assert win_dns_client.primary_suffix("salt", "a") == ret

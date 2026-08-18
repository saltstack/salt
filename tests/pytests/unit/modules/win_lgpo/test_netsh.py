import pytest

import salt.modules.win_lgpo as win_lgpo
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules():
    return {win_lgpo: {}}


def test_get_netsh_value():
    with patch.dict(win_lgpo.__context__, {"lgpo.netsh_data": {"domain": {}}}):
        win_lgpo._set_netsh_value("domain", "state", "State", "NotConfigured")
    with patch.dict(win_lgpo.__context__, {}):
        assert win_lgpo._get_netsh_value("domain", "State") == "NotConfigured"

    context = {
        "lgpo.netsh_data": {
            "domain": {
                "State": "ONContext",
                "Inbound": "NotConfigured",
                "Outbound": "NotConfigured",
                "LocalFirewallRules": "NotConfigured",
            },
        },
    }
    with patch.dict(win_lgpo.__context__, context):
        assert win_lgpo._get_netsh_value("domain", "State") == "ONContext"


def test_set_value_error():
    with pytest.raises(ValueError):
        win_lgpo._set_netsh_value("domain", "bad_section", "junk", "junk")


def test_set_value_firewall():
    mock_context = {"lgpo.netsh_data": {"domain": "junk"}}
    with patch(
        "salt.utils.win_lgpo_netsh.set_firewall_settings", MagicMock()
    ) as mock, patch.dict(win_lgpo.__context__, mock_context):
        win_lgpo._set_netsh_value(
            profile="domain",
            section="firewallpolicy",
            option="Inbound",
            value="spongebob",
        )
        mock.assert_called_once_with(
            profile="domain",
            inbound="spongebob",
            outbound=None,
            store="lgpo",
        )


def test_set_value_settings():
    mock_context = {"lgpo.netsh_data": {"domain": "junk"}}
    with patch(
        "salt.utils.win_lgpo_netsh.set_settings", MagicMock()
    ) as mock, patch.dict(win_lgpo.__context__, mock_context):
        win_lgpo._set_netsh_value(
            profile="domain",
            section="settings",
            option="spongebob",
            value="squarepants",
        )
        mock.assert_called_once_with(
            profile="domain",
            setting="spongebob",
            value="squarepants",
            store="lgpo",
        )


def test_set_value_state():
    mock_context = {"lgpo.netsh_data": {"domain": "junk"}}
    with patch("salt.utils.win_lgpo_netsh.set_state", MagicMock()) as mock, patch.dict(
        win_lgpo.__context__, mock_context
    ):
        win_lgpo._set_netsh_value(
            profile="domain",
            section="state",
            option="junk",
            value="spongebob",
        )
        mock.assert_called_once_with(
            profile="domain",
            state="spongebob",
            store="lgpo",
        )


def test_set_value_logging_filename():
    mock_context = {"lgpo.netsh_data": {"domain": "junk"}}
    with patch(
        "salt.utils.win_lgpo_netsh.set_logging_settings", MagicMock()
    ) as mock, patch.dict(win_lgpo.__context__, mock_context):
        win_lgpo._set_netsh_value(
            profile="domain",
            section="logging",
            option="FileName",
            value="Not configured",
        )
        mock.assert_called_once_with(
            profile="domain",
            setting="FileName",
            value="notconfigured",
            store="lgpo",
        )


def test_set_value_logging_log():
    mock_context = {"lgpo.netsh_data": {"domain": "junk"}}
    with patch(
        "salt.utils.win_lgpo_netsh.set_logging_settings", MagicMock()
    ) as mock, patch.dict(win_lgpo.__context__, mock_context):
        win_lgpo._set_netsh_value(
            profile="domain",
            section="logging",
            option="LogSpongebob",
            value="Junk",
        )
        mock.assert_called_once_with(
            profile="domain",
            setting="Spongebob",
            value="Junk",
            store="lgpo",
        )

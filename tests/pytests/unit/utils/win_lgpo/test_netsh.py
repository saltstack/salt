import pytest

import salt.utils.win_lgpo_netsh as win_lgpo_netsh
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


def test_get_settings_firewallpolicy_local():
    ret = win_lgpo_netsh.get_settings(
        profile="domain", section="firewallpolicy", store="local"
    )
    assert "Inbound" in ret
    assert "Outbound" in ret


def test_get_settings_firewallpolicy_lgpo():
    ret = win_lgpo_netsh.get_settings(
        profile="domain", section="firewallpolicy", store="lgpo"
    )
    assert "Inbound" in ret
    assert "Outbound" in ret


def test_get_settings_logging_local():
    ret = win_lgpo_netsh.get_settings(
        profile="domain", section="logging", store="local"
    )
    assert "FileName" in ret
    assert "LogAllowedConnections" in ret
    assert "LogDroppedConnections" in ret
    assert "MaxFileSize" in ret


def test_get_settings_logging_lgpo():
    ret = win_lgpo_netsh.get_settings(profile="domain", section="logging", store="lgpo")
    assert "FileName" in ret
    assert "LogAllowedConnections" in ret
    assert "LogDroppedConnections" in ret
    assert "MaxFileSize" in ret


def test_get_settings_settings_local():
    ret = win_lgpo_netsh.get_settings(
        profile="domain", section="settings", store="local"
    )
    assert "InboundUserNotification" in ret
    assert "LocalConSecRules" in ret
    assert "LocalFirewallRules" in ret
    assert "UnicastResponseToMulticast" in ret


def test_get_settings_settings_lgpo():
    ret = win_lgpo_netsh.get_settings(
        profile="domain", section="settings", store="lgpo"
    )
    assert "InboundUserNotification" in ret
    assert "LocalConSecRules" in ret
    assert "LocalFirewallRules" in ret
    assert "UnicastResponseToMulticast" in ret


def test_get_settings_state_local():
    ret = win_lgpo_netsh.get_settings(profile="domain", section="state", store="local")
    assert "State" in ret


def test_get_settings_state_lgpo():
    ret = win_lgpo_netsh.get_settings(profile="domain", section="state", store="lgpo")
    assert "State" in ret


def test_get_all_settings_local():
    ret = win_lgpo_netsh.get_all_settings(profile="domain", store="local")
    assert "Inbound" in ret
    assert "Outbound" in ret
    assert "FileName" in ret
    assert "LogAllowedConnections" in ret
    assert "LogDroppedConnections" in ret
    assert "MaxFileSize" in ret
    assert "InboundUserNotification" in ret
    assert "LocalConSecRules" in ret
    assert "LocalFirewallRules" in ret
    assert "UnicastResponseToMulticast" in ret
    assert "State" in ret


def test_get_all_settings_lgpo():
    ret = win_lgpo_netsh.get_all_settings(profile="domain", store="local")
    assert "Inbound" in ret
    assert "Outbound" in ret
    assert "FileName" in ret
    assert "LogAllowedConnections" in ret
    assert "LogDroppedConnections" in ret
    assert "MaxFileSize" in ret
    assert "InboundUserNotification" in ret
    assert "LocalConSecRules" in ret
    assert "LocalFirewallRules" in ret
    assert "UnicastResponseToMulticast" in ret
    assert "State" in ret


def test_get_all_profiles_local():
    ret = win_lgpo_netsh.get_all_profiles(store="local")
    assert "Domain Profile" in ret
    assert "Private Profile" in ret
    assert "Public Profile" in ret


def test_get_all_profiles_lgpo():
    ret = win_lgpo_netsh.get_all_profiles(store="lgpo")
    assert "Domain Profile" in ret
    assert "Private Profile" in ret
    assert "Public Profile" in ret


@pytest.mark.destructive_test
def test_set_firewall_settings_inbound_local():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="firewallpolicy", store="local"
    )["Inbound"]
    try:
        ret = win_lgpo_netsh.set_firewall_settings(
            profile="domain", inbound="allowinbound", store="local"
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store="local"
        )["Inbound"]
        assert new == "AllowInbound"
    finally:
        ret = win_lgpo_netsh.set_firewall_settings(
            profile="domain", inbound=current, store="local"
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_settings_inbound_local_notconfigured():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="firewallpolicy", store="local"
    )["Inbound"]
    try:
        pytest.raises(
            CommandExecutionError,
            win_lgpo_netsh.set_firewall_settings,
            profile="domain",
            inbound="notconfigured",
            store="local",
        )
    finally:
        ret = win_lgpo_netsh.set_firewall_settings(
            profile="domain", inbound=current, store="local"
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_settings_inbound_lgpo_notconfigured():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="firewallpolicy", store="lgpo"
    )["Inbound"]
    try:
        ret = win_lgpo_netsh.set_firewall_settings(
            profile="domain", inbound="notconfigured", store="lgpo"
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store="lgpo"
        )["Inbound"]
        assert new == "NotConfigured"
    finally:
        ret = win_lgpo_netsh.set_firewall_settings(
            profile="domain", inbound=current, store="lgpo"
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_settings_outbound_local():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="firewallpolicy", store="local"
    )["Outbound"]
    try:
        ret = win_lgpo_netsh.set_firewall_settings(
            profile="domain", outbound="allowoutbound", store="local"
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store="local"
        )["Outbound"]
        assert new == "AllowOutbound"
    finally:
        ret = win_lgpo_netsh.set_firewall_settings(
            profile="domain", outbound=current, store="local"
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_logging_allowed_local_enable():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="logging", store="local"
    )["LogAllowedConnections"]
    try:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain",
            setting="allowedconnections",
            value="enable",
            store="local",
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )["LogAllowedConnections"]
        assert new == "Enable"
    finally:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain",
            setting="allowedconnections",
            value=current,
            store="local",
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_logging_allowed_local_notconfigured():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="logging", store="local"
    )["LogAllowedConnections"]
    try:
        pytest.raises(
            CommandExecutionError,
            win_lgpo_netsh.set_logging_settings,
            profile="domain",
            setting="allowedconnections",
            value="notconfigured",
            store="local",
        )
    finally:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain",
            setting="allowedconnections",
            value=current,
            store="local",
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_logging_allowed_lgpo_notconfigured():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="logging", store="lgpo"
    )["LogAllowedConnections"]
    try:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain",
            setting="allowedconnections",
            value="notconfigured",
            store="lgpo",
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="lgpo"
        )["LogAllowedConnections"]
        assert new == "NotConfigured"
    finally:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain",
            setting="allowedconnections",
            value=current,
            store="lgpo",
        )
        assert ret is True


def test_set_firewall_logging_dropped_local_enable():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="logging", store="local"
    )["LogDroppedConnections"]
    try:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain",
            setting="droppedconnections",
            value="enable",
            store="local",
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )["LogDroppedConnections"]
        assert new == "Enable"
    finally:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain",
            setting="droppedconnections",
            value=current,
            store="local",
        )
        assert ret is True


def test_set_firewall_logging_filename_local():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="logging", store="local"
    )["FileName"]
    try:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain",
            setting="filename",
            value="C:\\Temp\\test.log",
            store="local",
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )["FileName"]
        assert new == "C:\\Temp\\test.log"
    finally:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain", setting="filename", value=current, store="local"
        )
        assert ret is True


def test_set_firewall_logging_maxfilesize_local():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="logging", store="local"
    )["MaxFileSize"]
    try:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain", setting="maxfilesize", value="16384", store="local"
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store="local"
        )["MaxFileSize"]
        assert new == 16384
    finally:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain", setting="maxfilesize", value=current, store="local"
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_settings_fwrules_local_enable():
    pytest.raises(
        CommandExecutionError,
        win_lgpo_netsh.set_settings,
        profile="domain",
        setting="localfirewallrules",
        value="enable",
        store="local",
    )


@pytest.mark.destructive_test
def test_set_firewall_settings_fwrules_lgpo_notconfigured():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="settings", store="lgpo"
    )["LocalFirewallRules"]
    try:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="localfirewallrules",
            value="notconfigured",
            store="lgpo",
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="lgpo"
        )["LocalFirewallRules"]
        assert new == "NotConfigured"
    finally:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="localfirewallrules",
            value=current,
            store="lgpo",
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_settings_consecrules_local_enable():
    pytest.raises(
        CommandExecutionError,
        win_lgpo_netsh.set_settings,
        profile="domain",
        setting="localconsecrules",
        value="enable",
        store="local",
    )


def test_set_firewall_settings_notification_local_enable():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="settings", store="local"
    )["InboundUserNotification"]
    try:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="inboundusernotification",
            value="enable",
            store="local",
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="local"
        )["InboundUserNotification"]
        assert new == "Enable"
    finally:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="inboundusernotification",
            value=current,
            store="local",
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_settings_notification_local_notconfigured():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="settings", store="local"
    )["InboundUserNotification"]
    try:
        pytest.raises(
            CommandExecutionError,
            win_lgpo_netsh.set_settings,
            profile="domain",
            setting="inboundusernotification",
            value="notconfigured",
            store="local",
        )
    finally:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="inboundusernotification",
            value=current,
            store="local",
        )
        assert ret is True


def test_set_firewall_settings_notification_lgpo_notconfigured():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="settings", store="lgpo"
    )["InboundUserNotification"]
    try:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="inboundusernotification",
            value="notconfigured",
            store="lgpo",
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="lgpo"
        )["InboundUserNotification"]
        assert new == "NotConfigured"
    finally:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="inboundusernotification",
            value=current,
            store="lgpo",
        )
        assert ret is True


def test_set_firewall_settings_unicast_local_disable():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="settings", store="local"
    )["UnicastResponseToMulticast"]
    try:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="unicastresponsetomulticast",
            value="disable",
            store="local",
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store="local"
        )["UnicastResponseToMulticast"]
        assert new == "Disable"
    finally:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="unicastresponsetomulticast",
            value=current,
            store="local",
        )
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_state_local_on():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="state", store="local"
    )["State"]
    try:
        ret = win_lgpo_netsh.set_state(profile="domain", state="off", store="local")
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store="local"
        )["State"]
        assert new == "OFF"
    finally:
        ret = win_lgpo_netsh.set_state(profile="domain", state=current, store="local")
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_state_local_notconfigured():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="state", store="local"
    )["State"]
    try:
        ret = win_lgpo_netsh.set_state(
            profile="domain",
            state="notconfigured",
            store="local",
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store="local"
        )["State"]
        assert new == "NotConfigured"
    finally:
        ret = win_lgpo_netsh.set_state(profile="domain", state=current, store="local")
        assert ret is True


@pytest.mark.destructive_test
def test_set_firewall_state_lgpo_notconfigured():
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="state", store="local"
    )["State"]
    try:
        ret = win_lgpo_netsh.set_state(
            profile="domain", state="notconfigured", store="lgpo"
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store="lgpo"
        )["State"]
        assert new == "NotConfigured"
    finally:
        ret = win_lgpo_netsh.set_state(profile="domain", state=current, store="lgpo")
        assert ret is True

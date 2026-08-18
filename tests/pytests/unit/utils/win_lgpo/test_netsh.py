import pytest

import salt.utils.win_lgpo_netsh as win_lgpo_netsh
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.mark.parametrize("store", ["local", "lgpo"])
def test_get_settings_firewallpolicy(store):
    ret = win_lgpo_netsh.get_settings(
        profile="domain", section="firewallpolicy", store=store
    )
    assert "Inbound" in ret
    assert "Outbound" in ret


@pytest.mark.parametrize("store", ["local", "lgpo"])
def test_get_settings_logging(store):
    ret = win_lgpo_netsh.get_settings(profile="domain", section="logging", store=store)
    assert "FileName" in ret
    assert "LogAllowedConnections" in ret
    assert "LogDroppedConnections" in ret
    assert "MaxFileSize" in ret


@pytest.mark.parametrize("store", ["local", "lgpo"])
def test_get_settings_settings(store):
    ret = win_lgpo_netsh.get_settings(profile="domain", section="settings", store=store)
    assert "InboundUserNotification" in ret
    assert "LocalConSecRules" in ret
    assert "LocalFirewallRules" in ret
    assert "UnicastResponseToMulticast" in ret


@pytest.mark.parametrize("store", ["local", "lgpo"])
def test_get_settings_state(store):
    ret = win_lgpo_netsh.get_settings(profile="domain", section="state", store=store)
    assert "State" in ret


@pytest.mark.parametrize("store", ["local", "lgpo"])
def test_get_all_settings(store):
    ret = win_lgpo_netsh.get_all_settings(profile="domain", store=store)
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


@pytest.mark.parametrize("store", ["local", "lgpo"])
def test_get_all_profiles(store):
    ret = win_lgpo_netsh.get_all_profiles(store=store)
    assert "Domain Profile" in ret
    assert "Private Profile" in ret
    assert "Public Profile" in ret


@pytest.mark.destructive_test
@pytest.mark.parametrize("store", ["local", "lgpo"])
@pytest.mark.parametrize(
    "inbound", ["allowinbound", "blockinbound", "blockinboundalways", "notconfigured"]
)
def test_set_firewall_settings_inbound(store, inbound):
    if inbound == "notconfigured" and store == "local":
        pytest.raises(
            CommandExecutionError,
            win_lgpo_netsh.set_firewall_settings,
            profile="domain",
            inbound=inbound,
            store=store,
        )
    else:
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store=store
        )["Inbound"]
        try:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", inbound=inbound, store=store
            )
            assert ret is True
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="firewallpolicy", store=store
            )["Inbound"]
            assert new.lower() == inbound
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", inbound=current, store=store
            )
            assert ret is True


@pytest.mark.destructive_test
@pytest.mark.parametrize("store", ["local", "lgpo"])
@pytest.mark.parametrize(
    "outbound", ["allowoutbound", "blockoutbound", "notconfigured"]
)
def test_set_firewall_settings_outbound(store, outbound):
    if outbound == "notconfigured" and store == "local":
        pytest.raises(
            CommandExecutionError,
            win_lgpo_netsh.set_firewall_settings,
            profile="domain",
            inbound=outbound,
            store=store,
        )
    else:
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="firewallpolicy", store=store
        )["Outbound"]
        try:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", outbound=outbound, store=store
            )
            assert ret is True
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="firewallpolicy", store=store
            )["Outbound"]
            assert new.lower() == outbound
        finally:
            ret = win_lgpo_netsh.set_firewall_settings(
                profile="domain", outbound=current, store=store
            )
            assert ret is True


@pytest.mark.destructive_test
@pytest.mark.parametrize("store", ["local", "lgpo"])
@pytest.mark.parametrize("setting", ["allowedconnections", "droppedconnections"])
@pytest.mark.parametrize("value", ["enable", "disable", "notconfigured"])
def test_set_firewall_logging_connections(store, setting, value):
    if value == "notconfigured" and store == "local":
        pytest.raises(
            CommandExecutionError,
            win_lgpo_netsh.set_logging_settings,
            profile="domain",
            setting=setting,
            value=value,
            store=store,
        )
    else:
        setting_map = {
            "allowedconnections": "LogAllowedConnections",
            "droppedconnections": "LogDroppedConnections",
        }
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store=store
        )[setting_map[setting]]
        try:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting=setting,
                value=value,
                store=store,
            )
            assert ret is True
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="logging", store=store
            )[setting_map[setting]]
            assert new.lower() == value
        finally:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain",
                setting=setting,
                value=current,
                store=store,
            )
            assert ret is True


@pytest.mark.destructive_test
@pytest.mark.parametrize("store", ["local", "lgpo"])
@pytest.mark.parametrize("value", ["C:\\Temp\\test.log", "notconfigured"])
def test_set_firewall_logging_filename(store, value):
    current = win_lgpo_netsh.get_settings(
        profile="domain", section="logging", store=store
    )["FileName"]
    try:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain",
            setting="filename",
            value=value,
            store=store,
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store=store
        )["FileName"]
        assert new.lower() == value.lower()
    finally:
        ret = win_lgpo_netsh.set_logging_settings(
            profile="domain", setting="filename", value=current, store=store
        )
        assert ret is True


@pytest.mark.destructive_test
@pytest.mark.parametrize("store", ["local", "lgpo"])
@pytest.mark.parametrize("value", ["16384", "notconfigured"])
def test_set_firewall_logging_maxfilesize(store, value):
    if value == "notconfigured":
        pytest.raises(
            CommandExecutionError,
            win_lgpo_netsh.set_logging_settings,
            profile="domain",
            setting="maxfilesize",
            value=value,
            store=store,
        )
    else:
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="logging", store=store
        )["MaxFileSize"]
        try:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain", setting="maxfilesize", value=value, store=store
            )
            assert ret is True
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="logging", store=store
            )["MaxFileSize"]
            assert new == int(value)
        finally:
            ret = win_lgpo_netsh.set_logging_settings(
                profile="domain", setting="maxfilesize", value=current, store=store
            )
            assert ret is True


@pytest.mark.destructive_test
@pytest.mark.parametrize("store", ["local", "lgpo"])
@pytest.mark.parametrize(
    "setting",
    ["localconsecrules", "inboundusernotification", "unicastresponsetomulticast"],
)
@pytest.mark.parametrize("value", ["enable", "disable", "notconfigured"])
def test_set_firewall_settings(store, setting, value):
    setting_map = {
        "localconsecrules": "LocalConSecRules",
        "inboundusernotification": "InboundUserNotification",
        "unicastresponsetomulticast": "UnicastResponseToMulticast",
    }
    if value == "notconfigured" and store == "local":
        pytest.raises(
            CommandExecutionError,
            win_lgpo_netsh.set_settings,
            profile="domain",
            setting=setting,
            value=value,
            store=store,
        )
    else:
        current = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store=store
        )[setting_map[setting]]
        try:
            ret = win_lgpo_netsh.set_settings(
                profile="domain",
                setting=setting,
                value=value,
                store=store,
            )
            assert ret is True
            new = win_lgpo_netsh.get_settings(
                profile="domain", section="settings", store=store
            )[setting_map[setting]]
            assert new.lower() == value
        finally:
            if current != "notconfigured":
                ret = win_lgpo_netsh.set_settings(
                    profile="domain",
                    setting=setting,
                    value=current,
                    store=store,
                )
            assert ret is True


@pytest.mark.destructive_test
@pytest.mark.parametrize("store", ["local", "lgpo"])
@pytest.mark.parametrize("state", ["on", "off", "notconfigured"])
def test_set_firewall_state(store, state):
    current_state = win_lgpo_netsh.get_settings(
        profile="domain", section="state", store=store
    )["State"]
    try:
        ret = win_lgpo_netsh.set_state(profile="domain", state=state, store=store)
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store=store
        )["State"]
        assert new.lower() == state.lower()
    finally:
        win_lgpo_netsh.set_state(profile="domain", state=current_state, store=store)


@pytest.mark.destructive_test
@pytest.mark.parametrize("store", ["local", "lgpo"])
@pytest.mark.parametrize("allow_inbound", ["enable", "disable"])
@pytest.mark.parametrize("state", ["on", "off", "notconfigured"])
def test_set_firewall_state_allow_inbound(store, allow_inbound, state):
    current_state = win_lgpo_netsh.get_settings(
        profile="domain", section="state", store=store
    )["State"]
    current_local_fw_rules = win_lgpo_netsh.get_settings(
        profile="domain", section="settings", store="lgpo"
    )["LocalFirewallRules"]
    try:
        ret = win_lgpo_netsh.set_settings(
            profile="domain",
            setting="localfirewallrules",
            value=allow_inbound,
            store=store,
        )
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="settings", store=store
        )["LocalFirewallRules"]
        assert new.lower() == allow_inbound.lower()
        ret = win_lgpo_netsh.set_state(profile="domain", state=state, store=store)
        assert ret is True
        new = win_lgpo_netsh.get_settings(
            profile="domain", section="state", store=store
        )["State"]
        assert new.lower() == state.lower()
    finally:
        if current_local_fw_rules.lower() != "notconfigured":
            win_lgpo_netsh.set_settings(
                profile="domain",
                setting="localfirewallrules",
                value=current_local_fw_rules,
                store=store,
            )
        win_lgpo_netsh.set_state(profile="domain", state=current_state, store=store)

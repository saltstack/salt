import time

import pytest


def _select_active_interface(interfaces):
    candidates = []
    for name, data in interfaces.items():
        if not data or name.lower().startswith("loopback"):
            continue
        flags = {flag.upper() for flag in data.get("flags", [])}
        is_up = data.get("up")
        if flags:
            if "UP" not in flags:
                continue
        elif is_up is False:
            continue
        candidates.append(name)
    if not candidates:
        pytest.skip("No active non-loopback interfaces available")
    return candidates[0]


def _wait_for_dns_state(
    salt_call_cli, interface, dns, *, present, timeout=30, interval=1
):
    deadline = time.time() + timeout
    last_servers = []
    while time.time() < deadline:
        ret = salt_call_cli.run("win_dns_client.get_dns_servers", interface=interface)
        assert ret.returncode == 0
        servers = ret.data or []
        last_servers = servers
        if present and dns in servers:
            return
        if not present and dns not in servers:
            return
        time.sleep(interval)

    expectation = "present" if present else "absent"
    pytest.fail(
        f"DNS server {dns} expected to be {expectation} on {interface}. "
        f"Last observed servers: {last_servers}"
    )


@pytest.mark.skip_unless_on_windows
@pytest.mark.windows_whitelisted
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_add_remove_dns(salt_call_cli):
    """Ensure a DNS server can be added and removed from a Windows interface."""

    ret = salt_call_cli.run("network.interfaces")
    assert ret.returncode == 0
    interfaces = ret.data or {}
    if not interfaces:
        pytest.skip("This test requires a network interface")

    interface = _select_active_interface(interfaces)
    dns = "8.8.8.8"

    ret = salt_call_cli.run("win_dns_client.get_dns_servers", interface=interface)
    assert ret.returncode == 0
    current_servers = ret.data or []
    index = len(current_servers) + 1

    ret = salt_call_cli.run("win_dns_client.add_dns", dns, interface, index=index)
    assert ret.returncode == 0
    assert ret.data is True

    _wait_for_dns_state(salt_call_cli, interface, dns, present=True)

    ret = salt_call_cli.run("win_dns_client.rm_dns", dns, interface=interface)
    assert ret.returncode == 0
    assert ret.data is True

    _wait_for_dns_state(salt_call_cli, interface, dns, present=False)

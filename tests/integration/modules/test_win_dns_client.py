import time

import pytest

from tests.support.case import ModuleCase


@pytest.mark.skip_unless_on_windows
@pytest.mark.windows_whitelisted
class WinDNSTest(ModuleCase):
    """
    Test for salt.modules.win_dns_client
    """

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_add_remove_dns(self):
        """
        Test add and removing a dns server
        """
        # Get a list of interfaces on the system
        interfaces = self.run_function("network.interfaces")
        candidates = [
            name
            for name, data in interfaces.items()
            if data
            and data.get("up", True)
            and not name.lower().startswith("Loopback".lower())
        ]
        if not candidates:
            pytest.skip("This test requires a network interface")

        interface = candidates[0]
        dns = "8.8.8.8"

        original_servers = self.run_function(
            "win_dns_client.get_dns_servers", interface=interface
        )
        index = len(original_servers) + 1 if original_servers else 1
        # add dns server
        self.assertTrue(
            self.run_function("win_dns_client.add_dns", [dns, interface], index=index)
        )

        self._wait_for_dns_state(interface, dns, present=True)

        # remove dns server
        self.assertTrue(
            self.run_function("win_dns_client.rm_dns", [dns], interface=interface)
        )

        self._wait_for_dns_state(interface, dns, present=False)

    def _wait_for_dns_state(self, interface, dns, *, present, timeout=30, interval=1):
        """
        Poll the DNS servers list until the expected state is observed.
        """
        end_time = time.time() + timeout
        last_servers = None
        while time.time() < end_time:
            servers = self.run_function(
                "win_dns_client.get_dns_servers", interface=interface
            )
            last_servers = servers
            if present and dns in servers:
                return
            if not present and dns not in servers:
                return
            time.sleep(interval)

        expectation = "present" if present else "absent"
        self.fail(
            f"DNS server {dns} expected to be {expectation} in {interface}. "
            f"Last observed servers: {last_servers}"
        )

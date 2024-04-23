import logging
import subprocess
import time

import pytest

log = logging.getLogger(__name__)


@pytest.mark.skip_unless_on_linux
def test_dns_change(master, minion, salt_cli, etc_hosts, caplog):
    """
    Verify a minion will pick up a master's dns change if it's been disconnected.
    """

    etc_hosts.write_text(f"{etc_hosts.orig_text}\n172.16.0.1    master.local")

    with minion.started(start_timeout=180):
        with caplog.at_level(logging.INFO):
            ret = salt_cli.run("test.ping", minion_tgt="minion")
            assert ret.returncode == 0
            etc_hosts.write_text(f"{etc_hosts.orig_text}\n127.0.0.1    master.local")
            subprocess.check_output(["ip", "addr", "del", "172.16.0.1/32", "dev", "lo"])
            time.sleep(15)
            assert (
                "Master ip address changed from 172.16.0.1 to 127.0.0.1" in caplog.text
            )
            ret = salt_cli.run("test.ping", minion_tgt="minion")
            assert ret.returncode == 0

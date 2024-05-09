import logging
import subprocess
import time

import pytest

log = logging.getLogger(__name__)


@pytest.mark.skip_unless_on_linux
def test_multimaster_dns(
    salt_mm_master_1,
    salt_mm_minion_1,
    mm_master_1_salt_cli,
    etc_hosts,
    caplog,
    master_alive_interval,
):
    """
    Verify a minion configured with multimaster hot/hot will pick up a master's
    dns change if it's been disconnected.
    """

    etc_hosts.write_text(
        f"{etc_hosts.orig_text}\n172.16.0.1    master1.local master2.local"
    )

    log.info("Added hosts record for master1.local and master2.local")

    with salt_mm_minion_1.started(start_timeout=180):
        with caplog.at_level(logging.INFO):
            ret = mm_master_1_salt_cli.run("test.ping", minion_tgt="mm-minion-1")
            assert ret.returncode == 0
            etc_hosts.write_text(
                f"{etc_hosts.orig_text}\n127.0.0.1    master1.local master2.local"
            )
            log.info("Changed hosts record for master1.local and master2.local")
            subprocess.check_output(["ip", "addr", "del", "172.16.0.1/32", "dev", "lo"])
            log.info("Removed secondary master IP address.")
            # Wait for the minion's master_alive_interval, adding a second for
            # reliablity.
            time.sleep(master_alive_interval + 1)
            assert (
                "Master ip address changed from 172.16.0.1 to 127.0.0.1" in caplog.text
            )
            ret = mm_master_1_salt_cli.run("test.ping", minion_tgt="mm-minion-1")
            assert ret.returncode == 0
            assert (
                "Master ip address changed from 172.16.0.1 to 127.0.0.1" in caplog.text
            )

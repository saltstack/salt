import logging
import subprocess
import time

import pytest
from pytestshellutils.exceptions import FactoryTimeout

log = logging.getLogger(__name__)


def assert_minion_responds(salt_cli, minion_id, timeout):
    deadline = time.monotonic() + timeout
    last_response = None
    while time.monotonic() < deadline:
        try:
            result = salt_cli.run("test.ping", "--timeout=5", minion_tgt=minion_id)
        except FactoryTimeout as exc:
            last_response = exc
        else:
            if result.returncode == 0 and result.data is True:
                return
            last_response = result
        time.sleep(1)
    pytest.fail(
        f"{minion_id} did not answer {salt_cli.id} within {timeout}s: {last_response}"
    )


@pytest.fixture
def orig_address(etc_hosts):
    try:
        etc_hosts.write_text(
            f"{etc_hosts.orig_text}\n172.16.0.1    master1.local master2.local"
        )
        yield
    finally:
        subprocess.run(["ip", "addr", "del", "172.16.0.1/32", "dev", "lo"], check=False)


@pytest.mark.skip_unless_on_linux
def test_multimaster_dns(
    orig_address,
    salt_mm_master_1,
    salt_mm_master_2,
    salt_mm_minion_1,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
    etc_hosts,
    event_listener,
    caplog,
    master_alive_interval,
):
    """
    Verify a minion configured with multimaster hot/hot will pick up a master's
    dns change if it's been disconnected.
    """

    log.info("Added hosts record for master1.local and master2.local")

    minion_id = salt_mm_minion_1.id
    wait_time = master_alive_interval * 6
    master_clis = (mm_master_1_salt_cli, mm_master_2_salt_cli)
    with salt_mm_minion_1.started(start_timeout=180), caplog.at_level(logging.INFO):
        for salt_cli in master_clis:
            assert_minion_responds(salt_cli, minion_id, wait_time)
        etc_hosts.write_text(
            f"{etc_hosts.orig_text}\n127.0.0.1    master1.local master2.local"
        )
        address_changed_at = time.time()
        subprocess.run(["ip", "addr", "del", "172.16.0.1/32", "dev", "lo"], check=True)

        start_tag = f"salt/minion/{minion_id}/start"
        start_events = event_listener.wait_for_events(
            [(salt_mm_master_1.id, start_tag), (salt_mm_master_2.id, start_tag)],
            timeout=wait_time,
            after_time=address_changed_at,
        )
        assert not start_events.missed
        for salt_cli in master_clis:
            assert_minion_responds(salt_cli, minion_id, wait_time)
        assert "Master ip address changed from 172.16.0.1 to 127.0.0.1" in caplog.text

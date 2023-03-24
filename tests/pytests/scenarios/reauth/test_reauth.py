import logging
import os
import threading
import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def timeout():
    return int(os.environ.get("SALT_CI_REAUTH_MASTER_WAIT", 100))


def test_reauth(salt_cli, salt_minion, salt_master, timeout, event_listener):
    # Make sure they can communicate
    assert salt_cli.run("test.ping", minion_tgt=salt_minion.id).data is True
    # Stop the master and minion
    salt_master.terminate()
    salt_minion.terminate()
    log.debug(
        "Master and minion stopped for reauth test, waiting for %s seconds", timeout
    )
    log.debug("Restarting the reauth minion")

    # We need to have the minion attempting to start in a different thread
    # when we try to start the master
    def minion_func():
        start = time.time()
        with salt_minion.started(start_timeout=timeout * 2):
            new_start = time.time()
            while time.time() < new_start + (timeout * 2):
                if event_listener.get_events(
                    [(salt_master.id, f"salt/job/*/ret/{salt_minion.id}")],
                    after_time=start,
                ):
                    break
                time.sleep(5)

    minion_thread = threading.Thread(target=minion_func)
    minion_thread.start()
    time.sleep(timeout)
    log.debug("Restarting the reauth master")
    salt_master.start()
    assert salt_cli.run("test.ping", minion_tgt=salt_minion.id).data is True
    minion_thread.join()

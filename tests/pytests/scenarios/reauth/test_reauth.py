import logging
import os
import threading
import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.timeout(900),
]

log = logging.getLogger(__name__)


def minion_func(salt_minion, stop_event):
    log.debug("minion_func started")
    try:
        # Manual start to avoid flaky readiness checks on Windows
        salt_minion.start()
        log.debug("minion_func: minion process started, waiting for stop_event")
        while not stop_event.is_set():
            if not salt_minion.is_running():
                log.error("minion_func: minion process died unexpectedly")
                break
            time.sleep(1)
        log.debug("minion_func: stop_event set or process died")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        log.exception("minion_func: exception occurred: %s", exc)
    finally:
        salt_minion.terminate()
    log.debug("minion_func finished")


@pytest.fixture(scope="module")
def timeout():
    return int(os.environ.get("SALT_CI_REAUTH_MASTER_WAIT", 60))


def test_reauth(salt_cli, salt_minion, salt_master, timeout, event_listener):
    # Make sure they can communicate
    assert salt_cli.run("test.ping", minion_tgt=salt_minion.id).data is True
    # Stop the master and minion
    salt_master.terminate()
    salt_minion.terminate()

    # Phase 1: Resource Isolation and Cleanup
    # Allow Windows to release file and registry handles
    log.debug("Master and minion stopped, waiting 10s for handle release")
    time.sleep(10)

    stop_event = threading.Event()
    # We need to have the minion attempting to start in a different process
    # when we try to start the master
    minion_proc = threading.Thread(target=minion_func, args=(salt_minion, stop_event))
    minion_proc.start()
    log.debug("Restarting the reauth minion thread")

    time.sleep(timeout)
    log.debug("Restarting the reauth master")
    start = time.time()
    salt_master.start()

    log.debug("Waiting for minion start event")
    # The minion might take some time to re-auth and send the start event
    event_listener.wait_for_events(
        [(salt_master.id, f"salt/minion/{salt_minion.id}/start")],
        after_time=start,
        timeout=timeout * 3,
    )

    # Phase 4: Diagnostic Validation
    # Allow master to finish its post-startup load (grains refresh, etc)
    log.debug("Minion start event received, allowing master to settle for 10s")
    time.sleep(10)

    log.debug("Pinging minion with retries...")
    # Phase 3: CLI Resilience
    # Use a long timeout and retries to handle re-auth latency on Windows
    # Pass _timeout to override the factory-level kill timer
    for attempt in range(1, 4):
        log.debug("Ping attempt %s/3", attempt)
        ret = salt_cli.run(
            "--timeout=60", "test.ping", minion_tgt=salt_minion.id, _timeout=120
        )
        log.debug("Ping result: %s", ret)
        if ret and ret.data is True:
            break
        time.sleep(5)
    else:
        pytest.fail("Minion failed to respond to ping after 3 attempts")

    log.debug("Ping successful, stopping minion thread")
    stop_event.set()
    minion_proc.join()

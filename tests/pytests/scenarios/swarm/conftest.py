import logging
import os
import threading
import time
from contextlib import ExitStack

import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


def _cleanup_minion(minion, start_time, cleanup_timeout):
    """Clean up a single minion with timeout protection."""
    try:
        if minion.is_running():
            minion.terminate()
            # Wait up to 2 seconds per minion for graceful shutdown
            wait_time = 2.0
            elapsed = time.time() - start_time
            if elapsed + wait_time > cleanup_timeout:
                wait_time = max(0.1, cleanup_timeout - elapsed)
            try:
                if hasattr(minion.impl, "_process") and minion.impl._process:
                    if minion.impl._process.is_running():
                        minion.impl._process.wait(timeout=wait_time)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                # If wait fails or times out, try to kill it
                log.warning("Failed to wait for minion process to terminate: %s", exc)
                try:
                    if hasattr(minion.impl, "_process") and minion.impl._process:
                        if minion.impl._process.is_running():
                            minion.impl._process.kill()
                except Exception as kill_exc:  # pylint: disable=broad-exception-caught
                    log.warning(
                        "Failed to kill minion process after wait failure: %s", kill_exc
                    )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # If termination fails, try to kill the process directly
        log.warning("Failed to terminate minion, attempting direct kill: %s", exc)
        try:
            if hasattr(minion.impl, "_process") and minion.impl._process:
                if minion.impl._process.is_running():
                    minion.impl._process.kill()
        except Exception as kill_exc:  # pylint: disable=broad-exception-caught
            log.warning("Failed to kill minion process directly: %s", kill_exc)


@pytest.fixture(scope="package")
def salt_master_factory(salt_factories):
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        random_string("swarm-master-"),
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        overrides=config_overrides,
    )
    return factory


@pytest.fixture(scope="package")
def salt_master(salt_master_factory):
    with salt_master_factory.started():
        yield salt_master_factory


@pytest.fixture(scope="package")
def salt_minion(salt_minion_factory):
    with salt_minion_factory.started():
        yield salt_minion_factory


@pytest.fixture(scope="package")
def salt_key_cli(salt_master):
    assert salt_master.is_running()
    return salt_master.salt_key_cli()


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    assert salt_master.is_running()
    return salt_master.salt_cli()


@pytest.fixture(scope="package")
def _minion_count(grains):
    # Allow this to be changed via an environment variable if needed
    env_count = os.environ.get("SALT_CI_MINION_SWARM_COUNT")
    if env_count is not None:
        return int(env_count)
    # Default to 15 swarm minions
    count = 15
    if grains["osarch"] != "aarch64":
        return count
    if grains["os"] != "Amazon":
        return count
    if grains["osmajorrelease"] != 2023:
        return count
    # Looks like the test suite on Amazon 2023 under ARM64 get's OOM killed
    # Let's reduce the number of swarm minions
    return count - 5


@pytest.fixture(scope="package")
def minion_swarm(salt_master, _minion_count):
    assert salt_master.is_running()
    minions = []
    # We create and arbitrarily tall context stack to register the
    # minions stop mechanism callback
    with ExitStack() as stack:
        for idx in range(_minion_count):
            minion_factory = salt_master.salt_minion_daemon(
                random_string(f"swarm-minion-{idx}-"),
                extra_cli_arguments_after_first_start_failure=["--log-level=info"],
                overrides={
                    "fips_mode": FIPS_TESTRUN,
                    "encryption_algorithm": (
                        "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
                    ),
                    "signing_algorithm": (
                        "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
                    ),
                },
            )
            stack.enter_context(minion_factory.started())
            minions.append(minion_factory)
        for minion in minions:
            assert minion.is_running()
        try:
            yield minions
        finally:
            # Manual cleanup with timeout to prevent hangs on Debian 13
            # ExitStack cleanup can hang if minions don't terminate quickly.
            # We manually terminate minions before ExitStack tries to clean them up,
            # with timeout protection to prevent indefinite hangs.
            cleanup_timeout = 30  # 30 seconds total timeout for cleanup
            start_time = time.time()

            # Clean up minions in parallel threads to speed up cleanup
            # and prevent one hanging minion from blocking others
            threads = []
            for minion in reversed(minions):  # Reverse order like ExitStack
                if time.time() - start_time >= cleanup_timeout:
                    break
                thread = threading.Thread(
                    target=_cleanup_minion,
                    args=(minion, start_time, cleanup_timeout),
                    daemon=True,
                )
                thread.start()
                threads.append(thread)

            # Wait for all cleanup threads with timeout
            for thread in threads:
                remaining_time = max(0.1, cleanup_timeout - (time.time() - start_time))
                if remaining_time <= 0:
                    break
                thread.join(timeout=remaining_time)

            # Final check - force kill any remaining processes
            for minion in minions:
                try:
                    if minion.is_running():
                        if hasattr(minion.impl, "_process") and minion.impl._process:
                            if minion.impl._process.is_running():
                                minion.impl._process.kill()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    log.warning(
                        "Failed to force kill minion process during final cleanup: %s",
                        exc,
                    )

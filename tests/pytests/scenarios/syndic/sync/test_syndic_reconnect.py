# Regression test for #68915
"""
Integration test: syndic reconnects to Master of Masters after MoM restart.

Before the fix, Syndic.reconnect() did not invalidate the stale auth token
on the pub_channel before closing it.  When the ZeroMQ socket detected a
reconnection it would attempt to reuse the old token, causing authentication
to fail and leaving the syndic unable to forward jobs.

This test exercises the full MoM→syndic→minion topology with a real process
restart of the MoM, then asserts that a ``test.ping`` dispatched through the
MoM still reaches the downstream minion after the restart.

Why a functional/integration test rather than a unit test?
  The reconnect path involves ZeroMQ socket-monitor callbacks
  (``ZeroMQSocketMonitor.monitor_callback``) and asyncio scheduling
  (``asyncio.ensure_future``), which only fire inside a live event loop that
  owns a real ZMQ context.  Unit mocks cannot exercise the timing of the
  reconnect-triggered re-authentication handshake.
"""
import logging
import time

import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_on_fips_enabled_platform,
]


# ---------------------------------------------------------------------------
# Function-scoped fixtures — we need to be able to restart the MoM inside
# the test body, so we cannot share package-scope fixtures with the other
# tests in this directory.
# ---------------------------------------------------------------------------


@pytest.fixture
def mom(request, salt_factories):
    """Master of Masters — the top-level master."""
    config_defaults = {
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "auto_accept": True,
        "order_masters": True,
        "gather_job_timeout": 30,
        "timeout": 30,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        random_string("mom-"),
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def syndic(mom):
    """Syndic that connects to *mom*."""
    ret_port = mom.config["ret_port"]
    port = mom.config["publish_port"]
    addr = mom.config["interface"]

    config_defaults = {
        "transport": mom.config["transport"],
        "interface": "127.0.0.2",
        "publish_port": f"{port}",
    }
    master_overrides = {
        "interface": "127.0.0.2",
        "auto_accept": True,
        "syndic_master": f"{addr}",
        "syndic_master_port": f"{ret_port}",
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    minion_overrides = {
        "master": "127.0.0.2",
        "publish_port": f"{port}",
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = mom.salt_syndic_daemon(
        random_string("syndic-"),
        defaults=config_defaults,
        master_overrides=master_overrides,
        minion_overrides=minion_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(factory.minion.terminate)
    factory.after_terminate(factory.master.terminate)
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def minion(syndic):
    """Downstream minion connected to the syndic's internal master."""
    config_defaults = {
        "transport": syndic.config["transport"],
    }
    port = syndic.master.config["ret_port"]
    addr = syndic.master.config["interface"]
    config_overrides = {
        "master": f"{addr}:{port}",
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = syndic.master.salt_minion_daemon(
        random_string("minion-"),
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


def test_syndic_reconnects_after_mom_restart(mom, syndic, minion):
    """
    Regression test for #68915.

    Verify that after the Master of Masters (MoM) is restarted:

    1. The syndic re-establishes its ZeroMQ publish-channel connection and
       completes re-authentication (the fix invalidates the stale auth token
       before closing the channel so a fresh handshake is performed).
    2. A ``test.ping`` dispatched from the MoM reaches the downstream minion
       through the syndic and returns a truthy result.

    Without the fix, step 2 times out or returns an empty result because the
    syndic's reconnect attempt reuses a stale auth token and the MoM rejects
    the subscription.
    """
    salt_cli = mom.salt_cli(timeout=60)
    minion_id = minion.id
    syndic_id = syndic.id

    # Baseline: verify the topology is working before the restart.
    # Targeting "*" returns {syndic_id: True, minion_id: True} for a
    # syndic topology; the syndic itself acts as a pseudo-minion on the MoM.
    ret = salt_cli.run("test.ping", minion_tgt="*", _timeout=30)
    assert ret.returncode == 0, f"Baseline ping failed before MoM restart: {ret}"
    assert isinstance(ret.data, dict), f"Unexpected baseline result type: {ret.data!r}"
    assert (
        ret.data.get(minion_id) is True
    ), f"Downstream minion not responding in baseline: {ret.data}"

    log.info("Baseline ping passed. Restarting MoM (%s)…", mom.id)

    # Stop the MoM, pause briefly to let the syndic detect the disconnect,
    # then bring the MoM back up.
    with mom.stopped():
        log.info("MoM stopped. Waiting for syndic to detect the disconnect…")
        time.sleep(3)

    log.info("MoM restarted. Waiting for syndic to reconnect and re-authenticate…")

    # Give the syndic up to 120 s to reconnect, re-authenticate, and register
    # with the MoM before we send the post-restart ping.  The ZMQ reconnect
    # interval is randomised (recon_default + up to recon_max), so allow
    # generous time for the syndic to reconnect, re-authenticate with the
    # restarted MoM, and for the minion to relay job returns back through
    # the syndic.
    last_ret = None
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        last_ret = salt_cli.run("test.ping", minion_tgt="*", _timeout=20)
        if (
            last_ret.returncode == 0
            and isinstance(last_ret.data, dict)
            and last_ret.data.get(minion_id) is True
        ):
            log.info(
                "Post-restart ping succeeded after %.1f s",
                120 - (deadline - time.monotonic()),
            )
            break
        log.debug(
            "Post-restart ping attempt: returncode=%r data=%r",
            last_ret.returncode,
            last_ret.data,
        )
        time.sleep(5)
    else:
        pytest.fail(
            f"Syndic did not reconnect to MoM within 120 s after restart. "
            f"Last response: returncode={last_ret.returncode!r}, "
            f"data={last_ret.data!r}"
        )

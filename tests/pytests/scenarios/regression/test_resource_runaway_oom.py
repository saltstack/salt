"""
Regression sentinel for an observed salt-minion OOM under prolonged master
backpressure.

Drives a real salt-master + salt-minion via saltfactories with aggressive
retry knobs, fires several async jobs, stops the master while the returns
are pending so the minion's return-retry path executes against an
unresponsive master, then resumes the master and lets retries drain.

What this test asserts: the diagnostic log lines for that failure mode --
``Request timed out while waiting for a response`` and ``failed to return
the job information for job`` -- are emitted. That confirms the failure-mode
code paths are reachable and exercised end-to-end.

What this test does *not* assert: the actual memory leak. The original
incident saw the minion creep from ~95 MB to ~200 MB over hours of
error-looping. In a ~14-second CI window we measure tens of KB of RSS
growth per retry-exhausted job, which extrapolates to thousands of jobs to
reach the OOM. Any tight RSS/child threshold here would either be flaky on
allocator noise or unreachable in CI time. The measurements are logged
unconditionally so a future regression that *does* leak fast enough to show
up in 14 s will be visible in the warning log.
"""

import logging
import pathlib
import time

import psutil
import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
]

LOG_PHRASE_FAILED_TO_RETURN = "failed to return the job information for job"
LOG_PHRASE_REQUEST_TIMEOUT = "Request timed out while waiting for a response"

# Aggressive retry knobs matching the original incident: the affected
# appliance ran timer=30/max=60/tries=5. We keep the semantics but scale
# timers down so a CI run finishes inside a couple of minutes.
NSX_MINION_RETRY_OVERRIDES = {
    "return_retry_timer": 1,
    "return_retry_timer_max": 2,
    "return_retry_tries": 3,
    "request_channel_timeout": 4,
    "request_channel_tries": 3,
}

# Concurrent async jobs we fire before stopping the master.
N_PENDING_JOBS = 6


@pytest.fixture
def runaway_master(salt_factories):
    overrides = {
        "open_mode": True,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        random_string("runaway-master-"),
        overrides=overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture
def runaway_minion(runaway_master):
    overrides = dict(NSX_MINION_RETRY_OVERRIDES)
    overrides.update(
        {
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": ("OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"),
            "signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        }
    )
    factory = runaway_master.salt_minion_daemon(
        random_string("runaway-minion-"),
        overrides=overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, runaway_master, factory.id
    )
    with factory.started():
        yield factory


def _sample_minion(proc):
    return {
        "rss": proc.memory_info().rss,
        "children": len(proc.children(recursive=True)),
        "num_fds": proc.num_fds(),
    }


def test_return_retry_resource_runaway(runaway_master, runaway_minion):
    """
    Reproduce the diagnostic log signature of the master-backpressure
    failure mode and record minion RSS / child process counts for later
    inspection.
    """
    minion_pid = runaway_minion.pid
    assert minion_pid is not None, "could not get minion PID from factory"
    minion_proc = psutil.Process(minion_pid)
    log_file = pathlib.Path(runaway_minion.config["log_file"])

    salt_cli = runaway_master.salt_cli()

    # Warm up: confirm minion is responsive before we stress it.
    ping = salt_cli.run("test.ping", minion_tgt=runaway_minion.id)
    assert ping.data is True, f"minion did not respond to test.ping: {ping}"

    baseline = _sample_minion(minion_proc)

    # Fire several async jobs so the minion has work whose returns will need
    # to be retried once the master goes away. test.sleep gives us a job that
    # finishes inside the master-outage window.
    jids = []
    for _ in range(N_PENDING_JOBS):
        ret = salt_cli.run("test.sleep", "3", "--async", minion_tgt=runaway_minion.id)
        jids.append(ret.stdout.strip().split(" ")[-1])

    # Brief settle so the jobs are accepted and started on the minion.
    time.sleep(1)

    # Take down the master while jobs are running and their returns are
    # pending. With the NSX-style retry knobs, each return retries for up to
    # ~6 seconds before exhausting tries; outage must outlast that.
    outage_samples = []
    with runaway_master.stopped():
        # Sample once early so we capture during-outage state.
        time.sleep(2)
        outage_samples.append(_sample_minion(minion_proc))
        # Long enough for jobs to complete and for several return-retry
        # cycles to fail.
        time.sleep(12)
        outage_samples.append(_sample_minion(minion_proc))

    # Master is back; let any lingering retries drain.
    time.sleep(5)
    settled = _sample_minion(minion_proc)

    log_text = log_file.read_text(errors="replace", encoding="utf-8")

    # ----- Sanity: confirm we actually reproduced the failure mode. -----
    assert LOG_PHRASE_REQUEST_TIMEOUT in log_text, (
        f"expected transport timeout log line {LOG_PHRASE_REQUEST_TIMEOUT!r} "
        f"in minion log {log_file}; harness did not stress the transport."
    )
    assert LOG_PHRASE_FAILED_TO_RETURN in log_text, (
        f"expected return-retry exhaustion log line "
        f"{LOG_PHRASE_FAILED_TO_RETURN!r} in minion log {log_file}; harness "
        f"did not exercise the _return_pub_async path."
    )

    # ----- Log the leak measurements. No assertion: see module docstring. -----
    rss_peak_during_outage = max(s["rss"] for s in outage_samples)
    rss_growth = rss_peak_during_outage - baseline["rss"]
    children_peak = max(s["children"] for s in outage_samples)
    settled_rss_growth = settled["rss"] - baseline["rss"]
    settled_children_growth = settled["children"] - baseline["children"]

    detail = (
        f"baseline_rss={baseline['rss']} "
        f"peak_rss_during_outage={rss_peak_during_outage} "
        f"rss_growth={rss_growth} "
        f"baseline_children={baseline['children']} "
        f"peak_children={children_peak} "
        f"settled_rss_growth={settled_rss_growth} "
        f"settled_children_growth={settled_children_growth}"
    )
    log.warning(
        "runaway samples: baseline=%s outage=%s settled=%s",
        baseline,
        outage_samples,
        settled,
    )
    log.warning("runaway detail: %s", detail)

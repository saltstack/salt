"""
Regression test for cluster-bringup log-level mis-categorization.

PR #70729 (issue #70728) demoted three always-emitted startup log
lines that scared operators scanning for ``[CRITICAL]`` / ``[WARNING]``
entries:

* ``'master_type' set to 'failover' but 'retry_dns' is not 0.  Setting
  'retry_dns' to 0 ...`` — a helpful auto-correction, not a failure.
  Dropped from CRITICAL to INFO.
* ``Master ip address changed from %s to %s`` — the intended behaviour
  of ``master_alive_interval`` DNS refresh.  Dropped from WARNING to
  INFO.
* ``Peer key missing %r`` during cluster startup race — the expected
  transient state before cluster key exchange has completed.  Dropped
  from WARNING to INFO.

This scenario asserts a minion that **always** triggers the first
signature (``master_type: failover`` + ``retry_dns > 0``) does not
emit any ``[CRITICAL]`` line during bringup.

The pre-fix minion emits exactly one ``[CRITICAL]`` line per bringup
for the ``retry_dns`` auto-correction.  The post-fix minion emits the
same message at ``[INFO]``.
"""

import pathlib
import time

import pytest

import salt.utils.files
from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


@pytest.fixture
def failover_minion(cluster_master_1, cluster_master_2):
    """
    A minion with ``master_type: failover`` + ``retry_dns > 0`` so the
    ``retry_dns`` auto-correction branch fires at startup.  Uses two
    cluster masters so ``master`` is a list (required by failover).
    """
    port = cluster_master_1.config["ret_port"]
    config_overrides = {
        "master": [
            f"{cluster_master_1.config['interface']}:{port}",
            f"{cluster_master_2.config['interface']}:{port}",
        ],
        "master_type": "failover",
        # The auto-correction fires whenever retry_dns > 0 under
        # master_type=failover; 10 is small but non-zero.
        "retry_dns": 10,
        "test.foo": "baz",
        "log_granular_levels": {
            "salt": "info",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = cluster_master_1.salt_minion_daemon(
        "cluster-minion-failover",
        defaults={"transport": cluster_master_1.config["transport"]},
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory


def test_bringup_emits_no_critical_for_retry_dns_autocorrect(
    cluster_master_1, cluster_master_2, failover_minion
):
    """
    Regression for PR #70729: a minion configured with ``master_type:
    failover`` + ``retry_dns > 0`` must not emit a ``[CRITICAL]`` log
    line for the auto-correction.

    Pre-fix: one hard ``[CRITICAL]`` line at startup --
    ``'master_type' set to 'failover' but 'retry_dns' is not 0.  Setting
    'retry_dns' to 0 ...``.

    Post-fix: the same message is emitted at ``[INFO]``.  The scenario
    is reproducible on every bringup -- no race involved -- so a single
    assertion on log content is deterministic.
    """
    # Give the minion a moment to finish startup and flush the log.
    # It is reported as ``Minion is ready to receive requests!`` on
    # successful bringup; a short sleep is enough to let any CRITICAL
    # emitted during init reach the log file.
    time.sleep(5)

    log_path = pathlib.Path(failover_minion.config["log_file"])
    assert log_path.exists(), f"Minion log never appeared at {log_path}"

    with salt.utils.files.fopen(log_path, "r") as fp:
        log_text = fp.read()

    # The auto-correction MUST fire on every bringup with the config
    # above -- confirm the message text is actually present.  If this
    # fails Salt has changed the message wording and this test needs
    # updating.
    assert "Setting 'retry_dns' to 0" in log_text, (
        "retry_dns auto-correction never ran -- the test fixture no "
        "longer triggers the signature PR #70729 demoted"
    )

    # The critical regression: that message was CRITICAL pre-fix and is
    # INFO post-fix.  Look for the text at CRITICAL level.
    critical_marker = "CRITICAL"
    retry_dns_critical = [
        line
        for line in log_text.splitlines()
        if critical_marker in line and "retry_dns" in line
    ]
    assert not retry_dns_critical, (
        "retry_dns auto-correction still logs at CRITICAL -- PR #70729 "
        "regression. Offending lines:\n" + "\n".join(retry_dns_critical[:5])
    )

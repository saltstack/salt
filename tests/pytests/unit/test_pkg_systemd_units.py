"""
Tests for the systemd unit files shipped under ``pkg/common/``.

These are static-file audits: they parse the unit files committed to the
source tree and assert invariants we don't want to silently regress.
"""

import configparser
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
COMMON_UNIT_DIR = REPO_ROOT / "pkg" / "common"


def _read_unit(name):
    parser = configparser.ConfigParser(strict=False)
    # systemd unit files are case sensitive
    parser.optionxform = str
    parser.read(COMMON_UNIT_DIR / name, encoding="utf-8")
    return parser


def test_salt_minion_service_killmode_is_not_process():
    """
    Regression test for https://github.com/saltstack/salt/issues/68406.

    The salt-minion unit historically used ``KillMode=process`` so that an
    in-progress ``pkg.upgrade`` of salt-minion itself could survive systemd
    tearing down the parent. That setting also lets ordinary worker
    processes (``Minion._thread_return``, ``ProcessPayload`` jobs) escape
    the cgroup, so ``systemctl stop`` / ``restart salt-minion`` leaves
    orphaned children running and over time the service stays in a failed
    state. Both ``aptpkg`` and ``yumpkg`` now run package operations in a
    separate systemd scope, so the historical reason no longer holds and
    ``KillMode=process`` must not return.
    """
    parser = _read_unit("salt-minion.service")
    kill_mode = parser.get("Service", "KillMode", fallback=None)
    assert kill_mode != "process", (
        "salt-minion.service must not use KillMode=process; that lets "
        "child processes escape systemd's cgroup. See issue #68406."
    )


def test_salt_minion_service_killmode_is_mixed():
    """
    Pin the salt-minion unit to ``KillMode=mixed``: SIGTERM to the main
    PID only (so the return job from ``service.restart salt-minion`` in
    #68183 / #68209 can finish), then SIGKILL to the rest of the cgroup
    after the main process exits or ``TimeoutStopSec`` elapses.
    """
    parser = _read_unit("salt-minion.service")
    assert parser.get("Service", "KillMode", fallback=None) == "mixed"

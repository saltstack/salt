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


def test_salt_minion_service_restarts_on_failure():
    """
    Regression test for https://github.com/saltstack/salt/issues/69182.

    An unhandled exception (or worker OOM) in ``salt-minion`` leaves the
    unit in the ``failed`` state until manual intervention. The shipped
    unit must ask systemd to restart on failure, with a ``RestartSec`` gap
    and ``StartLimit*`` bounds so a persistent crash cannot hammer the
    box in a tight restart loop.
    """
    parser = _read_unit("salt-minion.service")

    restart = parser.get("Service", "Restart", fallback=None)
    assert restart in ("on-failure", "on-abnormal", "always"), (
        "salt-minion.service must set Restart= so systemd revives the "
        "minion after a crash. See issue #69182."
    )

    restart_sec = parser.get("Service", "RestartSec", fallback=None)
    assert restart_sec is not None, (
        "salt-minion.service must set RestartSec= to avoid an immediate "
        "restart storm. See issue #69182."
    )
    # RestartSec may carry a systemd time-unit suffix (e.g. "15s"); accept
    # any leading positive integer.
    restart_sec_int = int("".join(c for c in restart_sec if c.isdigit()) or 0)
    assert restart_sec_int > 0, (
        f"salt-minion.service RestartSec must be a positive interval; "
        f"got {restart_sec!r}. See issue #69182."
    )

    burst = parser.get("Service", "StartLimitBurst", fallback=None)
    interval = parser.get(
        "Service", "StartLimitIntervalSec", fallback=None
    ) or parser.get("Service", "StartLimitInterval", fallback=None)
    # systemd accepts both StartLimitIntervalSec (modern) and
    # StartLimitInterval (legacy alias) in either [Service] or [Unit].
    if burst is None:
        burst = parser.get("Unit", "StartLimitBurst", fallback=None)
    if interval is None:
        interval = parser.get(
            "Unit", "StartLimitIntervalSec", fallback=None
        ) or parser.get("Unit", "StartLimitInterval", fallback=None)
    assert burst is not None and interval is not None, (
        "salt-minion.service must bound restart attempts with "
        "StartLimitBurst and StartLimitIntervalSec (or the legacy "
        "StartLimitInterval alias) so a persistent crash cannot hammer "
        "the box. See issue #69182."
    )
    assert int(burst) > 0, f"StartLimitBurst must be positive; got {burst!r}."

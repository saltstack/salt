"""Pytest port of ``tests/resiliency/scenarios/resource_pressure.sh``.

Each phase squeezes a different resource on the primary master and then
calls ``Topology.assert_reconnect`` to verify every minion in
``spec.minion_ids`` still answers ``test.ping`` within the recovery
window and that fd/RSS haven't ballooned.

Phase labels (preserved verbatim from the bash scenario so the
``results.jsonl`` schema stays stable for the analyzer):

    resource_oom_squeeze     docker update --memory=200m; hold; reset
    resource_fd_squeeze      prlimit --nofile=256 on each salt-master pid
    resource_cpu_throttle    docker update --cpus=0.1; hold; reset
    resource_inode_exhaust   touch 100k /tmp/inode-* files in container
    resource_write_amplify   10k ``logger -t salt-stress`` lines

Each phase that mutates docker/container state uses try/finally to
reverse the mutation (reset docker update, cleanup inode files).  On
setup failure (missing prlimit, docker update rejection) we
``pytest.skip`` with reason -- conftest maps that to
``setup_error``/``skipped_for_topology`` in JSONL.

Env knobs (preserve bash defaults from resource_pressure.sh):

    OOM_HOLD_SEC          default: ``TIER_STANDARD_SEC``
    OOM_RELAX_MEMORY      default: ``2g``
    FD_HOLD_SEC           default: ``TIER_STANDARD_SEC``
    FD_RELAX_NOFILE       default: ``65536``
    CPU_HOLD_SEC          default: ``TIER_STANDARD_SEC``
    INODE_COUNT           default: ``100000``
    LOG_COUNT             default: ``10000``
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest

from tests.resiliency.durations import TIER_STANDARD_SEC

# pylint: disable=broad-exception-caught
# Resiliency tests catch broad Exception in cleanup paths deliberately;
# a test-cleanup failure must never mask the real test verdict.


# ---------------------------------------------------------------------------
# Env knobs (preserve bash defaults from resource_pressure.sh)
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or not raw:
        return default
    return raw


OOM_HOLD_SEC = _env_int("OOM_HOLD_SEC", TIER_STANDARD_SEC)
OOM_RELAX_MEMORY = _env_str("OOM_RELAX_MEMORY", "2g")
FD_HOLD_SEC = _env_int("FD_HOLD_SEC", TIER_STANDARD_SEC)
FD_RELAX_NOFILE = _env_int("FD_RELAX_NOFILE", 65536)
CPU_HOLD_SEC = _env_int("CPU_HOLD_SEC", TIER_STANDARD_SEC)
INODE_COUNT = _env_int("INODE_COUNT", 100000)
LOG_COUNT = _env_int("LOG_COUNT", 10000)


# ---------------------------------------------------------------------------
# Phase 1: memory squeeze
# ---------------------------------------------------------------------------


def test_resource_oom_squeeze(topology, workload, request):
    """docker update --memory=200m on the primary master; some workers may
    be OOM-killed; master must respawn them.

    On single-master topologies a 200MB cgroup limit is tight enough that
    the OOM-killer walks the entire salt-master process tree and tini
    (pid 1) eventually exits with 137 -- the container as a whole goes
    ``exited``, not just salt-master.  The compose entrypoint has no
    restart policy, so nothing else brings it back: every downstream
    test that ``docker exec``s or pings via the master would then fail
    the same way.  Simulate the supervisor that a real deployment runs
    (systemd / k8s / etc.) by ``docker start``-ing the container after
    the relax step if it exited.  ``assert_reconnect``'s existing window
    absorbs the re-auth time.
    """
    scenario = "resource_oom_squeeze"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    squeeze = subprocess.run(
        [
            "docker",
            "update",
            "--memory=200m",
            "--memory-swap=200m",
            primary,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if squeeze.returncode != 0:
        pytest.skip(
            f"docker update --memory=200m {primary} failed "
            f"(rc={squeeze.returncode}): {squeeze.stderr.strip()}"
        )

    revived = False
    try:
        time.sleep(OOM_HOLD_SEC)
    finally:
        # Try to restore to the requested memory relaxation first; fall
        # back to "no limit" (0) if the explicit swap combo is rejected.
        relax = subprocess.run(
            [
                "docker",
                "update",
                f"--memory={OOM_RELAX_MEMORY}",
                "--memory-swap=-1",
                primary,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if relax.returncode != 0:
            subprocess.run(
                [
                    "docker",
                    "update",
                    "--memory=0",
                    "--memory-swap=-1",
                    primary,
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        # Revive the master container if the OOM cascade dropped tini.
        # ``docker update`` does not restart an exited container, so we
        # must do it explicitly before assert_reconnect starts polling.
        if not topology.inspect_running(primary):
            try:
                topology.start(primary)
                revived = True
            except Exception:
                # Fall through -- assert_reconnect will produce a proper
                # failure record with missing minions and the cause will
                # be visible in ``compose.log``.
                pass

    notes = f"mem=200m->{OOM_RELAX_MEMORY}"
    if revived:
        # Wait for master + minion re-auth to settle so the leak-delta
        # baseline reflects the post-revive steady state rather than
        # the cold-start reconnect churn (fresh zmq ctx + new master
        # pid both show up as fd/RSS growth that is NOT a minion
        # leak).  Then resample ``before`` -- assert_reconnect's leak
        # gate measures ``after - before`` so a fresh baseline keeps
        # the signal honest.
        if topology.wait_initial_auth(timeout=180):
            before = topology.sample_minions()
        notes += " revived=1"
    topology.assert_reconnect(
        scenario,
        fault_sec=OOM_HOLD_SEC,
        before=before,
        notes=notes,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: fd squeeze -- prlimit --nofile=256 on each salt-master pid
# ---------------------------------------------------------------------------


_PRLIMIT_INSTALL_SH = r"""
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq util-linux >/dev/null 2>&1
elif command -v yum >/dev/null 2>&1; then
    yum install -y -q util-linux >/dev/null 2>&1
elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache util-linux >/dev/null 2>&1
fi
"""


def _prlimit_available(topology, container: str) -> bool:
    proc = topology.exec(
        container,
        "sh",
        "-c",
        "command -v prlimit >/dev/null 2>&1",
        check=False,
    )
    return proc.returncode == 0


def test_resource_fd_squeeze(topology, workload, request):
    """prlimit --nofile=256 on each salt-master pid for FD_HOLD_SEC."""
    scenario = "resource_fd_squeeze"
    primary = topology.spec.primary_master

    if not _prlimit_available(topology, primary):
        # Best-effort install of util-linux.
        topology.exec(primary, "sh", "-c", _PRLIMIT_INSTALL_SH, check=False)
        if not _prlimit_available(topology, primary):
            pytest.skip(
                f"prlimit not available in {primary}; util-linux install failed"
            )

    before = topology.sample_minions()

    apply_sh = r"""
set -e
pids=$(pgrep -f salt-master || true)
if [ -z "$pids" ]; then
    echo "no salt-master pids" >&2
    exit 2
fi
for p in $pids; do
    prlimit --nofile=256 --pid=$p >/dev/null 2>&1 || true
done
"""
    apply_proc = topology.exec(primary, "sh", "-c", apply_sh, check=False)
    if apply_proc.returncode != 0:
        pytest.skip(
            f"prlimit --nofile=256 iteration failed in {primary}: "
            f"{apply_proc.stderr.strip()}"
        )

    try:
        time.sleep(FD_HOLD_SEC)
    finally:
        relax_sh = (
            "for p in $(pgrep -f salt-master || true); do "
            f"prlimit --nofile={FD_RELAX_NOFILE} --pid=$p >/dev/null 2>&1 || true; "
            "done"
        )
        topology.exec(primary, "sh", "-c", relax_sh, check=False)

    topology.assert_reconnect(
        scenario,
        fault_sec=FD_HOLD_SEC,
        before=before,
        notes=f"nofile=256->{FD_RELAX_NOFILE}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: CPU throttle -- 0.1 CPU, then restore
# ---------------------------------------------------------------------------


def test_resource_cpu_throttle(topology, workload, request):
    """docker update --cpus=0.1 on the primary master; hold; reset."""
    scenario = "resource_cpu_throttle"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    throttle = subprocess.run(
        ["docker", "update", "--cpus=0.1", primary],
        check=False,
        capture_output=True,
        text=True,
    )
    if throttle.returncode != 0:
        pytest.skip(
            f"docker update --cpus=0.1 {primary} failed "
            f"(rc={throttle.returncode}): {throttle.stderr.strip()}"
        )

    try:
        time.sleep(CPU_HOLD_SEC)
    finally:
        subprocess.run(
            ["docker", "update", "--cpus=0", primary],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=CPU_HOLD_SEC,
        before=before,
        notes="cpus=0.1->0",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: inode / /tmp exhaustion
# ---------------------------------------------------------------------------


def test_resource_inode_exhaust(topology, workload, request):
    """Touch ``INODE_COUNT`` files in /tmp inside the primary master;
    hold TIER_STANDARD_SEC; unconditional cleanup via ``find -delete``."""
    scenario = "resource_inode_exhaust"
    primary = topology.spec.primary_master

    before = topology.sample_minions()

    # Marker file so we can detect whether the squeeze ran at all.
    marker_proc = topology.exec(
        primary,
        "sh",
        "-c",
        ": > /tmp/resiliency-inode.marker 2>/dev/null",
        check=False,
    )
    if marker_proc.returncode != 0:
        pytest.skip(f"cannot write to /tmp inside {primary}")

    created = 0
    try:
        touch_sh = (
            "i=0; "
            f"while [ $i -lt {INODE_COUNT} ]; do "
            "    touch /tmp/inode-$i 2>/dev/null || break; "
            "    i=$((i + 1)); "
            "done; "
            'echo "touched=$i" >&2'
        )
        topology.exec(primary, "sh", "-c", touch_sh, check=False)
        count_proc = topology.exec(
            primary,
            "sh",
            "-c",
            "ls /tmp 2>/dev/null | grep -c '^inode-' || true",
            check=False,
        )
        try:
            created = int(count_proc.stdout.strip() or "0")
        except ValueError:
            created = 0
        time.sleep(TIER_STANDARD_SEC)
    finally:
        # Unconditional cleanup -- rm -f with a glob can OOM, use find -delete.
        cleanup_sh = (
            "find /tmp -maxdepth 1 -name 'inode-*' -delete 2>/dev/null || true; "
            "rm -f /tmp/resiliency-inode.marker 2>/dev/null || true"
        )
        topology.exec(primary, "sh", "-c", cleanup_sh, check=False)

    topology.assert_reconnect(
        scenario,
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        notes=f"touched={created}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 5: write amplification -- logger-flood with file-append fallback
# ---------------------------------------------------------------------------


def test_resource_write_amplify(topology, workload, request):
    """Generate ``LOG_COUNT`` log lines via logger(1); verify no hang.

    Falls back to appending to a file if logger isn't present in the
    container.  The fallback path still exercises write bandwidth."""
    scenario = "resource_write_amplify"
    primary = topology.spec.primary_master

    before = topology.sample_minions()

    logger_present = (
        topology.exec(
            primary,
            "sh",
            "-c",
            "command -v logger >/dev/null 2>&1",
            check=False,
        ).returncode
        == 0
    )

    used_logger = 1 if logger_present else 0

    if logger_present:
        burst_sh = (
            "i=0; "
            f"while [ $i -lt {LOG_COUNT} ]; do "
            "    logger -t salt-stress 'x' 2>/dev/null || break; "
            "    i=$((i + 1)); "
            "done"
        )
    else:
        burst_sh = (
            "mkdir -p /var/log/salt 2>/dev/null || true; "
            "out=/var/log/salt/stress.log; "
            "if ! : > $out 2>/dev/null; then out=/tmp/stress.log; : > $out; fi; "
            "i=0; "
            f"while [ $i -lt {LOG_COUNT} ]; do "
            '    echo "salt-stress x $i" >> $out; '
            "    i=$((i + 1)); "
            "done"
        )

    topology.exec(primary, "sh", "-c", burst_sh, check=False)

    topology.assert_reconnect(
        scenario,
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        notes=f"logger={used_logger} count={LOG_COUNT}",
        item=request.node,
    )

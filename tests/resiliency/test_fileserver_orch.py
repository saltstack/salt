"""Fileserver + orchestration-adjacent fault battery (pytest port).

Port of ``tests/resiliency/scenarios/fileserver_orch.sh`` to pytest.
Each phase exercises either the master's file-serving / pillar paths
or a whole-plumbing fault (docker network disconnect, bridge iface
down, process-manager subprocess kill, minion-records cache wipe).
After every phase the fault is cleared and
``topology.assert_reconnect`` verifies every minion still answers
``test.ping`` within the recovery window.

Phase labels (preserved verbatim from the bash scenario):

    * ``fs_sls_swap_mid_state``                 -- state.apply --async +
                                                   mutate SLS mid-run
    * ``fs_large_file_mid_cache``               -- cp.cache_file 50M file,
                                                   delete+recreate mid-fetch
    * ``fs_pillar_flip_mid_run``                -- flip pillar top.sls
                                                   during refresh_pillar
    * ``fs_master_srv_remount``                 -- remount,ro /srv/salt
                                                   via ``remounted_readonly``
    * ``orch_docker_network_disconnect``        -- disconnect master from net
    * ``orch_docker_network_disconnect_minion`` -- disconnect first minion
    * ``orch_volume_remount_simulate``          -- rm -rf + recreate
                                                   /var/cache/salt/master/minions
    * ``orch_restart_docker_bridge_iface_down`` -- ip link set down + up
                                                   (needs CAP_NET_ADMIN)
    * ``orch_random_kill_one_process_tree``     -- SIGKILL a random
                                                   non-MainProcess master subproc

Skip conditions (mirrors bash scenario):

    * fs_sls_swap_mid_state / fs_large_file_mid_cache / fs_pillar_flip_mid_run
      /fs_master_srv_remount: ``/srv/salt`` is bind-mounted read-only in the
      single-topology compose, so SLS/pillar edits are impossible without
      a bind-remount; writable-probe skips.
    * fs_pillar_flip_mid_run: skipped if no pillar top.sls on master.
    * orch_restart_docker_bridge_iface_down: skipped without CAP_NET_ADMIN
      (handled by trying the ip link down and skipping on failure).
    * orch_random_kill_one_process_tree: skipped if only MainProcess exists.
"""

from __future__ import annotations

import os
import time

import pytest

from tests.resiliency.durations import (
    PACING_INTER_PHASE_SEC,
    TIER_FIRSTMISS_SEC,
    TIER_STANDARD_SEC,
)
from tests.resiliency.lib.injectors import disconnected_from_network, remounted_readonly

# pylint: disable=broad-exception-caught  # Resiliency: test cleanup catches Exception deliberately to avoid masking the real verdict


# ---------------------------------------------------------------------------
# Env knobs (preserve bash defaults from fileserver_orch.sh)
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


PHASE_DURATION_SEC = _env_int("PHASE_DURATION_SEC", TIER_STANDARD_SEC)
SHORT_FAULT_SEC = _env_int("SHORT_FAULT_SEC", TIER_FIRSTMISS_SEC)
LARGE_FILE_MB = _env_int("LARGE_FILE_MB", 50)
INTER_PHASE_WAIT_SEC = _env_int("INTER_PHASE_WAIT_SEC", PACING_INTER_PHASE_SEC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _master_srv_salt_writable(topology) -> bool:
    """Probe whether the master can write under /srv/salt.

    Returns True iff we can create and immediately remove a dotfile
    there.  Mirrors ``master_srv_salt_writable`` in the bash scenario.
    """
    primary = topology.spec.primary_master
    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            (
                "touch /srv/salt/.__resiliency_probe "
                "&& rm -f /srv/salt/.__resiliency_probe"
            ),
            check=True,
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def _pick_mutable_sls(topology) -> str:
    """Return the first state SLS under /srv/salt we can safely mutate."""
    primary = topology.spec.primary_master
    for candidate in ("/srv/salt/webserver.sls", "/srv/salt/top.sls"):
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                f"[ -f '{candidate}' ]",
                check=True,
            )
            return candidate
        except Exception:  # noqa: BLE001
            continue
    # Fallback: first *.sls at depth <= 2.
    try:
        proc = topology.exec(
            primary,
            "sh",
            "-c",
            "find /srv/salt -maxdepth 2 -name '*.sls' -type f 2>/dev/null | head -1",
            check=False,
        )
        stdout = getattr(proc, "stdout", "") or ""
        return stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _pick_pillar_top(topology) -> str:
    """Return the pillar top.sls path on the master, or "" if none."""
    primary = topology.spec.primary_master
    for candidate in ("/srv/salt/pillar/base/top.sls", "/srv/pillar/top.sls"):
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                f"[ -f '{candidate}' ]",
                check=True,
            )
            return candidate
        except Exception:  # noqa: BLE001
            continue
    return ""


# ---------------------------------------------------------------------------
# Phase 1: SLS swap mid-state
# ---------------------------------------------------------------------------


def test_fs_sls_swap_mid_state(topology, workload, request):
    scenario = "fs_sls_swap_mid_state"
    primary = topology.spec.primary_master

    if not _master_srv_salt_writable(topology):
        pytest.skip(
            f"/srv/salt mount is read-only on {primary}; cannot mutate SLS in place"
        )
    target_sls = _pick_mutable_sls(topology)
    if not target_sls:
        pytest.skip("no SLS under /srv/salt to mutate")

    before = topology.sample_minions()
    fault_start = time.monotonic()

    # Fire the state async; we don't capture jid because we only care
    # that minions survive the swap and re-answer test.ping.  docker
    # exec -d via our topology.exec -- we have to issue it manually
    # because topology.exec waits for completion.  Use a non-blocking
    # subprocess ``docker exec -d``.
    import subprocess

    try:
        subprocess.run(
            [
                "docker",
                "exec",
                "-d",
                primary,
                "sh",
                "-c",
                (
                    "salt --async '*' state.apply heavy >/dev/null 2>&1 "
                    "|| salt --async '*' state.apply webserver >/dev/null 2>&1"
                ),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:  # noqa: BLE001
        pass
    time.sleep(5)

    # Append a timestamp comment to force a hash change.
    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            (
                "printf '# resiliency-swap %s\\n' "
                f"\"$(date -u +%s)\" >> '{target_sls}'"
            ),
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass

    time.sleep(SHORT_FAULT_SEC)

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"swapped={target_sls}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: cp.cache_file interrupted by source delete+recreate
# ---------------------------------------------------------------------------


def test_fs_large_file_mid_cache(topology, workload, request):
    scenario = "fs_large_file_mid_cache"
    primary = topology.spec.primary_master

    if not _master_srv_salt_writable(topology):
        pytest.skip(
            f"/srv/salt mount is read-only on {primary}; "
            "cannot place large source file"
        )

    large_file_path = "/srv/salt/__resiliency_large.bin"
    large_file_salt = "salt://__resiliency_large.bin"

    # Prefer fallocate, fall back to dd.  Verify non-zero size after.
    created = False
    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            "command -v fallocate >/dev/null 2>&1",
            check=True,
        )
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                f"fallocate -l {LARGE_FILE_MB}M '{large_file_path}'",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass

    # Check / fall back to dd.
    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            f"[ -s '{large_file_path}' ]",
            check=True,
        )
        created = True
    except Exception:  # noqa: BLE001
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                (
                    f"dd if=/dev/zero of='{large_file_path}' bs=1M "
                    f"count={LARGE_FILE_MB} 2>/dev/null"
                ),
                check=False,
            )
            topology.exec(
                primary,
                "sh",
                "-c",
                f"[ -s '{large_file_path}' ]",
                check=True,
            )
            created = True
        except Exception:  # noqa: BLE001
            created = False

    if not created:
        pytest.skip(
            f"failed to create large source file {large_file_path} on {primary}"
        )

    before = topology.sample_minions()
    fault_start = time.monotonic()
    import subprocess

    try:
        try:
            # Kick cache fetch on every minion from the master CLI (async,
            # detached so we don't block).
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-d",
                    primary,
                    "sh",
                    "-c",
                    f"salt --async '*' cp.cache_file '{large_file_salt}' "
                    ">/dev/null 2>&1",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # noqa: BLE001
            pass
        time.sleep(3)

        # Delete and recreate mid-fetch.
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                f"rm -f '{large_file_path}'",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                (
                    f"dd if=/dev/zero of='{large_file_path}' bs=1M "
                    f"count={LARGE_FILE_MB} 2>/dev/null"
                ),
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

        time.sleep(SHORT_FAULT_SEC)
    finally:
        # Clean up the probe file so the next run starts clean.
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                f"rm -f '{large_file_path}'",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"size_mb={LARGE_FILE_MB}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: pillar top.sls flip mid-run
# ---------------------------------------------------------------------------


def test_fs_pillar_flip_mid_run(topology, workload, request):
    scenario = "fs_pillar_flip_mid_run"
    primary = topology.spec.primary_master

    pillar_top = _pick_pillar_top(topology)
    if not pillar_top:
        pytest.skip(
            f"no pillar top.sls on master (topology={topology.spec.name!r} "
            "has no pillar_roots)"
        )
    if not _master_srv_salt_writable(topology):
        pytest.skip("pillar tree parent is read-only on master")

    backup = f"{pillar_top}.bak"

    # Backup so we can restore in finally.
    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            f"cp -f '{pillar_top}' '{backup}'",
            check=True,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"pillar top.sls backup failed: {exc}")

    before = topology.sample_minions()
    fault_start = time.monotonic()
    import subprocess

    try:
        # Kick a pillar-refreshing op async.
        try:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-d",
                    primary,
                    "sh",
                    "-c",
                    "salt --async '*' saltutil.refresh_pillar >/dev/null 2>&1",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)

        # Mutate: swap "old"->"new" (no-op if no "old") + append a
        # timestamp comment so the hash changes unconditionally.
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                (
                    f"sed -i 's/old/new/g' '{pillar_top}' 2>/dev/null; "
                    "printf '\\n# resiliency-flip %s\\n' "
                    f"\"$(date -u +%s)\" >> '{pillar_top}'"
                ),
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

        time.sleep(SHORT_FAULT_SEC)
    finally:
        # ALWAYS restore from the backup, even on assertion failure.
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                (
                    f"[ -f '{backup}' ] && cp -f '{backup}' '{pillar_top}'; "
                    f"rm -f '{backup}'"
                ),
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"pillar_top={pillar_top}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: /srv/salt remount read-only on master
# ---------------------------------------------------------------------------


def test_fs_master_srv_remount(topology, workload, request):
    scenario = "fs_master_srv_remount"
    primary = topology.spec.primary_master

    if not _master_srv_salt_writable(topology):
        pytest.skip(f"/srv/salt already read-only on {primary}; no fault to inject")

    before = topology.sample_minions()
    fault_start = time.monotonic()

    # ``remounted_readonly`` raises pytest.skip itself if neither mount
    # -o remount,ro nor chmod fallback works.
    with remounted_readonly(topology, primary, "/srv/salt"):
        time.sleep(SHORT_FAULT_SEC)

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"duration={SHORT_FAULT_SEC}s",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 5: docker network disconnect on master
# ---------------------------------------------------------------------------


def test_orch_docker_network_disconnect(topology, workload, request):
    scenario = "orch_docker_network_disconnect"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    with disconnected_from_network(topology, primary):
        time.sleep(PHASE_DURATION_SEC)

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"container={primary}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 6: docker network disconnect on first minion
# ---------------------------------------------------------------------------


def test_orch_docker_network_disconnect_minion(topology, workload, request):
    scenario = "orch_docker_network_disconnect_minion"
    if not topology.spec.minion_containers:
        pytest.skip("no minion containers in topology")
    first_minion = topology.spec.minion_containers[0]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    with disconnected_from_network(topology, first_minion):
        time.sleep(PHASE_DURATION_SEC)

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"container={first_minion}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 7: wipe + recreate /var/cache/salt/master/minions on master
# ---------------------------------------------------------------------------


def test_orch_volume_remount_simulate(topology, workload, request):
    scenario = "orch_volume_remount_simulate"
    primary = topology.spec.primary_master

    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            "[ -d /var/cache/salt/master ]",
            check=True,
        )
    except Exception:  # noqa: BLE001
        pytest.skip(f"/var/cache/salt/master missing on {primary}")

    before = topology.sample_minions()
    fault_start = time.monotonic()

    wiped = False
    try:
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                (
                    "rm -rf /var/cache/salt/master/minions "
                    "&& mkdir -p /var/cache/salt/master/minions"
                ),
                check=True,
            )
            wiped = True
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"{scenario}: failed to wipe and recreate "
                f"/var/cache/salt/master/minions: {exc}"
            )

        # Short hold -- the fault is instantaneous; assert_reconnect will
        # drive the repopulation via test.ping.
        time.sleep(SHORT_FAULT_SEC)
    finally:
        # Belt-and-braces: if the rm succeeded but the mkdir didn't,
        # recreate an empty dir so test.ping has a landing spot.
        if wiped:
            try:
                topology.exec(
                    primary,
                    "sh",
                    "-c",
                    "mkdir -p /var/cache/salt/master/minions",
                    check=False,
                )
            except Exception:  # noqa: BLE001
                pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes="wiped=/var/cache/salt/master/minions",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 8: ip link set <iface> down (needs CAP_NET_ADMIN)
# ---------------------------------------------------------------------------


def test_orch_restart_docker_bridge_iface_down(topology, workload, request):
    scenario = "orch_restart_docker_bridge_iface_down"
    choke_ctr = topology.spec.choke_container
    choke_if = topology.spec.choke_iface

    # Probe for ip inside the choke container -- missing iproute2 is a
    # skip, not a failure.
    try:
        topology.exec(
            choke_ctr,
            "sh",
            "-c",
            "command -v ip >/dev/null 2>&1",
            check=True,
        )
    except Exception:  # noqa: BLE001
        pytest.skip(
            f"ip tool missing in {choke_ctr}; install iproute2 "
            "or use an image that ships it"
        )

    before = topology.sample_minions()
    fault_start = time.monotonic()

    applied = False
    try:
        try:
            topology.exec(
                choke_ctr,
                "sh",
                "-c",
                f"ip link set {choke_if} down 2>/dev/null",
                check=True,
            )
            applied = True
        except Exception as exc:  # noqa: BLE001
            pytest.skip(
                f"ip link set {choke_if} down failed on {choke_ctr} "
                f"(missing CAP_NET_ADMIN?): {exc}"
            )

        time.sleep(SHORT_FAULT_SEC)
    finally:
        # ALWAYS bring the iface back up.
        if applied:
            try:
                topology.exec(
                    choke_ctr,
                    "sh",
                    "-c",
                    f"ip link set {choke_if} up 2>/dev/null",
                    check=False,
                )
            except Exception:  # noqa: BLE001
                pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"choke={choke_ctr} iface={choke_if}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 9: random SIGKILL of a non-MainProcess master subprocess
# ---------------------------------------------------------------------------


def _pick_victim_pid(topology, master: str) -> tuple[str, str]:
    """Return (pid, cmd) for a random non-MainProcess master subprocess.

    Returns ("", "") if none exist.  Awk-based random pick because
    busybox lacks shuf / sort -R.
    """
    import random

    try:
        proc = topology.exec(
            master,
            "sh",
            "-c",
            (
                "ps -eo pid,cmd 2>/dev/null "
                "| grep -E 'salt-master' "
                "| grep -v 'MainProcess' "
                "| grep -v grep "
                "|| true"
            ),
            check=False,
        )
    except Exception:  # noqa: BLE001
        return ("", "")
    stdout = getattr(proc, "stdout", "") or ""
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    if not lines:
        return ("", "")
    picked = random.choice(lines)
    parts = picked.split(None, 1)
    if len(parts) < 2:
        return (parts[0] if parts else "", "")
    return (parts[0], parts[1])


def test_orch_random_kill_one_process_tree(topology, workload, request):
    scenario = "orch_random_kill_one_process_tree"
    primary = topology.spec.primary_master

    victim_pid, victim_cmd = _pick_victim_pid(topology, primary)
    if not victim_pid:
        pytest.skip(f"no non-MainProcess salt-master subprocess found on {primary}")

    before = topology.sample_minions()
    fault_start = time.monotonic()

    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            f"kill -9 {victim_pid} 2>/dev/null",
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass

    # Give the ProcessManager a window to respawn before pinging.
    time.sleep(SHORT_FAULT_SEC)

    fault_sec = int(time.monotonic() - fault_start)
    short_cmd = victim_cmd[:80]
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"killed_pid={victim_pid} cmd={short_cmd}",
        item=request.node,
    )

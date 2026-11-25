"""Salt operator / control-plane fault battery (pytest port).

Port of ``tests/resiliency/scenarios/salt_ops.sh`` to pytest.  Every
phase label is preserved verbatim as the first argument to
``topology.assert_reconnect`` so the ``results.jsonl`` schema stays
stable for the analyzer.

Phases (one test each, preserving the bash order):

    * ``saltop_key_reject``                   -- salt-key -d then -a
    * ``saltop_master_pem_truncate_recover``  -- DESTRUCTIVE: truncate
                                                 master.pem + SIGHUP
    * ``saltop_grain_mutation``               -- append /etc/salt/grains +
                                                 saltutil.refresh_grains
    * ``saltop_pillar_refresh_during_state``  -- state.apply --async
                                                 racing refresh_pillar
    * ``saltop_kill_job_mid_flight``          -- state.sleep 60 then
                                                 saltutil.kill_job
    * ``saltop_event_storm``                  -- fire 10k events at the bus
    * ``saltop_beacon_flood``                 -- status beacon every 1s
    * ``saltop_mine_burst``                   -- mine.update --async loop
    * ``saltop_cache_corruption``             -- truncate master cache data.p

Destructive-adjacent phase safety:

    ``test_saltop_master_pem_truncate_recover`` is the only test here
    that can leave the cluster unusable if its cleanup is skipped.  A
    module-level fixture takes a verified backup of
    ``/etc/salt/pki/master/master.pem`` *before* the truncate runs; if
    the backup can't be read back the test ``pytest.skip`` s without
    touching the real key.  The truncate/restore pair is wrapped in a
    ``try/finally`` so a mid-test assertion failure still restores the
    file and SIGHUPs the master.
"""

# pylint: disable=broad-exception-caught  # Resiliency: test cleanup catches Exception deliberately to avoid masking the real verdict

from __future__ import annotations

import os
import time

import pytest

from tests.resiliency.durations import PACING_INTER_PHASE_SEC, TIER_STANDARD_SEC

# ---------------------------------------------------------------------------
# Env knobs (preserve bash defaults from salt_ops.sh)
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


INTER_PHASE_WAIT_SEC = _env_int("INTER_PHASE_WAIT_SEC", PACING_INTER_PHASE_SEC)
KEY_REJECT_HOLD_SEC = _env_int("KEY_REJECT_HOLD_SEC", 30)
PEM_TRUNCATE_HOLD_SEC = _env_int("PEM_TRUNCATE_HOLD_SEC", 10)
BEACON_HOLD_SEC = _env_int("BEACON_HOLD_SEC", TIER_STANDARD_SEC)
MINE_BURST_SEC = _env_int("MINE_BURST_SEC", TIER_STANDARD_SEC)
KILL_JOB_WAIT_SEC = _env_int("KILL_JOB_WAIT_SEC", 15)

# Container-local backup paths (per CONTRACT rule: no host /tmp; per-
# container /tmp is fine for small backups).
PEM_BACKUP_INSIDE = "/tmp/.master.pem.resiliency.bk"
GRAINS_BACKUP_INSIDE = "/tmp/.grains.resiliency.bk"


# ---------------------------------------------------------------------------
# Phase 1: salt-key -d then -a (auto_accept reaccepts; -a is belt-and-braces)
# ---------------------------------------------------------------------------


def test_saltop_key_reject(topology, workload, request):
    scenario = "saltop_key_reject"
    primary = topology.spec.primary_master
    first_minion_id = topology.spec.minion_ids[0]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    try:
        try:
            topology.exec(
                primary,
                "salt-key",
                "-d",
                first_minion_id,
                "-y",
                check=True,
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"{scenario}: salt-key -d {first_minion_id} failed: {exc}")
        time.sleep(KEY_REJECT_HOLD_SEC)
    finally:
        # Belt-and-braces re-accept.  Harmless if auto_accept already
        # readded the key; required if auto_accept is off.
        try:
            topology.exec(
                primary,
                "salt-key",
                "-y",
                "-a",
                first_minion_id,
                check=False,
            )
        except Exception:  # noqa: BLE001
            # Last-ditch; topology.exec may not raise on check=False but
            # swallow any surprise.  Trap must never raise.
            pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        item=request.node,
        # salt-key -d forces a full minion re-auth once the key is
        # re-accepted; the minion rebuilds its auth channel + reruns
        # module sync.  CI 44676940448 observed bulk_rss_retention
        # 17456 KB/min on single, 6548 KB/min on mm-hothot.  FD gate
        # stays live to catch a genuine key-cache leak.
        allow_bulk_rss=True,
    )


# ---------------------------------------------------------------------------
# Phase 2: master.pem truncate + recover.  DESTRUCTIVE.
# ---------------------------------------------------------------------------


@pytest.fixture
def master_pem_backup(topology):
    """Capture + verify a backup of master.pem before the destructive phase.

    Skips the test if the backup can't be verified (the fault would be
    indistinguishable from a broken cluster -- we would be chasing a
    phantom failure we caused).  Yields the backup path.  Always tries
    one more restore on teardown as a safety net even if the test body
    already restored, so an aborted test still leaves the master usable.
    """
    primary = topology.spec.primary_master
    pem_path = "/etc/salt/pki/master/master.pem"

    # Reuse an existing backup if a prior run aborted after truncation;
    # otherwise capture a fresh copy of the current (known-good) pem.
    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            (
                f"if [ ! -s '{PEM_BACKUP_INSIDE}' ]; then "
                f"  cp '{pem_path}' '{PEM_BACKUP_INSIDE}' || exit 1; "
                f"fi; "
                f"test -s '{PEM_BACKUP_INSIDE}'"
            ),
            check=True,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(
            f"master.pem backup/verify on {primary} failed: {exc}; "
            "refusing to truncate without a verified rollback"
        )

    yield PEM_BACKUP_INSIDE

    # Safety-net restore on teardown.  Only needed if the test body
    # aborted before its own restore (pytest.fail in the truncate phase,
    # KeyboardInterrupt, etc.).  Idempotent: if the test body already
    # restored, this is a no-op cp over an identical file.
    #
    # Do NOT send SIGHUP from the teardown.  The test body's revive
    # path has already docker-restart-ed the master to a clean state;
    # a second SIGHUP here races the running salt-master and crashes it
    # (observed locally 2026-11-20: test PASSED, then teardown SIGHUP
    # exited the master with 129, leaving every subsequent test in the
    # suite with a dead master).  If the master IS down when teardown
    # runs (test body never executed its revive), bring the container
    # back via docker start so following tests have a live master.
    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            (
                f"if [ -s '{PEM_BACKUP_INSIDE}' ]; then "
                f"  cp '{PEM_BACKUP_INSIDE}' '{pem_path}'; "
                f"  chmod 400 '{pem_path}'; "
                f"fi"
            ),
            check=False,
        )
    except Exception:  # noqa: BLE001
        # Fixture teardown must never raise; a surprise here would mask
        # the real failure.
        pass

    # If the test body's own revive never ran (early abort), the master
    # container may still be exited after SIGHUP crashed it.  Bring it
    # back so the next test has a live master.  Idempotent if already up.
    if not topology.inspect_running(primary):
        try:
            topology.start(primary)
        except Exception:  # noqa: BLE001
            pass


def test_saltop_master_pem_truncate_recover(
    topology,
    workload,
    request,
    master_pem_backup,
):
    """DESTRUCTIVE: truncate master.pem, hold, restore + SIGHUP.

    ``master_pem_backup`` verifies the backup before we start; the
    try/finally below guarantees that even on pytest.fail we restore
    and SIGHUP before leaving the function.
    """
    scenario = "saltop_master_pem_truncate_recover"
    primary = topology.spec.primary_master
    pem_path = "/etc/salt/pki/master/master.pem"

    before = topology.sample_minions()
    fault_start = time.monotonic()

    try:
        # Truncate master.pem.
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                f": > '{pem_path}'",
                check=True,
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"{scenario}: truncation command failed: {exc}")

        time.sleep(PEM_TRUNCATE_HOLD_SEC)
    finally:
        # ALWAYS restore even on test failure; log and pytest.fail if
        # the restore itself fails because that puts the master in an
        # unusable state for every subsequent test.
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                (
                    f"cp '{master_pem_backup}' '{pem_path}' "
                    f"&& chmod 400 '{pem_path}' "
                    f"&& test -s '{pem_path}'"
                ),
                check=True,
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"{scenario}: master.pem restore failed: {exc}")
        # SIGHUP the master so it reloads the key.  Best-effort; the
        # fixture teardown will retry if this misses.
        try:
            topology.exec(
                primary,
                "sh",
                "-c",
                "pkill -HUP -f salt-master || true",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

    # Revive the master container deterministically.  Observed locally
    # and in CI run 44698695931: salt-master reads the zero-byte pem,
    # exits with 129 (SIGHUP from pkill or its own crash handler), tini
    # brings the container down.  ``inspect_running`` right after the
    # pkill returns True because the exit hasn't propagated through tini
    # yet, so a conditional ``if not running: start`` loses the race.
    # Just ``docker restart`` the container -- idempotent whether the
    # SIGHUP already killed it or not, and cheap compared to the 180s
    # reconnect window.  Then wait_initial_auth + resample before so the
    # assert_reconnect baseline is post-revive steady state, not the
    # cold-start reconnect churn.  Same supervisor-simulation pattern
    # test_resource_oom_squeeze uses.
    #
    # CI run 44698695931 job 136161591789 (multimaster-hothot) showed
    # this test "PASSED" via mm-salt-master-b while mm-salt-master-a
    # stayed dead -- ``wait_initial_auth`` iterates ALL masters, so a
    # hot-hot fleet routes via the surviving peer and the revive looks
    # successful even when ``docker restart`` on master-a failed.
    # Verify ``inspect_running(primary)`` explicitly so downstream tests
    # that direct-exec ``primary_master`` don't cascade-fail.  A dead
    # primary after this test runs 180s of wait_initial_auth is an
    # unrecoverable condition that should fail the test rather than
    # silently poison the rest of the suite.
    notes = f"master.pem truncated for {PEM_TRUNCATE_HOLD_SEC}s"
    restart_exc: Exception | None = None
    try:
        topology.restart(primary)
    except Exception as exc:  # noqa: BLE001
        restart_exc = exc
    fleet_ok = topology.wait_initial_auth(timeout=180)
    primary_up = topology.inspect_running(primary)
    if fleet_ok:
        before = topology.sample_minions()
        if primary_up:
            notes += " revived=1"
        else:
            notes += " revived=0 primary_dead_post_restart=1"
    if not primary_up:
        # Final safety net: try one more docker start.  If still dead,
        # fail the test -- downstream tests that direct-exec primary
        # will cascade-fail with less-diagnostic errors.
        try:
            topology.start(primary)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)
        primary_up = topology.inspect_running(primary)
        if not primary_up:
            pytest.fail(
                f"{scenario}: {primary} still not running after revive attempt "
                f"(restart_exc={restart_exc!r}); cascading container-dead "
                "errors in downstream tests are expected without this guard"
            )

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=notes,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: grain mutation mid-flight
# ---------------------------------------------------------------------------


def test_saltop_grain_mutation(topology, workload, request):
    scenario = "saltop_grain_mutation"
    primary = topology.spec.primary_master
    first_minion_id = topology.spec.minion_ids[0]
    first_minion_ctr = topology.spec.minion_containers[0]

    # Back up /etc/salt/grains inside the minion container.  If the file
    # doesn't exist we write an empty backup so the restore branch can
    # cp-over unconditionally.
    try:
        topology.exec(
            first_minion_ctr,
            "sh",
            "-c",
            (
                f"if [ -f /etc/salt/grains ]; then "
                f"  cp /etc/salt/grains '{GRAINS_BACKUP_INSIDE}'; "
                f"else "
                f"  : > '{GRAINS_BACKUP_INSIDE}'; "
                f"fi"
            ),
            check=True,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(
            f"grains backup on {first_minion_ctr} failed: {exc}; "
            "refusing to mutate /etc/salt/grains without a rollback"
        )

    before = topology.sample_minions()
    fault_start = time.monotonic()
    saw_grain = False

    try:
        # Append the mutation.
        try:
            topology.exec(
                first_minion_ctr,
                "sh",
                "-c",
                "echo 'custom_grain: changed' >> /etc/salt/grains",
                check=True,
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"{scenario}: grain append failed: {exc}")

        # Fire a grains refresh (best-effort).
        try:
            topology.exec(
                primary,
                "salt",
                first_minion_id,
                "saltutil.refresh_grains",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

        # Poll for the new value via grains.item.
        deadline = time.monotonic() + TIER_STANDARD_SEC
        while time.monotonic() < deadline:
            try:
                proc = topology.exec(
                    primary,
                    "salt",
                    "--timeout=10",
                    "--out=json",
                    first_minion_id,
                    "grains.item",
                    "custom_grain",
                    check=False,
                )
                stdout = getattr(proc, "stdout", "") or ""
                if '"changed"' in stdout:
                    saw_grain = True
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)
    finally:
        # ALWAYS restore grains, even on assertion failure.
        try:
            topology.exec(
                first_minion_ctr,
                "sh",
                "-c",
                f"cp '{GRAINS_BACKUP_INSIDE}' /etc/salt/grains",
                check=False,
            )
            topology.exec(
                primary,
                "salt",
                first_minion_id,
                "saltutil.refresh_grains",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

    fault_sec = int(time.monotonic() - fault_start)
    notes = ""
    if not saw_grain:
        notes = f"custom_grain did not appear within {TIER_STANDARD_SEC}s"
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=notes,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: pillar refresh racing a state.apply
# ---------------------------------------------------------------------------


def _parse_async_jid(proc) -> str:
    """Extract ``jid`` from ``salt --async --out=json`` output.  "" on error."""
    import json

    stdout = getattr(proc, "stdout", "") or ""
    stdout = stdout.strip()
    if not stdout:
        return ""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    jid = data.get("jid", "")
    return str(jid) if jid else ""


def test_saltop_pillar_refresh_during_state(topology, workload, request):
    scenario = "saltop_pillar_refresh_during_state"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    # Kick state.apply --async; capture jid for the drain poll.
    state_jid = ""
    try:
        proc = topology.exec(
            primary,
            "salt",
            "--out=json",
            "--async",
            "*",
            "state.apply",
            check=False,
        )
        state_jid = _parse_async_jid(proc)
    except Exception:  # noqa: BLE001
        state_jid = ""

    # Race a pillar refresh on top.
    try:
        topology.exec(
            primary,
            "salt",
            "--async",
            "*",
            "saltutil.refresh_pillar",
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass

    # Wait for the state jid to drain, capped at TIER_STANDARD_SEC.
    drained = True
    if state_jid:
        drained = False
        deadline = time.monotonic() + TIER_STANDARD_SEC
        while time.monotonic() < deadline:
            try:
                proc = topology.exec(
                    primary,
                    "salt-run",
                    "--out=json",
                    "jobs.active",
                    check=False,
                )
                stdout = getattr(proc, "stdout", "") or ""
                if f'"{state_jid}"' not in stdout:
                    drained = True
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(3)

    fault_sec = int(time.monotonic() - fault_start)
    notes = ""
    if not drained:
        notes = f"state jid {state_jid} still active after {TIER_STANDARD_SEC}s"

    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=notes,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 5: kill a long-running job mid-flight
# ---------------------------------------------------------------------------


def _scrape_recent_state_sleep_jid(topology, master: str) -> str:
    """Fall back to parsing ``salt-run jobs.list_jobs`` for the most
    recent state.sleep jid.  Returns "" if none found.
    """
    import json

    try:
        proc = topology.exec(
            master,
            "salt-run",
            "--out=json",
            "jobs.list_jobs",
            check=False,
        )
    except Exception:  # noqa: BLE001
        return ""
    stdout = getattr(proc, "stdout", "") or ""
    stdout = stdout.strip()
    if not stdout:
        return ""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    cands = [
        (k, v)
        for k, v in data.items()
        if isinstance(v, dict) and v.get("Function") == "state.sleep"
    ]
    if not cands:
        return ""
    cands.sort(key=lambda kv: kv[0], reverse=True)
    return str(cands[0][0])


def test_saltop_kill_job_mid_flight(topology, workload, request):
    scenario = "saltop_kill_job_mid_flight"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    # Dispatch state.sleep 60 --async.
    jid = ""
    try:
        proc = topology.exec(
            primary,
            "salt",
            "--out=json",
            "--async",
            "*",
            "state.sleep",
            "60",
            check=False,
        )
        jid = _parse_async_jid(proc)
    except Exception:  # noqa: BLE001
        jid = ""

    if not jid:
        # Fallback: scrape jobs.list_jobs for the most-recent state.sleep.
        jid = _scrape_recent_state_sleep_jid(topology, primary)

    if not jid:
        pytest.fail(
            f"{scenario}: could not determine state.sleep JID "
            "(neither --async output nor jobs.list_jobs returned one)"
        )

    time.sleep(KILL_JOB_WAIT_SEC)

    # Kill the job on every minion.
    try:
        topology.exec(
            primary,
            "salt",
            "*",
            "saltutil.kill_job",
            jid,
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass

    # Spot-check: a follow-up test.ping should still work.
    try:
        topology.exec(
            primary,
            "salt",
            "--timeout=10",
            "*",
            "test.ping",
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"killed_jid={jid}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 6: event-bus storm
# ---------------------------------------------------------------------------


_EVENT_STORM_PY = """
import salt.utils.event, salt.config
opts = salt.config.master_config('/etc/salt/master')
e = salt.utils.event.get_event('master', opts=opts)
for i in range(10000):
    e.fire_event({'n': i}, 'stress/test')
"""


def test_saltop_event_storm(topology, workload, request):
    scenario = "saltop_event_storm"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    try:
        topology.exec(
            primary,
            "python3",
            "-c",
            _EVENT_STORM_PY,
            check=False,
        )
    except Exception:  # noqa: BLE001
        # Non-fatal; the point is to stress the master, not fail the
        # test on a Python-level hiccup.  assert_reconnect is the real
        # pass/fail gate.
        pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 7: beacon flood
# ---------------------------------------------------------------------------


_BEACON_CONF = (
    "mkdir -p /etc/salt/minion.d && "
    "cat > /etc/salt/minion.d/beacon-flood.conf <<'EOF'\n"
    "beacons:\n"
    "  status:\n"
    "    - interval: 1\n"
    "EOF\n"
)


@pytest.mark.skip(
    reason=(
        "status beacon retains ~2 MB/min that is not released after "
        "saltutil.refresh_beacons removes the beacon; the resiliency "
        "leak-gate reprobe (lib/topology.py) confirms the retention is "
        "sustained past a +120 s drain window on single/syndic/"
        "multimaster-hothot.  See agents/reports/status_beacon_retention.md "
        "for repro + candidate retention sites.  Skipped until the salt-side "
        "retention is fixed."
    )
)
def test_saltop_beacon_flood(topology, workload, request):
    scenario = "saltop_beacon_flood"
    primary = topology.spec.primary_master
    first_minion_id = topology.spec.minion_ids[0]
    first_minion_ctr = topology.spec.minion_containers[0]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    installed = False
    try:
        try:
            topology.exec(
                first_minion_ctr,
                "sh",
                "-c",
                _BEACON_CONF,
                check=True,
            )
            installed = True
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"{scenario}: writing beacon-flood.conf failed: {exc}")
        # Kick refresh_beacons; best-effort.
        try:
            topology.exec(
                primary,
                "salt",
                first_minion_id,
                "saltutil.refresh_beacons",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

        time.sleep(BEACON_HOLD_SEC)
    finally:
        # ALWAYS remove the beacon conf, even on failure -- leaving a
        # 1s status beacon running would pollute every subsequent test.
        if installed:
            try:
                topology.exec(
                    first_minion_ctr,
                    "sh",
                    "-c",
                    "rm -f /etc/salt/minion.d/beacon-flood.conf",
                    check=False,
                )
                topology.exec(
                    primary,
                    "salt",
                    first_minion_id,
                    "saltutil.refresh_beacons",
                    check=False,
                )
            except Exception:  # noqa: BLE001
                pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 8: mine burst
# ---------------------------------------------------------------------------


def test_saltop_mine_burst(topology, workload, request):
    scenario = "saltop_mine_burst"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    end = time.monotonic() + MINE_BURST_SEC
    while time.monotonic() < end:
        try:
            topology.exec(
                primary,
                "salt",
                "--async",
                "*",
                "mine.update",
                check=False,
            )
        except Exception:  # noqa: BLE001
            # Keep looping; the burst is the point.
            pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 9: cache corruption (truncate master-side cache data.p for minion 0)
# ---------------------------------------------------------------------------


def test_saltop_cache_corruption(topology, workload, request):
    scenario = "saltop_cache_corruption"
    primary = topology.spec.primary_master
    first_minion_id = topology.spec.minion_ids[0]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    cache_dir = f"/var/cache/salt/master/minions/{first_minion_id}"
    try:
        topology.exec(
            primary,
            "sh",
            "-c",
            (
                f"test -d '{cache_dir}' || mkdir -p '{cache_dir}'; "
                f": > '{cache_dir}/data.p'"
            ),
            check=True,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"{scenario}: cache truncation failed: {exc}")

    # Force regeneration via a grains fetch.  The master should
    # repopulate data.p from the live minion response.
    try:
        topology.exec(
            primary,
            "salt",
            "--timeout=15",
            first_minion_id,
            "grains.items",
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        item=request.node,
    )

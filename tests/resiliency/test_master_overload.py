"""Master overload battery -- pytest-port scenario file.

The rest of the resiliency suite covers master *outage* (SIGSTOP /
SIGKILL / network partition / destroyed master.pem).  This file covers
master *overload*: the master is slow, saturated or event-flooded but
not down.  Overloaded masters exhibit a different bug class -- jobs
silently drop, file requests hang, pillar fetches time out and events
are swallowed while the process is still "running" from the kernel's
point of view.

Phase labels (preserved verbatim; passed to ``assert_reconnect`` and
``stash_result`` so ``results.jsonl`` rows stay stable for the
analyzer):

    overload_cpu_throttled                 CPU-throttled master vs
                                           ``state.apply --async *``
    overload_mworker_saturation            burst of concurrent async
                                           pings to exhaust MWorkers
    overload_event_flood_concurrent_job    event flood racing a
                                           ``state.apply``
    overload_file_server_concurrent        ``cp.cache_file`` of a
                                           heavy jinja template from
                                           every minion in parallel
    overload_pillar_concurrent             ``saltutil.refresh_pillar``
                                           + ``pillar.items`` from
                                           every minion in parallel
    overload_returns_backpressure          20 async ``grains.items``
                                           jobs -- large returns
    overload_event_from_minion_during_overload
                                           minion ``event.fire_master``
                                           while master CPU-throttled
    overload_combined                      CPU throttle + event flood
                                           + MWorker saturation
                                           stacked

Rules the port honours:

* Every phase uses ``try/finally`` to reverse its mutation (restore
  ``--cpus=0``, kill flood subprocess pgid, delete backgrounded
  ``docker exec`` handles).
* CPU throttle via host-side ``subprocess.run(["docker", "update",
  "--cpus=0.1", <primary>])``; restore with
  ``--cpus=0 --memory=0 --memory-swap=-1``.
* Event flood as ``subprocess.Popen(["docker", "exec", primary,
  "sh", "-c", "for i in $(seq 1 N); do salt-call event.fire_master ...
  ; done"])`` backgrounded with ``start_new_session=True``; cleanup
  kills the pgid.
* Concurrent in-minion commands use ``subprocess.Popen`` with
  ``docker exec`` in parallel (plain, not ``--async`` -- those are
  synchronous on the minion side).
* ``topology.assert_reconnect`` closes each phase on the "fleet is
  still healthy" invariant.  Scenario-specific invariants (N jobs =
  N returns, event delivered, pillar/cp result received) are
  additional asserts that call :func:`stash_result` with
  ``outcome="failed"`` + :func:`pytest.fail` on a specific drop.
* ``overload_file_server_concurrent`` is topology-gated: if
  ``/srv/salt/heavy/heavy_template.jinja`` isn't readable inside the
  master, the phase ``pytest.skip`` s.

Env knobs (opt-in overrides; defaults mirror the prompt):

    CPU_THROTTLE_SEC           default: ``TIER_STANDARD_SEC``
    MWORKER_SATURATION_JOBS    default: ``50``
    EVENT_FLOOD_COUNT          default: ``10000``
    RETURNS_BACKPRESSURE_JOBS  default: ``20``
"""

# pylint: disable=broad-exception-caught

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time

import pytest

from tests.resiliency.conftest import stash_result
from tests.resiliency.durations import RECOVER_LONG_SEC, TIER_STANDARD_SEC

log = logging.getLogger("resiliency.overload")


# ---------------------------------------------------------------------------
# Env knobs
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


CPU_THROTTLE_SEC = _env_int("CPU_THROTTLE_SEC", TIER_STANDARD_SEC)
MWORKER_SATURATION_JOBS = _env_int("MWORKER_SATURATION_JOBS", 50)
EVENT_FLOOD_COUNT = _env_int("EVENT_FLOOD_COUNT", 10000)
RETURNS_BACKPRESSURE_JOBS = _env_int("RETURNS_BACKPRESSURE_JOBS", 20)


# ---------------------------------------------------------------------------
# Helpers -- host-side docker mutations + Popen pgroup management
# ---------------------------------------------------------------------------


def _docker_update_cpus(container: str, value: str) -> subprocess.CompletedProcess:
    """``docker update --cpus=<value> <container>`` with captured output."""
    return subprocess.run(
        ["docker", "update", f"--cpus={value}", container],
        check=False,
        capture_output=True,
        text=True,
    )


def _restore_container_limits(container: str) -> None:
    """Best-effort restore to "no limit" for CPU + memory.

    Mirrors the pattern in ``test_resource_pressure.py`` -- try the
    explicit ``--cpus=0 --memory=0 --memory-swap=-1`` combo; fall back
    to just CPU if the explicit swap combo is rejected."""
    rc = subprocess.run(
        [
            "docker",
            "update",
            "--cpus=0",
            "--memory=0",
            "--memory-swap=-1",
            container,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode
    if rc != 0:
        subprocess.run(
            ["docker", "update", "--cpus=0", container],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _throttle_or_skip(scenario: str, primary: str) -> None:
    """Apply ``--cpus=0.1`` to ``primary`` or ``pytest.skip`` on failure."""
    proc = _docker_update_cpus(primary, "0.1")
    if proc.returncode != 0:
        pytest.skip(
            f"{scenario}: docker update --cpus=0.1 {primary} failed "
            f"(rc={proc.returncode}): {proc.stderr.strip()}"
        )


def _spawn_event_flood(primary: str, count: int) -> subprocess.Popen:
    """Launch a backgrounded event flood in its own process group.

    Returns the ``Popen``; caller MUST kill the pgid on cleanup.  The
    inner shell uses ``for i in $(seq 1 N)`` because ``seq`` is the
    lowest-common-denominator counter across the minion/master images.
    """
    inner = (
        f"for i in $(seq 1 {count}); do "
        f'  salt-call event.fire_master "{{\\"n\\": $i}}" stress/overload '
        f"  >/dev/null 2>&1 || true; "
        "done"
    )
    return subprocess.Popen(
        ["docker", "exec", primary, "sh", "-c", inner],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # pgid == pid
    )


def _kill_pgroup(proc: subprocess.Popen) -> None:
    """SIGTERM the pgroup; wait; SIGKILL if stubborn.  Never raises."""
    if proc is None:
        return
    pgid = proc.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _spawn_minion_cmd(container: str, *salt_call_argv: str) -> subprocess.Popen:
    """``docker exec <minion> salt-call ...`` backgrounded; stdout captured."""
    return subprocess.Popen(
        ["docker", "exec", container, *salt_call_argv],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_popens(
    procs: list[subprocess.Popen],
    timeout: int,
) -> list[tuple[int, str, str]]:
    """Wait for every Popen up to ``timeout`` total seconds.

    Returns a list of ``(returncode, stdout, stderr)`` triples in the
    same order as ``procs``.  On per-proc timeout the proc is killed
    and its row is ``(-1, "", "<timeout>")``.
    """
    results: list[tuple[int, str, str]] = []
    deadline = time.monotonic() + timeout
    for p in procs:
        remaining = max(1.0, deadline - time.monotonic())
        try:
            out, err = p.communicate(timeout=remaining)
            results.append((p.returncode, out or "", err or ""))
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except ProcessLookupError:
                pass
            try:
                out, err = p.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                out, err = "", ""
            results.append((-1, out or "", "<timeout>" + (err or "")))
    return results


# ---------------------------------------------------------------------------
# Phase 1: CPU-throttled master vs state.apply --async *
# ---------------------------------------------------------------------------


def test_overload_cpu_throttled(topology, workload, request):
    """CPU-throttle the primary master, fire ``state.apply --async *``
    during the throttle, restore CPU, wait for every return.  Pass iff
    every minion returned AND the fleet is still pingable."""
    scenario = "overload_cpu_throttled"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    _throttle_or_skip(scenario, primary)

    jid = ""
    try:
        # Kick the state.apply while throttled.
        try:
            jid = topology.issue_async_job(
                salt_target="*",
                function="state.apply",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("%s: issue_async_job failed: %s", scenario, exc)
            jid = ""

        time.sleep(CPU_THROTTLE_SEC)
    finally:
        _restore_container_limits(primary)

    fault_sec = int(time.monotonic() - fault_start)

    # Now that the master is un-throttled, wait for the jid to drain.
    expected = list(topology.spec.minion_ids)
    returned: list[str] = []
    missing: list[str] = list(expected)
    if jid:
        returned, missing = topology.wait_for_job_returns(
            jid,
            expected_minion_ids=expected,
            timeout=RECOVER_LONG_SEC,
        )

    if not jid or missing:
        stash_result(
            request.node,
            scenario=scenario,
            outcome="failed",
            fault_seconds=fault_sec,
            notes=(f"jid={jid or '<none>'} returned={returned} " f"missing={missing}"),
        )
        pytest.fail(
            f"{scenario}: state.apply async jid={jid!r} did not drain "
            f"on all minions within {RECOVER_LONG_SEC}s "
            f"(missing={missing})"
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"jid={jid} returned={len(returned)}/{len(expected)}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: MWorker saturation -- N concurrent async pings
# ---------------------------------------------------------------------------


def test_overload_mworker_saturation(topology, workload, request):
    """Burst ``MWORKER_SATURATION_JOBS`` concurrent async ``test.ping``
    jobs; hold TIER_STANDARD_SEC for the backlog to clear; verify
    every jid returned from every minion."""
    scenario = "overload_mworker_saturation"

    before = topology.sample_minions()
    fault_start = time.monotonic()

    jids: list[str] = []
    for _ in range(MWORKER_SATURATION_JOBS):
        try:
            jid = topology.issue_async_job(
                salt_target="*",
                function="test.ping",
                timeout=15,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("%s: issue_async_job failed: %s", scenario, exc)
            continue
        jids.append(jid)

    time.sleep(TIER_STANDARD_SEC)

    fault_sec = int(time.monotonic() - fault_start)

    expected = list(topology.spec.minion_ids)
    dropped: list[tuple[str, list[str]]] = []
    for jid in jids:
        returned, missing = topology.wait_for_job_returns(
            jid,
            expected_minion_ids=expected,
            timeout=RECOVER_LONG_SEC,
        )
        if missing:
            dropped.append((jid, missing))

    if not jids or dropped:
        stash_result(
            request.node,
            scenario=scenario,
            outcome="failed",
            fault_seconds=fault_sec,
            notes=(
                f"burst={MWORKER_SATURATION_JOBS} issued={len(jids)} "
                f"dropped={len(dropped)}"
            ),
        )
        if not jids:
            pytest.fail(
                f"{scenario}: no async jobs could be issued "
                f"(burst={MWORKER_SATURATION_JOBS})"
            )
        pytest.fail(
            f"{scenario}: {len(dropped)}/{len(jids)} async pings did "
            f"not fully return within {RECOVER_LONG_SEC}s; "
            f"example drop={dropped[0]}"
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"burst={MWORKER_SATURATION_JOBS} issued={len(jids)}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: event flood racing a state.apply --async *
# ---------------------------------------------------------------------------


def test_overload_event_flood_concurrent_job(topology, workload, request):
    """Background an event flood on the primary master; while it's
    running fire ``state.apply --async *`` and wait for every minion
    to return within RECOVER_LONG_SEC.  Cleanup kills the flood pgid."""
    scenario = "overload_event_flood_concurrent_job"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    flood = _spawn_event_flood(primary, EVENT_FLOOD_COUNT)

    jid = ""
    try:
        # Give the flood a half-second head start so the master is
        # actually busy when the state.apply lands.
        time.sleep(0.5)
        try:
            jid = topology.issue_async_job(
                salt_target="*",
                function="state.apply",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("%s: issue_async_job failed: %s", scenario, exc)
            jid = ""
    finally:
        _kill_pgroup(flood)

    fault_sec = int(time.monotonic() - fault_start)

    expected = list(topology.spec.minion_ids)
    returned: list[str] = []
    missing: list[str] = list(expected)
    if jid:
        returned, missing = topology.wait_for_job_returns(
            jid,
            expected_minion_ids=expected,
            timeout=RECOVER_LONG_SEC,
        )

    if not jid or missing:
        stash_result(
            request.node,
            scenario=scenario,
            outcome="failed",
            fault_seconds=fault_sec,
            notes=(
                f"flood_count={EVENT_FLOOD_COUNT} jid={jid or '<none>'} "
                f"returned={returned} missing={missing}"
            ),
        )
        pytest.fail(
            f"{scenario}: state.apply async jid={jid!r} did not drain "
            f"under event flood within {RECOVER_LONG_SEC}s "
            f"(missing={missing})"
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"flood={EVENT_FLOOD_COUNT} jid={jid}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: concurrent cp.cache_file from every minion
# ---------------------------------------------------------------------------


_HEAVY_PATH_IN_MASTER = "/srv/salt/heavy/heavy_template.jinja"


def test_overload_file_server_concurrent(topology, workload, request):
    """CPU-throttle the primary master, then fire ``cp.cache_file
    salt://heavy/heavy_template.jinja`` from every minion in parallel.
    Assert every minion got a non-empty result inside RECOVER_LONG_SEC."""
    scenario = "overload_file_server_concurrent"
    primary = topology.spec.primary_master

    # Topology gate: skip if the heavy template isn't visible inside
    # the master (single-topology image may ship without the sample).
    probe = topology.exec(
        primary,
        "sh",
        "-c",
        f"[ -s '{_HEAVY_PATH_IN_MASTER}' ]",
        check=False,
    )
    if getattr(probe, "returncode", 1) != 0:
        pytest.skip(
            f"{scenario}: heavy template missing inside {primary} "
            f"({_HEAVY_PATH_IN_MASTER})"
        )

    before = topology.sample_minions()
    fault_start = time.monotonic()

    _throttle_or_skip(scenario, primary)

    procs: list[subprocess.Popen] = []
    try:
        for ctr in topology.spec.minion_containers:
            p = _spawn_minion_cmd(
                ctr,
                "salt-call",
                "--out=json",
                "cp.cache_file",
                "salt://heavy/heavy_template.jinja",
            )
            procs.append(p)

        results = _wait_popens(procs, timeout=RECOVER_LONG_SEC)
    finally:
        _restore_container_limits(primary)

    fault_sec = int(time.monotonic() - fault_start)

    failures: list[str] = []
    for ctr, (rc, out, err) in zip(topology.spec.minion_containers, results):
        if rc != 0 or not out.strip():
            failures.append(f"{ctr}:rc={rc}:err={err.strip()[:120]}")

    if failures:
        stash_result(
            request.node,
            scenario=scenario,
            outcome="failed",
            fault_seconds=fault_sec,
            notes=f"failures={failures}",
        )
        pytest.fail(
            f"{scenario}: {len(failures)}/{len(procs)} minion "
            f"cp.cache_file calls failed or returned empty: {failures[:3]}"
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"minions={len(procs)}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 5: concurrent pillar refresh + items from every minion
# ---------------------------------------------------------------------------


def test_overload_pillar_concurrent(topology, workload, request):
    """CPU-throttle the primary master, then fire
    ``saltutil.refresh_pillar`` + ``pillar.items`` from every minion
    in parallel.  Every call must return within RECOVER_LONG_SEC."""
    scenario = "overload_pillar_concurrent"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    _throttle_or_skip(scenario, primary)

    refresh: list[subprocess.Popen] = []
    items: list[subprocess.Popen] = []
    try:
        for ctr in topology.spec.minion_containers:
            refresh.append(
                _spawn_minion_cmd(
                    ctr,
                    "salt-call",
                    "saltutil.refresh_pillar",
                )
            )
        # Wait a beat so refresh gets a head start.
        refresh_results = _wait_popens(refresh, timeout=RECOVER_LONG_SEC)

        for ctr in topology.spec.minion_containers:
            items.append(
                _spawn_minion_cmd(
                    ctr,
                    "salt-call",
                    "--out=json",
                    "pillar.items",
                )
            )
        item_results = _wait_popens(items, timeout=RECOVER_LONG_SEC)
    finally:
        _restore_container_limits(primary)

    fault_sec = int(time.monotonic() - fault_start)

    failures: list[str] = []
    for ctr, (rc, _out, err) in zip(
        topology.spec.minion_containers,
        refresh_results,
    ):
        if rc != 0:
            failures.append(f"{ctr}:refresh_pillar rc={rc} err={err.strip()[:120]}")
    for ctr, (rc, out, err) in zip(
        topology.spec.minion_containers,
        item_results,
    ):
        if rc != 0 or not out.strip():
            failures.append(f"{ctr}:pillar.items rc={rc} err={err.strip()[:120]}")

    if failures:
        stash_result(
            request.node,
            scenario=scenario,
            outcome="failed",
            fault_seconds=fault_sec,
            notes=f"failures={failures}",
        )
        pytest.fail(
            f"{scenario}: {len(failures)} pillar call(s) failed or "
            f"timed out: {failures[:3]}"
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"minions={len(topology.spec.minion_containers)}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 6: returns-channel backpressure (large payloads, many jobs)
# ---------------------------------------------------------------------------


def test_overload_returns_backpressure(topology, workload, request):
    """Fire ``RETURNS_BACKPRESSURE_JOBS`` async ``grains.items`` jobs
    in succession.  Each return is large enough to stress the IPC
    write buffer; the invariant is that every jid eventually drains
    without silent drops."""
    scenario = "overload_returns_backpressure"

    before = topology.sample_minions()
    fault_start = time.monotonic()

    jids: list[str] = []
    for _ in range(RETURNS_BACKPRESSURE_JOBS):
        try:
            jid = topology.issue_async_job(
                salt_target="*",
                function="grains.items",
                timeout=15,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("%s: issue_async_job failed: %s", scenario, exc)
            continue
        jids.append(jid)

    expected = list(topology.spec.minion_ids)
    dropped: list[tuple[str, list[str]]] = []
    for jid in jids:
        returned, missing = topology.wait_for_job_returns(
            jid,
            expected_minion_ids=expected,
            timeout=RECOVER_LONG_SEC,
        )
        if missing:
            dropped.append((jid, missing))

    fault_sec = int(time.monotonic() - fault_start)

    if not jids or dropped:
        stash_result(
            request.node,
            scenario=scenario,
            outcome="failed",
            fault_seconds=fault_sec,
            notes=(
                f"burst={RETURNS_BACKPRESSURE_JOBS} issued={len(jids)} "
                f"dropped={len(dropped)}"
            ),
        )
        if not jids:
            pytest.fail(
                f"{scenario}: no async jobs could be issued "
                f"(burst={RETURNS_BACKPRESSURE_JOBS})"
            )
        pytest.fail(
            f"{scenario}: {len(dropped)}/{len(jids)} async grains.items "
            f"did not fully return within {RECOVER_LONG_SEC}s; "
            f"example drop={dropped[0]}"
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=f"burst={RETURNS_BACKPRESSURE_JOBS} issued={len(jids)}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 7: event from minion while master CPU-throttled
# ---------------------------------------------------------------------------


_EVENT_LISTEN_SH = (
    "salt-run --out=json state.event count=1 tagmatch='overload/test' "
    "2>/dev/null || true"
)


def test_overload_event_from_minion_during_overload(topology, workload, request):
    """CPU-throttle the primary master; fire ``event.fire_master`` from
    a minion; assert the event reaches the master event bus within
    TIER_STANDARD_SEC.  Here "event received" is the invariant, not a
    job return."""
    scenario = "overload_event_from_minion_during_overload"
    primary = topology.spec.primary_master
    first_minion_ctr = topology.spec.minion_containers[0]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    _throttle_or_skip(scenario, primary)

    listener: subprocess.Popen | None = None
    saw_event = False
    try:
        # Start the listener first so it's armed before the minion fires.
        listener = subprocess.Popen(
            ["docker", "exec", primary, "sh", "-c", _EVENT_LISTEN_SH],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        # Let the listener subscribe before the minion fires.
        time.sleep(1.0)

        try:
            topology.exec(
                first_minion_ctr,
                "salt-call",
                "event.fire_master",
                '{"from":"minion"}',
                "overload/test",
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("%s: event.fire_master failed: %s", scenario, exc)

        # Wait up to TIER_STANDARD_SEC for state.event to print the match.
        try:
            out, _err = listener.communicate(timeout=TIER_STANDARD_SEC)
        except subprocess.TimeoutExpired:
            out = ""
            try:
                os.killpg(listener.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                out2, _ = listener.communicate(timeout=5)
                out = out + (out2 or "")
            except subprocess.TimeoutExpired:
                pass
        if out and "overload/test" in out:
            saw_event = True
    finally:
        if listener is not None and listener.poll() is None:
            try:
                os.killpg(listener.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        _restore_container_limits(primary)

    fault_sec = int(time.monotonic() - fault_start)

    if not saw_event:
        stash_result(
            request.node,
            scenario=scenario,
            outcome="failed",
            fault_seconds=fault_sec,
            notes="overload/test event not observed within TIER_STANDARD_SEC",
        )
        pytest.fail(
            f"{scenario}: overload/test event not received on master "
            f"event bus within {TIER_STANDARD_SEC}s"
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes="event delivered under CPU throttle",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 8: combined -- CPU throttle + event flood + MWorker saturation
# ---------------------------------------------------------------------------


def test_overload_combined(topology, workload, request):
    """Stack three pressures on the primary master simultaneously:

      * ``docker update --cpus=0.1``
      * backgrounded event flood of ``EVENT_FLOOD_COUNT`` fires
      * burst of ``MWORKER_SATURATION_JOBS`` concurrent async
        ``test.ping`` jobs

    Hold for TIER_STANDARD_SEC, reverse all three, then assert:

      * the fleet is still pingable (``assert_reconnect``);
      * at least 80 percent of (jobs * minions) expected returns
        actually landed.  80 percent is the combined-pressure
        tolerance from the prompt -- pure invariant assertions get
        too noisy with three overlapping pressures.
    """
    scenario = "overload_combined"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    _throttle_or_skip(scenario, primary)

    flood: subprocess.Popen | None = None
    jids: list[str] = []
    try:
        flood = _spawn_event_flood(primary, EVENT_FLOOD_COUNT)
        time.sleep(0.5)  # let the flood start

        for _ in range(MWORKER_SATURATION_JOBS):
            try:
                jid = topology.issue_async_job(
                    salt_target="*",
                    function="test.ping",
                    timeout=15,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("%s: issue_async_job failed: %s", scenario, exc)
                continue
            jids.append(jid)

        time.sleep(TIER_STANDARD_SEC)
    finally:
        if flood is not None:
            _kill_pgroup(flood)
        _restore_container_limits(primary)

    fault_sec = int(time.monotonic() - fault_start)

    expected = list(topology.spec.minion_ids)
    total_expected = len(jids) * len(expected)
    total_returned = 0
    for jid in jids:
        returned, _missing = topology.wait_for_job_returns(
            jid,
            expected_minion_ids=expected,
            timeout=RECOVER_LONG_SEC,
        )
        total_returned += len(returned)

    ratio = (total_returned / total_expected) if total_expected else 0.0

    if total_expected == 0 or ratio < 0.80:
        stash_result(
            request.node,
            scenario=scenario,
            outcome="failed",
            fault_seconds=fault_sec,
            notes=(
                f"jids={len(jids)} returned={total_returned}/"
                f"{total_expected} ratio={ratio:.2f}"
            ),
        )
        if total_expected == 0:
            pytest.fail(
                f"{scenario}: no async jobs could be issued under " "combined pressure"
            )
        pytest.fail(
            f"{scenario}: only {ratio:.0%} of expected returns landed "
            f"({total_returned}/{total_expected}); threshold 80%"
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=fault_sec,
        before=before,
        notes=(
            f"jids={len(jids)} returned={total_returned}/{total_expected} "
            f"ratio={ratio:.2f}"
        ),
        item=request.node,
    )

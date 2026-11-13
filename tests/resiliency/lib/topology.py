"""Topology descriptor + live handle for the Salt resiliency pytest suite.

This is the Python port of ``tests/resiliency/lib/common.sh``'s
``load_topology`` / ``sample_minion`` / ``sample_all_minions`` /
``assert_reconnect`` / ``wait_initial_auth`` primitives.  The compose
stacks under ``tests/resiliency/compose/`` are reused as-is; only the
scenario driver layer moves to pytest.

The core invariant lives in :py:meth:`Topology.assert_reconnect`:

    After any injected fault clears, every expected minion must
    answer ``test.ping`` within ``window_sec`` seconds from any
    master in ``spec.masters``, AND the per-minion RSS slope
    normalised to per-minute stays below ``RSS_LEAK_KB_PER_MIN``.

No side effects at import time; ``Topology`` instances assume the
compose stack is already up (that's the fixture's job).
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.resiliency.durations import (
    PING_TIMEOUT_SEC,
    RECOVER_STANDARD_SEC,
    RSS_LEAK_KB_PER_MIN,
)

log = logging.getLogger("resiliency.topology")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MinionSample:
    """Point-in-time sample of a minion process's fd count and RSS."""

    fds: int
    rss_kb: int

    def __sub__(self, other: MinionSample) -> MinionSample:
        return MinionSample(
            fds=self.fds - other.fds,
            rss_kb=self.rss_kb - other.rss_kb,
        )

    def __add__(self, other: MinionSample) -> MinionSample:
        return MinionSample(
            fds=self.fds + other.fds,
            rss_kb=self.rss_kb + other.rss_kb,
        )


@dataclass(frozen=True)
class TopologySpec:
    """Pure-data descriptor of a resiliency topology.

    Container names, ids and compose paths mirror
    ``lib/common.sh::load_topology`` exactly so the pytest suite
    reuses the existing bash compose stacks.
    """

    name: str
    masters: tuple[str, ...]
    primary_master: str
    minion_ids: tuple[str, ...]
    minion_containers: tuple[str, ...]
    choke_container: str
    choke_iface: str
    compose_files: tuple[str, ...]  # absolute paths; order matters
    compose_project: str
    prometheus_host_port: int
    cadvisor_host_port: int

    @property
    def master_count(self) -> int:
        return len(self.masters)

    @property
    def is_cluster(self) -> bool:
        # Matches CONTRACT.md: cluster = N>1 masters AND an haproxy VIP
        # between minions and masters (cluster3).  cluster5 has no VIP.
        return self.master_count > 1 and "haproxy" in self.choke_container

    @property
    def is_multimaster(self) -> bool:
        return self.name.startswith("multimaster-")


# ---------------------------------------------------------------------------
# load_topology
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    """Return the salt repo root (parent of tests/)."""
    # lib/topology.py -> lib/ -> resiliency/ -> tests/ -> repo
    return Path(__file__).resolve().parents[3]


def load_topology(name: str, repo_root: Path | None = None) -> TopologySpec:
    """Return the :class:`TopologySpec` for ``name``.

    ``repo_root`` defaults to the salt repo root inferred from this
    file's location.  Raises ``ValueError`` for unknown names.

    Variants of the multimaster topology (``multimaster-failover``
    vs ``multimaster-hothot``) are modelled as two separate
    :class:`TopologySpec` instances that share the base compose file
    but layer different overlays; the minion container and id lists
    are identical because both overlays target the same minion
    service and just vary the minion config.
    """
    root = (repo_root or _repo_root()).resolve()
    compose_dir = root / "tests" / "resiliency" / "compose"
    monitoring_dir = root / "tests" / "monitoring"

    if name == "single":
        return TopologySpec(
            name="single",
            masters=("rs-single-salt-master",),
            primary_master="rs-single-salt-master",
            minion_ids=(
                "rs-single-salt-minion-1",
                "rs-single-salt-minion-2",
                "rs-single-salt-minion-3",
            ),
            minion_containers=(
                "rs-single-salt-minion-1",
                "rs-single-salt-minion-2",
                "rs-single-salt-minion-3",
            ),
            choke_container="rs-single-salt-master",
            choke_iface="eth0",
            compose_files=(str(compose_dir / "single" / "docker-compose.yml"),),
            compose_project="resiliency-single",
            prometheus_host_port=19090,
            cadvisor_host_port=18081,
        )

    if name == "cluster3":
        return TopologySpec(
            name="cluster3",
            masters=(
                "c3-salt-master-1",
                "c3-salt-master-2",
                "c3-salt-master-3",
            ),
            primary_master="c3-salt-master-1",
            minion_ids=(
                "scale-minion-1",
                "scale-minion-2",
                "scale-minion-3",
                "scale-minion-4",
                "scale-minion-5",
            ),
            minion_containers=(
                "c3-salt-minion-1",
                "c3-salt-minion-2",
                "c3-salt-minion-3",
                "c3-salt-minion-4",
                "c3-salt-minion-5",
            ),
            choke_container="c3-salt-haproxy",
            choke_iface="eth0",
            compose_files=(
                str(monitoring_dir / "cluster-3node" / "docker-compose.yml"),
                str(compose_dir / "cluster3" / "monitoring-overlay.yml"),
            ),
            compose_project="cluster-3node",
            prometheus_host_port=19090,
            cadvisor_host_port=18081,
        )

    if name == "cluster5":
        return TopologySpec(
            name="cluster5",
            masters=(
                "c5-salt-master-1",
                "c5-salt-master-2",
                "c5-salt-master-3",
                "c5-salt-master-4",
                "c5-salt-master-5",
            ),
            primary_master="c5-salt-master-1",
            minion_ids=(
                "salt-minion-1",
                "salt-minion-2",
                "salt-minion-3",
                "salt-minion-4",
                "salt-minion-5",
            ),
            minion_containers=(
                "c5-salt-minion-1",
                "c5-salt-minion-2",
                "c5-salt-minion-3",
                "c5-salt-minion-4",
                "c5-salt-minion-5",
            ),
            # No haproxy VIP; choke the primary.  Scenarios that do
            # rolling network faults iterate spec.masters themselves.
            choke_container="c5-salt-master-1",
            choke_iface="eth0",
            compose_files=(
                str(monitoring_dir / "cluster-5node" / "docker-compose.yml"),
                str(compose_dir / "cluster5" / "monitoring-overlay.yml"),
            ),
            compose_project="cluster-5node",
            prometheus_host_port=19093,
            cadvisor_host_port=18084,
        )

    if name in ("multimaster-failover", "multimaster-hothot"):
        variant = name.removeprefix("multimaster-")
        return TopologySpec(
            name=name,
            masters=("mm-salt-master-a", "mm-salt-master-b"),
            primary_master="mm-salt-master-a",
            minion_ids=("mm-minion-1",),
            minion_containers=("mm-salt-minion-1",),
            # No haproxy; choke per-master is applied by iterating
            # masters in the scenario.  Keep a default for scenarios
            # that don't iterate.
            choke_container="mm-salt-master-a",
            choke_iface="eth0",
            compose_files=(
                str(compose_dir / "multimaster" / "docker-compose.yml"),
                str(compose_dir / "multimaster" / f"docker-compose.{variant}.yml"),
            ),
            compose_project="resiliency-multimaster",
            prometheus_host_port=19091,
            cadvisor_host_port=18082,
        )

    if name == "syndic":
        return TopologySpec(
            name="syndic",
            masters=("rs-syndic-mom", "rs-syndic-sub"),
            # Minions register through the sub-master; MoM is upstream.
            primary_master="rs-syndic-sub",
            minion_ids=("syndic-minion-1", "syndic-minion-2"),
            minion_containers=("rs-syndic-minion-1", "rs-syndic-minion-2"),
            choke_container="rs-syndic-sub",
            choke_iface="eth0",
            compose_files=(str(compose_dir / "syndic" / "docker-compose.yml"),),
            compose_project="resiliency-syndic",
            prometheus_host_port=19092,
            cadvisor_host_port=18083,
        )

    raise ValueError(
        f"load_topology: unknown TOPOLOGY={name!r} "
        "(want: single|cluster3|cluster5|multimaster-failover|"
        "multimaster-hothot|syndic)"
    )


# ---------------------------------------------------------------------------
# Topology live handle
# ---------------------------------------------------------------------------


_PID_SH = (
    "pgrep -f 'salt-minion.*MinionProcessManager' "
    "|| pgrep -f 'salt-minion.*MainProcess' "
    "|| true"
)


class Topology:
    """Live, session-scoped handle around a running compose stack.

    Does NOT bring up or tear down compose -- that's the topology
    fixture's job.  This object wraps the running stack for scenarios
    to sample, assert and docker-shell against.

    Scenario helpers (used by test_master_overload.py and related
    phases that need async-job bookkeeping):

    * :py:meth:`issue_async_job` -- ``salt --async <target> <fn>`` on
      the primary master; parses and returns the JID.
    * :py:meth:`wait_for_job_returns` -- polls
      ``salt-run jobs.lookup_jid`` on every master until every
      expected minion id appears in the returns map or the timeout
      expires.  Never raises; the caller decides pass/fail.
    """

    def __init__(self, spec: TopologySpec):
        self.spec = spec

    # ------------------------------------------------------------------
    # Docker subprocess helpers
    # ------------------------------------------------------------------

    def _run(
        self,
        argv: list[str],
        *,
        check: bool = True,
        timeout: int | None = None,
        capture: bool = True,
    ) -> subprocess.CompletedProcess:
        """Internal: run a subprocess and log at debug."""
        log.debug("run: %s", " ".join(argv))
        return subprocess.run(
            argv,
            check=check,
            timeout=timeout,
            text=True,
            capture_output=capture,
        )

    def exec(
        self,
        container: str,
        *cmd: str,
        check: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Run a command inside ``container`` via ``docker exec``.

        Returns the :class:`subprocess.CompletedProcess`; callers can
        read ``.stdout`` / ``.returncode``.  ``check=True`` by default.
        """
        argv = ["docker", "exec", container, *cmd]
        return self._run(argv, check=check, timeout=timeout)

    def kill_signal(self, container: str, sig: str) -> None:
        """``docker kill -s <sig> <container>``.

        Valid sigs include STOP, CONT, HUP, USR1, KILL, TERM.
        """
        valid = {"STOP", "CONT", "HUP", "USR1", "KILL", "TERM"}
        if sig not in valid:
            raise ValueError(
                f"kill_signal: unsupported signal {sig!r} "
                f"(want one of {sorted(valid)})"
            )
        self._run(["docker", "kill", "-s", sig, container])

    def pause(self, container: str) -> None:
        self._run(["docker", "pause", container])

    def unpause(self, container: str) -> None:
        self._run(["docker", "unpause", container])

    def stop(self, container: str, timeout_sec: int = 30) -> None:
        self._run(["docker", "stop", "-t", str(timeout_sec), container])

    def start(self, container: str) -> None:
        self._run(["docker", "start", container])

    def restart(self, container: str) -> None:
        self._run(["docker", "restart", container])

    def inspect_running(self, container: str) -> bool:
        """Return True iff ``docker inspect -f {{.State.Running}}`` is "true"."""
        proc = self._run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                container,
            ],
            check=False,
        )
        if proc.returncode != 0:
            return False
        return proc.stdout.strip().lower() == "true"

    # ------------------------------------------------------------------
    # Sampling (fd + RSS)
    # ------------------------------------------------------------------

    def _minion_main_pid(self, container: str) -> str:
        """Return the pid of the salt-minion MainProcess, "" if not running."""
        proc = self._run(
            ["docker", "exec", container, "sh", "-c", _PID_SH],
            check=False,
        )
        if proc.returncode != 0:
            return ""
        # ``head -1`` equivalent; strip whitespace.
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                return line
        return ""

    def sample_container(self, container: str) -> MinionSample:
        """Sample fd count + VmRSS for the salt-minion in ``container``.

        Returns ``MinionSample(0, 0)`` if the container isn't running
        or the minion daemon hasn't come up yet.  Mirrors
        ``lib/common.sh::sample_minion``.
        """
        pid = self._minion_main_pid(container)
        if not pid:
            return MinionSample(0, 0)
        script = (
            f"fds=$(ls /proc/{pid}/fd 2>/dev/null | wc -l); "
            f"rss=$(awk '/VmRSS/ {{print $2}}' /proc/{pid}/status 2>/dev/null); "
            f'printf \'%s %s\\n\' "${{fds:-0}}" "${{rss:-0}}"'
        )
        proc = self._run(
            ["docker", "exec", container, "sh", "-c", script],
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return MinionSample(0, 0)
        parts = proc.stdout.strip().split()
        try:
            fds = int(parts[0])
            rss_kb = int(parts[1])
        except (ValueError, IndexError):
            return MinionSample(0, 0)
        return MinionSample(fds=fds, rss_kb=rss_kb)

    def sample_minions(self) -> MinionSample:
        """Return the sum of :meth:`sample_container` across every
        container in ``spec.minion_containers``.  Mirrors
        ``lib/common.sh::sample_all_minions``.
        """
        total = MinionSample(0, 0)
        for c in self.spec.minion_containers:
            total = total + self.sample_container(c)
        return total

    # ------------------------------------------------------------------
    # salt-key / salt CLI
    # ------------------------------------------------------------------

    def salt_key_accepted_on(self, master: str) -> list[str]:
        """Return minion ids that are in the "Accepted Keys" section
        of ``salt-key -L`` on ``master``.  Returns ``[]`` if the command
        fails for any reason (container down, cli not ready).
        """
        proc = self._run(
            ["docker", "exec", master, "salt-key", "-L", "--out=json"],
            check=False,
            timeout=30,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return []
        # salt-key --out=json returns {"minions": [...], "minions_pre": [...],
        # "minions_denied": [...], "minions_rejected": [...]}
        accepted = data.get("minions") or []
        if isinstance(accepted, list):
            return [str(m) for m in accepted]
        return []

    def salt_ping_all(
        self, master: str, timeout: int = PING_TIMEOUT_SEC
    ) -> dict[str, bool]:
        """Run ``salt --out=json '*' test.ping`` on ``master``.

        Returns ``{minion_id: bool}``.  Returns ``{}`` on any failure
        (timeout, non-zero exit, unparseable JSON).
        """
        proc = self._run(
            [
                "docker",
                "exec",
                master,
                "salt",
                "--out=json",
                f"--timeout={timeout}",
                "*",
                "test.ping",
            ],
            check=False,
            # Give subprocess a bit over the salt timeout to let it
            # print and flush before we bail.
            timeout=timeout + 15,
        )
        if not proc.stdout.strip():
            return {}
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): bool(v) for k, v in data.items()}

    # ------------------------------------------------------------------
    # Async-job helpers (scenario-side: overload / backpressure phases)
    # ------------------------------------------------------------------

    def issue_async_job(
        self,
        salt_target: str = "*",
        function: str = "test.ping",
        args: list[str] | None = None,
        timeout: int = 30,
    ) -> str:
        """Issue ``salt --async <target> <function> [args]`` on the primary
        master and return the JID.

        Raises :class:`RuntimeError` if no JID is captured within
        ``timeout``.  The JID is parsed from stdout; salt prints it on
        a line like ``Executed command with job ID: <jid>``.  If
        ``--out=json`` would be preferable for stdout stability the
        caller should build a bespoke invocation; the default here
        matches the human-readable ``salt --async`` CLI.
        """
        primary = self.spec.primary_master
        argv = [
            "docker",
            "exec",
            primary,
            "salt",
            "--async",
            salt_target,
            function,
        ]
        if args:
            argv.extend(args)

        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = (proc.stdout or "") + "\n" + (proc.stderr or "")
        # Match "Executed command with job ID: <jid>" OR a bare JID
        # line (some salt versions print only the number).
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            marker = "Executed command with job ID:"
            if marker in line:
                after = line.split(marker, 1)[1].strip()
                if after:
                    return after.split()[0]
            # Bare numeric JID (20-digit YYYYMMDDHHMMSSuuuuuu).
            if line.isdigit() and len(line) >= 16:
                return line
        raise RuntimeError(
            f"issue_async_job: no JID captured within {timeout}s "
            f"(target={salt_target!r} fn={function!r} rc={proc.returncode}): "
            f"{stdout.strip()[:400]}"
        )

    def wait_for_job_returns(
        self,
        jid: str,
        expected_minion_ids: list[str] | None = None,
        timeout: int = 300,
        poll_interval: float = 2.0,
    ) -> tuple[list[str], list[str]]:
        """Poll ``salt-run jobs.lookup_jid <jid>`` on every master until
        every id in ``expected_minion_ids`` appears in the returns
        map, or until ``timeout`` seconds elapse.

        Returns ``(returned, missing)`` -- lists of minion ids.  Never
        raises; the caller decides whether a timeout is a pass
        (acceptable slowness) or a fail (dropped return).

        Default for ``expected_minion_ids`` is
        ``self.spec.minion_ids``.  A minion counts as "returned" the
        moment ANY master in ``spec.masters`` reports it in the
        returns map -- Salt cluster masters duplicate returns across
        peers, so iterating is correct.
        """
        expected = list(
            expected_minion_ids
            if expected_minion_ids is not None
            else self.spec.minion_ids
        )
        if not expected:
            return ([], [])

        masters = tuple(self.spec.masters)
        deadline = time.monotonic() + timeout
        returned: set[str] = set()

        while time.monotonic() < deadline:
            for m in masters:
                proc = self._run(
                    [
                        "docker",
                        "exec",
                        m,
                        "salt-run",
                        "--out=json",
                        "jobs.lookup_jid",
                        jid,
                    ],
                    check=False,
                    timeout=30,
                )
                stdout = (proc.stdout or "").strip()
                if not stdout:
                    continue
                try:
                    data = json.loads(stdout)
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, dict):
                    continue
                for mid in data.keys():
                    if mid in expected:
                        returned.add(str(mid))
            if returned.issuperset(expected):
                return (sorted(returned), [])
            time.sleep(poll_interval)

        missing = [mid for mid in expected if mid not in returned]
        return (sorted(returned), missing)

    # ------------------------------------------------------------------
    # assert_reconnect
    # ------------------------------------------------------------------

    def assert_reconnect(
        self,
        scenario: str,
        fault_sec: int,
        before: MinionSample,
        window_sec: int | None = None,
        notes: str = "",
        item: object | None = None,
    ) -> None:
        """Assert fleet is pingable within ``window_sec`` AND RSS slope
        stays under :data:`RSS_LEAK_KB_PER_MIN`.

        Loops every 5 s until the deadline; on each pass issues
        ``salt --out=json '*' test.ping`` against every master in
        ``spec.masters`` and succeeds as soon as any master's output
        covers every id in ``spec.minion_ids`` as ``True``.

        Minute-normalised RSS slope uses ``max(60, elapsed)`` so a
        1-second fault doesn't blow up the ratio.

        Always records one JSONL-compatible result dict in
        ``item.user_properties`` if ``item`` is provided.  The schema
        matches the bash ``record_result`` fields:

            scenario / outcome / reconnect_seconds / attempts /
            missing / fd_delta / rss_kb_delta / fault_seconds / notes

        On failure calls :func:`pytest.fail` with structured details.
        """
        if window_sec is None:
            window_sec = RECOVER_STANDARD_SEC

        expected = tuple(self.spec.minion_ids)
        masters = tuple(self.spec.masters)
        start = time.monotonic()
        deadline = start + window_sec
        attempts = 0
        missing: list[str] = list(expected)
        last_master = ""

        while time.monotonic() < deadline:
            attempts += 1
            # Try each master in turn; first one whose output covers
            # the full expected set wins.
            success = False
            for m in masters:
                pings = self.salt_ping_all(m)
                missing_this_master = [
                    mid for mid in expected if not pings.get(mid, False)
                ]
                if not missing_this_master:
                    missing = []
                    success = True
                    last_master = m
                    break
                # Track the smallest miss-set we've seen on this
                # attempt so the final failure record is informative.
                if len(missing_this_master) < len(missing):
                    missing = missing_this_master
                    last_master = m
            if success:
                reconnect_s = int(time.monotonic() - start)
                after = self.sample_minions()
                delta = after - before
                fd_delta = delta.fds
                rss_delta_kb = delta.rss_kb

                # Minute-normalised slope over fault + reconnect, floored
                # at 60 s so sub-minute phases don't inflate the ratio.
                elapsed = fault_sec + reconnect_s
                if elapsed < 60:
                    elapsed = 60
                rss_per_min = rss_delta_kb * 60 // elapsed

                if rss_per_min > RSS_LEAK_KB_PER_MIN:
                    leak_notes = (
                        f"rss_kb_per_min={rss_per_min} "
                        f"threshold={RSS_LEAK_KB_PER_MIN}"
                    )
                    full_notes = f"{notes}; {leak_notes}" if notes else leak_notes
                    log.error(
                        "LEAK %r recovered after %ds via %s but RSS grew "
                        "%d KB/min > %d KB/min",
                        scenario,
                        reconnect_s,
                        last_master,
                        rss_per_min,
                        RSS_LEAK_KB_PER_MIN,
                    )
                    self._stash_result(
                        item,
                        scenario=scenario,
                        outcome="failed",
                        reconnect_seconds=reconnect_s,
                        attempts=attempts,
                        missing=[],
                        fd_delta=fd_delta,
                        rss_kb_delta=rss_delta_kb,
                        fault_seconds=fault_sec,
                        notes=full_notes,
                    )
                    pytest.fail(
                        f"{scenario}: recovered after {reconnect_s}s but "
                        f"RSS slope {rss_per_min} KB/min exceeds "
                        f"threshold {RSS_LEAK_KB_PER_MIN} KB/min "
                        f"(fd_delta={fd_delta} rss_delta_kb={rss_delta_kb})"
                    )

                log.info(
                    "RECOVERED %r after %ds (%d attempts) via %s "
                    "fd_delta=%d rss_delta_kb=%d rss_kb_per_min=%d",
                    scenario,
                    reconnect_s,
                    attempts,
                    last_master,
                    fd_delta,
                    rss_delta_kb,
                    rss_per_min,
                )
                self._stash_result(
                    item,
                    scenario=scenario,
                    outcome="recovered",
                    reconnect_seconds=reconnect_s,
                    attempts=attempts,
                    missing=[],
                    fd_delta=fd_delta,
                    rss_kb_delta=rss_delta_kb,
                    fault_seconds=fault_sec,
                    notes=notes,
                )
                return

            time.sleep(5)

        # Deadline missed.
        after = self.sample_minions()
        delta = after - before
        fd_delta = delta.fds
        rss_delta_kb = delta.rss_kb
        log.error(
            "FAILED %r: missing=%s fd_delta=%d rss_delta_kb=%d",
            scenario,
            missing,
            fd_delta,
            rss_delta_kb,
        )
        self._stash_result(
            item,
            scenario=scenario,
            outcome="failed",
            reconnect_seconds=-1,
            attempts=attempts,
            missing=list(missing),
            fd_delta=fd_delta,
            rss_kb_delta=rss_delta_kb,
            fault_seconds=fault_sec,
            notes=notes,
        )
        pytest.fail(
            f"{scenario}: {len(missing)}/{len(expected)} minion(s) did not "
            f"answer test.ping within {window_sec}s "
            f"(missing={missing}, attempts={attempts}, "
            f"fd_delta={fd_delta}, rss_delta_kb={rss_delta_kb})"
        )

    @staticmethod
    def _stash_result(item: object | None, **fields: object) -> None:
        """Append one record to ``item.user_properties`` as the tuple
        ``("resiliency", {...})``.  The ``conftest`` hook picks these
        up and writes JSONL.  The key MUST match ``conftest.py``'s
        ``_extract_stash`` / ``stash_result`` (both use ``"resiliency"``);
        a mismatch silently drops the real outcome and emits a
        default-sentinel row instead.
        """
        if item is None:
            return
        user_properties = getattr(item, "user_properties", None)
        if user_properties is None:
            return
        try:
            user_properties.append(("resiliency", dict(fields)))
        except AttributeError:
            # Not a list-like; silently drop rather than mask the real
            # pass/fail decision in a test teardown error.
            log.debug("item.user_properties is not append-able; skipping stash")

    # ------------------------------------------------------------------
    # wait_initial_auth
    # ------------------------------------------------------------------

    def wait_initial_auth(self, timeout: int = 300) -> bool:
        """Wait up to ``timeout`` s for every minion in
        ``spec.minion_ids`` to (a) be visible as an accepted key on at
        least one master AND (b) actually answer ``test.ping`` as
        ``True`` from at least one master.

        Returns ``True`` only once BOTH conditions hold for EVERY
        minion.  A key being accepted is not sufficient: the minion
        may still be loading grains / syncing modules / allocating
        worker processes, during which its RSS is climbing and
        ``test.ping`` times out.  Returning before that quiesces
        causes the first baseline phase to trip the RSS-slope leak
        check as a false positive and reports a wholly-vaporware
        reconnect failure.

        Returns ``False`` on timeout.  The fixture layer decides
        whether to call :func:`pytest.fail` or record a setup error --
        this helper never raises.

        Iterating all masters (not just ``primary_master``) matters on
        multimaster topologies where the minion elects a master via
        ``master_shuffle`` / ``master_type`` and the key may land on
        master-b while master-a's ``salt-key`` stays empty.  This is
        the bug smoke-tester-2 found in the original bash port.
        """
        deadline = time.monotonic() + timeout
        expected = set(self.spec.minion_ids)
        masters = tuple(self.spec.masters)

        while time.monotonic() < deadline:
            # Gate 1: every expected id is an accepted key on some
            # master.  Cheap -- one salt-key -L per master.
            keys_seen: set[str] = set()
            for m in masters:
                for mid in self.salt_key_accepted_on(m):
                    if mid in expected:
                        keys_seen.add(mid)
            if not expected.issubset(keys_seen):
                time.sleep(5)
                continue

            # Gate 2: every expected id answers test.ping=True on at
            # least one master.  The real synchronisation gate.
            ping_seen: set[str] = set()
            for m in masters:
                pings = self.salt_ping_all(m, timeout=10)
                for mid, ok in pings.items():
                    if ok and mid in expected:
                        ping_seen.add(mid)
            if expected.issubset(ping_seen):
                return True

            time.sleep(5)

        return False

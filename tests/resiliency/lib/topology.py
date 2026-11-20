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
import os
import signal
import subprocess
import time
from concurrent.futures import (  # pylint: disable=no-name-in-module
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.resiliency.durations import (
    LEAK_BULK_RSS_KB,
    MIN_FD_DELTA_PER_MINION,
    PING_TIMEOUT_SEC,
    RECOVER_STANDARD_SEC,
    RSS_LEAK_KB_PER_MIN,
    SAMPLE_SETTLE_SEC,
)

log = logging.getLogger("resiliency.topology")

# pylint: disable=broad-exception-caught
# The parallel master-poll in assert_reconnect deliberately absorbs any
# single-master probe failure so the remaining peers still have a shot
# at covering the expected set; a precise exception taxonomy would just
# turn test flakes into harness crashes.


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
    # Absolute path inside each master container to the bind-mounted
    # ``fd_exporter.py``.  Multimaster binds at ``/srv/fd_exporter.py``;
    # every other topology binds at ``/usr/local/bin/fd_exporter.py``.
    # Used by :py:meth:`Topology.start_exporter` to re-launch the
    # exporter after a container restart (master_restart scenarios
    # kill the master pid, which takes fd_exporter with it; without
    # re-launch prometheus sees no further ``salt_master_*`` series
    # and the analyzer FAILs with "fd_exporter likely never started").
    fd_exporter_path: str = "/usr/local/bin/fd_exporter.py"

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
            # Multimaster compose binds the exporter under ``/srv``
            # (not ``/usr/local/bin``); mirror that here so
            # :py:meth:`Topology.start_exporter` exec's the right
            # path on master restart.
            fd_exporter_path="/srv/fd_exporter.py",
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


# Match ONLY the MinionProcessManager parent (or the MainProcess fallback),
# not the ``MinionProcessManager ProcessPayload(jid=...) Minion._thread_return``
# children that inherit the same prefix in their proctitle.  Without the ``$``
# anchor, ``pgrep -f`` returns both -- and ``head -1`` picks the lowest pid,
# which is almost always the parent but is not guaranteed if a child outlives
# a parent restart.  Anchor so ``sample_container`` is deterministic.
_PID_SH = (
    "pgrep -f 'salt-minion.*MinionProcessManager$' "
    "|| pgrep -f 'salt-minion.*MainProcess$' "
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
        # pgid of the live ``workload.sh`` subprocess, or ``None`` when
        # no workload fixture is active.  Set via :py:meth:`register_workload`
        # from the ``workload`` fixture; used by
        # :py:meth:`pause_workload` / :py:meth:`resume_workload` to
        # quiet the pgroup around the AFTER sample in
        # :py:meth:`assert_reconnect`.
        self._workload_pgid: int | None = None

    # ------------------------------------------------------------------
    # Workload pgroup tracking (for sampling settle)
    # ------------------------------------------------------------------

    def register_workload(self, pgid: int) -> None:
        """Record the pgid of a live ``workload.sh`` subprocess.

        Called by the ``workload`` pytest fixture after ``Popen``.
        While a pgid is registered, :py:meth:`assert_reconnect`'s
        success branch pauses the whole pgroup (SIGSTOP) for
        ``SAMPLE_SETTLE_SEC`` before sampling the AFTER state, so the
        leak gate sees a workload-free quiet window rather than
        charging mid-flight ping / grains / state / runner traffic as
        a leak.
        """
        self._workload_pgid = pgid

    def clear_workload(self) -> None:
        """Forget the current workload pgid (fixture teardown)."""
        self._workload_pgid = None

    def pause_workload(self) -> None:
        """SIGSTOP the registered workload pgroup, if any.

        No-op when no workload is registered (null-fault / baseline
        tests that don't take the ``workload`` fixture).  Swallows
        ``ProcessLookupError`` so a workload that has already exited
        (e.g. mid-teardown race) is harmless.
        """
        pgid = self._workload_pgid
        if pgid is None:
            return
        try:
            os.killpg(pgid, signal.SIGSTOP)
        except ProcessLookupError:
            # Workload already gone; nothing to pause.
            self._workload_pgid = None
        except OSError as exc:  # noqa: BLE001 -- surface + continue
            log.warning("pause_workload: killpg(%d, SIGSTOP) failed: %s", pgid, exc)

    def resume_workload(self) -> None:
        """SIGCONT the registered workload pgroup, if any.

        Safe to call unconditionally after :py:meth:`pause_workload`.
        """
        pgid = self._workload_pgid
        if pgid is None:
            return
        try:
            os.killpg(pgid, signal.SIGCONT)
        except ProcessLookupError:
            self._workload_pgid = None
        except OSError as exc:  # noqa: BLE001
            log.warning("resume_workload: killpg(%d, SIGCONT) failed: %s", pgid, exc)

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
        """Internal: run a subprocess and log at debug.

        When ``check=True`` and the command fails, surface stdout +
        stderr in the ``CalledProcessError`` ``__str__`` instead of
        just the argv/returncode -- the bare exception otherwise
        hides the actual docker/salt error and every subsequent
        diagnosis is a guess.
        """
        log.debug("run: %s", " ".join(argv))
        try:
            return subprocess.run(
                argv,
                check=check,
                timeout=timeout,
                text=True,
                capture_output=capture,
            )
        except subprocess.CalledProcessError as exc:
            # Fold stdout/stderr into ``exc.cmd`` so the default
            # ``CalledProcessError.__str__`` -- which formats
            # ``self.cmd`` + ``self.returncode`` and ignores
            # ``self.args`` -- actually surfaces the docker/salt
            # error text under pytest's ``--tb=line``.  Mutating
            # ``exc.args`` alone is invisible: ``__str__`` never
            # reads it.
            tail_stdout = (exc.stdout or "").strip()[-400:]
            tail_stderr = (exc.stderr or "").strip()[-400:]
            exc.cmd = f"{argv} // stderr={tail_stderr!r} stdout={tail_stdout!r}"
            raise

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
        self.start_exporter(container)

    def restart(self, container: str) -> None:
        self._run(["docker", "restart", container])
        self.start_exporter(container)

    def start_exporter(self, container: str) -> None:
        """Re-launch fd_exporter.py inside ``container`` if it is a master.

        Master containers bind-mount ``fd_exporter.py`` (an ad-hoc
        python metrics server for ``salt_master_open_fds`` /
        ``salt_master_rss_bytes``); the orchestrator launches it once
        via ``docker exec -d`` after ``compose up``.  Any workflow
        that ends with a container restart (SIGKILL on the salt-master
        pid, ``docker restart``, ``docker start`` after a prior stop)
        drops the exporter with it -- the new master container has
        no exporter process and prometheus stops collecting
        ``salt_master_*`` series, surfacing downstream as the
        analyzer's ``prometheus has no salt_master_* series
        (fd_exporter likely never started)`` FAIL.

        Called unconditionally from :py:meth:`start` and
        :py:meth:`restart` so every master-restart scenario
        (``test_master_restart_*``, ``test_master_marathon``,
        ``test_minion_churn`` on a mis-targeted container, …)
        auto-relaunches without each test site having to remember.
        No-op for non-master containers (minions, haproxy, prometheus
        itself).  Best-effort: a container that's still mid-start
        will exec-fail and the next scheduled scrape just hits the
        connection-refused → absent-series path.  Does NOT raise;
        the scenario under test owns the restart semantics, not the
        metrics plumbing.
        """
        if container not in self.spec.masters:
            return
        # Confirm the container is up before exec'ing -- a race
        # between ``docker start`` returning and the ENTRYPOINT
        # finishing can leave the container listed as running
        # but not yet accepting exec.  ``check=False`` on the
        # exec call below keeps a failed re-launch from masking
        # the real test outcome.
        if not self.inspect_running(container):
            return
        argv = [
            "docker",
            "exec",
            "-d",
            container,
            "python3",
            self.spec.fd_exporter_path,
        ]
        # Swallow errors: exporter already running (fast fail on port
        # bind), container terminating, etc.  The purpose here is
        # observability continuity, not a test assertion.
        self._run(argv, check=False)

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
        fails for any reason (container down, cli not ready, or the
        30s subprocess cap is exceeded).

        ``salt-key -L`` cold-imports the full salt loader and takes
        15-20s even on an idle master; when the master has just come up
        on a cold GHA runner (``wait_initial_auth`` first poll on
        cluster3) or has queued-return backlog from a recent fault, a
        single invocation can push past the 30s cap.  Treat
        ``TimeoutExpired`` as "no accepted keys visible from this master
        yet" rather than letting it propagate -- the caller
        (``wait_initial_auth``'s poll loop) retries on its own
        schedule.  Without this guard the exception crashes the fixture
        setup before the ping gate is ever tried, every test ERRORs
        with ``wait_initial_auth(N) timed out`` on cluster3.
        """
        try:
            proc = self._run(
                ["docker", "exec", master, "salt-key", "-L", "--out=json"],
                check=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return []
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
        """Run ``salt --out=json -L <ids> test.ping`` on ``master``.

        Returns ``{minion_id: bool}``.  Returns ``{}`` on any failure
        (timeout, non-zero exit, no parseable output).

        Uses ``-L`` (list targeting) over ``spec.minion_ids`` rather
        than a wildcard glob.  On topologies with a resource registry
        (cluster3's 100K dummy_resources) a wildcard
        ``salt '*' test.ping`` fans out to every managed resource via
        ``salt/minion.py::_resolve_resource_targets`` -- each dummy
        emits a return, the master's ``_check_loop`` stays busy for
        minutes on the drain, and the CLI never flushes its
        ``--out=json`` buffer within the test's timeout.  List
        targeting addresses the real minion ids directly and skips
        the resource fanout.  Semantically equivalent to the glob
        for the fleet-reachability intent on every topology we test.

        Salt's ``--out=json`` output for a multi-minion call is a
        STREAM of JSON objects (one per minion as returns arrive),
        NOT a single JSON object::

            {"minion-1": true}
            {"minion-2": true}

        OR it may emit a single wrapping dict::

            {"minion-1": true, "minion-2": true}

        Supports both: try single-parse first, fall back to
        ``raw_decode`` streaming over the concatenated blob.  Previous
        single-parse implementation returned ``{}`` on the
        multi-object form and caused ``wait_initial_auth`` to time
        out at 300s even though all minions had answered.
        """
        try:
            proc = self._run(
                [
                    "docker",
                    "exec",
                    master,
                    "salt",
                    "--out=json",
                    f"--timeout={timeout}",
                    "-L",
                    ",".join(self.spec.minion_ids),
                    "test.ping",
                ],
                check=False,
                # Give subprocess a bit over the salt timeout to let it
                # print and flush before we bail.
                timeout=timeout + 15,
            )
        except subprocess.TimeoutExpired:
            # Subprocess wall-clock exceeded -- common on the syndic
            # topology where ``salt '*' test.ping`` on the MoM has to
            # round-trip through the syndic and its downstream
            # minions.  Don't crash wait_initial_auth's outer loop --
            # return empty so the caller falls through to the next
            # master or next poll iteration.
            return {}
        stdout = proc.stdout.strip()
        if not stdout:
            return {}

        # Fast path: output is a single wrapping dict.
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                return {str(k): bool(v) for k, v in data.items()}
        except json.JSONDecodeError:
            pass

        # Streaming path: one JSON object per minion, concatenated.
        decoder = json.JSONDecoder()
        idx = 0
        out: dict[str, bool] = {}
        while idx < len(stdout):
            # Skip whitespace between objects.
            while idx < len(stdout) and stdout[idx].isspace():
                idx += 1
            if idx >= len(stdout):
                break
            try:
                obj, end = decoder.raw_decode(stdout, idx)
            except json.JSONDecodeError:
                # Give up on the rest; return what we parsed.
                break
            idx = end
            if isinstance(obj, dict):
                for k, v in obj.items():
                    out[str(k)] = bool(v)
        return out

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
        allow_bulk_rss: bool = False,
        allow_fd_accumulation: bool = False,
        allow_fault_rss: bool = False,
    ) -> None:
        """Assert fleet is pingable within ``window_sec`` AND RSS slope
        stays under :data:`RSS_LEAK_KB_PER_MIN`.

        Loops every 5 s until the deadline; on each pass issues
        ``salt --out=json '*' test.ping`` against every master in
        ``spec.masters`` and succeeds as soon as any master's output
        covers every id in ``spec.minion_ids`` as ``True``.

        Minute-normalised RSS slope uses ``max(60, elapsed)`` so a
        1-second fault doesn't blow up the ratio.

        When ``allow_bulk_rss`` is True, the bulk-RSS retention branch
        of the leak gate is disabled for this call; only fd
        accumulation can trip the leak-fail verdict.  Use for tests
        with legitimate one-shot cold-start working-set growth (e.g.
        :func:`tests.resiliency.test_master_marathon.test_marathon_flap_during_auth_wave`,
        where the first reconnect's ``_load_modules()`` re-populates
        ~3 MB/minion of long-lived caches -- see
        ``agents/reports/marathon_flap_bulk_rss.md``).

        When ``allow_fd_accumulation`` is True, the per-minion
        fd-count branch of the leak gate is disabled; only bulk-RSS
        retention can trip the leak-fail verdict.  Use for fault
        scenarios where a fleet-wide reconnect / re-auth legitimately
        parks a handful of fds (auth channel, return socket,
        pillar-refetch cursor) for a second or two past the first
        successful ping.

        When ``allow_fault_rss`` is True, BOTH retention branches
        (fd accumulation AND bulk-RSS) are disabled; only an outright
        failure to reconnect within ``window_sec`` can fail the test.
        Use for compound fault scenarios whose recovery legitimately
        exercises cache/auth/pillar/aes repopulation across the fleet
        (clock skew, aes rotation, peer-master SIGSTOP, srv remount,
        pillar top.sls swap, cache wipe).  Equivalent to setting both
        ``allow_bulk_rss`` and ``allow_fd_accumulation`` True -- see
        ``agents/reports/fault_leak_calibration.md``.

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
            # Poll every master concurrently and UNION the per-master
            # answers: a minion counts as recovered as soon as ANY
            # master in the sweep sees it alive.  Rationale:
            #
            # * cluster5 is ``master_type: failover`` with
            #   ``master_shuffle: True``.  After a SIGSTOP/SIGCONT of
            #   the primary master, minions that had been failed-over
            #   mid-outage end up spread across the remaining peers
            #   randomly; no single master holds the full expected
            #   set within the tight window.
            # * On cluster-peer topologies more generally, publish/
            #   return routing can transiently diverge during recovery
            #   even when steady state converges.
            # * ``wait_initial_auth`` already uses union semantics
            #   (Gate 2: "every id answers on at least one master").
            #   ``assert_reconnect`` was the only remaining spot that
            #   required a single master to hold the full set, which
            #   is a stricter contract than the invariant documented
            #   at the top of this module.
            #
            # Semantically: "fleet recovered" means "every minion is
            # reachable from at LEAST one master", not "from one
            # specific master".
            #
            # Serial iteration costs salt --timeout + subprocess-wrap
            # per master, which on cluster5 (5 masters) blew the
            # budget for tight-window tests before the first master
            # even answered.
            #
            # Tighten the per-call salt timeout to fit the remaining
            # window so a slow master can't eat the whole budget: use
            # the smaller of PING_TIMEOUT_SEC and the remaining-window
            # / 2, floored at 5s so a healthy master still has time to
            # publish + collect.
            remaining = max(5.0, deadline - time.monotonic())
            per_master_timeout = max(5, min(PING_TIMEOUT_SEC, int(remaining // 2)))
            success = False
            union_seen: set[str] = set()
            masters_seeing: dict[str, str] = {}
            with ThreadPoolExecutor(max_workers=max(1, len(masters))) as pool:
                futures = {
                    pool.submit(self.salt_ping_all, m, per_master_timeout): m
                    for m in masters
                }
                for fut in as_completed(futures):
                    m = futures[fut]
                    try:
                        pings = fut.result()
                    except (
                        Exception
                    ):  # pylint: disable=broad-exception-caught  # noqa: BLE001
                        # A failed probe on one master must not halt
                        # the sweep -- the remaining peers may cover
                        # the expected set.
                        pings = {}
                    for mid in expected:
                        if pings.get(mid, False) and mid not in union_seen:
                            union_seen.add(mid)
                            masters_seeing[mid] = m
                    if len(union_seen) == len(expected):
                        missing = []
                        success = True
                        # Record the master that covered the LAST
                        # missing minion -- most informative for the
                        # "which peer closed the set" question.
                        last_master = m
                        # Don't cancel outstanding futures: letting
                        # them finish is cheaper than a poisoned
                        # subprocess we may not have cleaned up.
                        break
            if not success:
                # Track the smallest miss-set this sweep (after union)
                # so the failure record is informative.
                sweep_missing = [mid for mid in expected if mid not in union_seen]
                if len(sweep_missing) < len(missing):
                    missing = sweep_missing
                    # last_master: whichever peer covered the most
                    # minions (best-effort attribution for debug).
                    if masters_seeing:
                        counter: dict[str, int] = {}
                        for m in masters_seeing.values():
                            counter[m] = counter.get(m, 0) + 1
                        last_master = max(counter, key=counter.get)
            if success:
                reconnect_s = int(time.monotonic() - start)
                # Quiet window before the AFTER sample: ``sample_minions``
                # is instantaneous, which races with transient fork
                # pairs (return-channel fork, chunked-register, docker
                # exec children) that are still open the instant the
                # first ping sweep covers the fleet.  See
                # ``SAMPLE_SETTLE_SEC`` in ``tests/resiliency/durations.py``.
                #
                # Pause the workload pgroup (if the ``workload`` fixture
                # is active) across the settle + sample so continuous
                # ping / grains / state / runner traffic from
                # ``workload.sh`` doesn't inflate the minion working
                # set after recovery and trip the leak gate as if the
                # growth were fault-induced.  Without this, run
                # 43773954141 showed clock_/disk_/fs_ tests growing
                # 200-3000 KB/min on workload-driven minions even
                # though no fault leak existed.  ``pause_workload``
                # is a no-op for tests that don't take the fixture.
                self.pause_workload()
                try:
                    if SAMPLE_SETTLE_SEC > 0:
                        time.sleep(SAMPLE_SETTLE_SEC)
                    after = self.sample_minions()
                finally:
                    self.resume_workload()
                delta = after - before
                fd_delta = delta.fds
                rss_delta_kb = delta.rss_kb

                # Minute-normalised slope over fault + reconnect, floored
                # at 60 s so sub-minute phases don't inflate the ratio.
                elapsed = fault_sec + reconnect_s
                if elapsed < 60:
                    elapsed = 60
                rss_per_min = rss_delta_kb * 60 // elapsed

                # Leak gate: slope alone is not a leak signature.  A
                # fault scenario that runs 25 s can legitimately grow
                # several MB of working set as minions repopulate
                # caches.  Only fail when there is also a *retention*
                # signal -- either fd count accumulated (progressive
                # leak) or absolute growth is large (bulk retention).
                # Values below those gates record RECOVERED and let
                # the analyzer flag trends across runs instead.
                # Scale the fd gate by minion count: `sample_minions`
                # sums fds across every container in `spec.minion_containers`,
                # so a single transient allocation on any one minion
                # produces +1 in the fleet total.  Require at least
                # `MIN_FD_DELTA_PER_MINION` per minion before declaring
                # accumulation.
                fd_threshold = MIN_FD_DELTA_PER_MINION * max(
                    1, len(self.spec.minion_containers)
                )
                # ``allow_fault_rss`` is the full fault-work opt-out;
                # it implies both fd-accumulation and bulk-RSS
                # exemption.  Resolve it into the finer-grained flags
                # so downstream tracking (reason=..., leak_notes) still
                # reflects which branch would have tripped.
                if allow_fault_rss:
                    allow_fd_accumulation = True
                    allow_bulk_rss = True
                leak_fd = (not allow_fd_accumulation) and fd_delta > fd_threshold
                # Bulk-RSS retention is skipped when the caller opts out
                # (``allow_bulk_rss=True``) for scenarios with legitimate
                # one-shot cold-start growth (module reload after first
                # reconnect).  fd accumulation is still gated so an
                # auth-future / async-return socket leak would still
                # surface -- unless ``allow_fd_accumulation`` /
                # ``allow_fault_rss`` is also set for fault-work tests.
                leak_bulk = (not allow_bulk_rss) and rss_delta_kb > LEAK_BULK_RSS_KB
                if rss_per_min > RSS_LEAK_KB_PER_MIN and (leak_fd or leak_bulk):
                    reason = "fd_accumulation" if leak_fd else "bulk_rss_retention"
                    leak_notes = (
                        f"rss_kb_per_min={rss_per_min} "
                        f"threshold={RSS_LEAK_KB_PER_MIN} "
                        f"reason={reason}"
                    )
                    full_notes = f"{notes}; {leak_notes}" if notes else leak_notes
                    log.error(
                        "LEAK %r recovered after %ds via %s but RSS grew "
                        "%d KB/min > %d KB/min (reason=%s)",
                        scenario,
                        reconnect_s,
                        last_master,
                        rss_per_min,
                        RSS_LEAK_KB_PER_MIN,
                        reason,
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
                        f"(fd_delta={fd_delta} rss_delta_kb={rss_delta_kb} "
                        f"reason={reason})"
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
        """Record one resiliency row on ``item.user_properties``.

        The ``conftest`` hook picks up the first ``"resiliency"`` tuple
        and writes JSONL.  To stay compatible with scenarios that
        already seeded a partial dict via ``conftest.stash_result``
        (outcome + notes, no deltas), MERGE our fields into the
        existing tuple instead of appending a second one.  A second
        tuple would get silently dropped by ``_extract_stash`` and the
        real deltas would never reach results.jsonl -- which was the
        original silent-drop bug.

        If no prior tuple exists, append a fresh one.  The key MUST
        match ``conftest.py``'s ``_extract_stash`` / ``stash_result``
        (all three use ``"resiliency"``).
        """
        if item is None:
            return
        user_properties = getattr(item, "user_properties", None)
        if user_properties is None:
            return
        try:
            for key, value in user_properties:
                if key == "resiliency" and isinstance(value, dict):
                    value.update(fields)
                    return
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
        start = time.monotonic()
        iteration = 0
        last_keys_seen: set[str] = set()
        last_ping_seen: set[str] = set()

        while time.monotonic() < deadline:
            iteration += 1
            # Gate 1: every expected id is an accepted key on some
            # master.  Cheap -- one salt-key -L per master.
            keys_seen: set[str] = set()
            for m in masters:
                for mid in self.salt_key_accepted_on(m):
                    if mid in expected:
                        keys_seen.add(mid)
            last_keys_seen = keys_seen
            if not expected.issubset(keys_seen):
                # Periodic progress so a stuck gate isn't silent for
                # the full timeout window -- helps diagnose cluster3
                # bringup regressions without having to rummage in the
                # compose.log snapshot.
                if iteration % 6 == 0:
                    elapsed = int(time.monotonic() - start)
                    log.info(
                        "wait_initial_auth[%ss] gate1 keys: %d/%d accepted (missing=%s)",
                        elapsed,
                        len(keys_seen),
                        len(expected),
                        sorted(expected - keys_seen),
                    )
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
            last_ping_seen = ping_seen
            if expected.issubset(ping_seen):
                return True

            if iteration % 6 == 0:
                elapsed = int(time.monotonic() - start)
                log.info(
                    "wait_initial_auth[%ss] gate2 pings: %d/%d responded (missing=%s)",
                    elapsed,
                    len(ping_seen),
                    len(expected),
                    sorted(expected - ping_seen),
                )

            time.sleep(5)

        # Timeout: emit the final observed state so the setup-error row
        # includes actionable context instead of just "timed out".
        log.error(
            "wait_initial_auth timed out after %ds: "
            "keys_seen=%d/%d (missing=%s) pings_seen=%d/%d (missing=%s)",
            timeout,
            len(last_keys_seen),
            len(expected),
            sorted(expected - last_keys_seen),
            len(last_ping_seen),
            len(expected),
            sorted(expected - last_ping_seen),
        )
        return False

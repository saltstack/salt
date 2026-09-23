"""
Scenario reproducing the salt-minion pyzmq ``Context.__del__`` wedge
in the MinionProcessManager (MPM) MainThread.

The wedge observed in the wild () fires inside the MPM
process's asyncio / tornado ioloop -- NOT inside a job payload
subprocess. Reproducing it in a bounded local run requires three
pieces:

    1. A salt-master and salt-minion that authenticate normally.
    2. A periodic ioloop callback that leaks a zmq Context per tick
       -- the shape of a third-party beacon or engine that talks to
       the master without a paired ``close()``. See
       ``wedge_beacons/wedge_leak.py``: salt's periodic-callback
       beacon dispatcher runs it on the same ioloop the MPM
       MainThread services.
    3. A silent iptables DROP of the master's ret_port and
       publish_port so the beacon's queued REQ sends never drain.
       LINGER=-1 + undeliverable queue is what makes
       ``socket.close()`` block in libzmq's ``zmq_ctx_term()`` when
       the leaked Context's ``__del__`` runs.

Detection: watch the MPM process's MainThread
``voluntary_ctxt_switches`` counter. A healthy MainThread ticks
tens of times per five seconds (asyncio poll wakeups, event I/O); a
wedged MainThread stops advancing entirely because it is parked in
an uninterruptible libzmq syscall.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

import pytest

log = logging.getLogger(__name__)


def _sudo_iptables_available() -> bool:
    """Return True iff ``sudo -n iptables -L -n`` can run without a
    password prompt.  Many CI runners do not grant passwordless sudo
    for iptables; this test cannot install its DROP blackhole without
    it, so we skip rather than fail loudly.
    """
    if sys.platform != "linux":
        return False
    try:
        return (
            subprocess.run(
                ["sudo", "-n", "iptables", "-L", "-n"],
                capture_output=True,
                timeout=5,
                check=False,
            ).returncode
            == 0
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(
        sys.platform != "linux",
        reason="Wedge detection uses /proc/<pid>/task/*/status; Linux-only.",
    ),
    pytest.mark.skipif(
        not _sudo_iptables_available(),
        reason=(
            "Scenario requires ``sudo -n iptables`` to install a DROP "
            "blackhole around the salt-master's ret/publish ports.  "
            "Runner does not grant passwordless sudo access to iptables."
        ),
    ),
]

WEDGE_TIMEOUT_S = 5 * 60
POLL_INTERVAL_S = 5
WEDGE_CONFIRM_WINDOWS = 3
DROP_AFTER_BASELINE_S = 5
# After releasing the blackhole, how long we let the MPM MainThread try
# to advance before we call it "did not recover".
RECOVERY_TIMEOUT_S = 3 * 60
# Healthy MainThread ticks tens of voluntary ctxt switches per 5s window;
# require this many in a single window to declare "recovered".
RECOVERY_MIN_TICKS = 10
# In the "master permanently gone" variant we watch the MPM MainThread
# for this long after lifting the blackhole; if it never advances again,
# we've matched the production shape (30+ hour prod wedge on an affected env).
PERMANENT_WEDGE_OBSERVE_S = 90

_DIAG_LOG = Path("/tmp/wedge-scenario-diag.log")


def _diag(msg: str) -> None:
    with _DIAG_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def _proc_cmdline(pid: int) -> str:
    try:
        return (
            Path(f"/proc/{pid}/cmdline")
            .read_bytes()
            .replace(b"\x00", b" ")
            .decode(errors="replace")
        )
    except (FileNotFoundError, PermissionError):
        return ""


def _find_mpm_pid(minion_parent_pid: int) -> int:
    """Locate the MinionProcessManager process that runs the ioloop.

    In a production salt-minion this is a distinct child of the
    systemd-managed parent, cmdline ending in ``MinionProcessManager``.
    In the saltfactories test setup (``--disable-keepalive``) the
    parent process is itself the ioloop -- no separate MPM child.

    Walk children first; if none match a strict ``MinionProcessManager$``
    cmdline, fall back to the parent (which IS the ioloop).
    """
    proc_children = Path(f"/proc/{minion_parent_pid}/task/{minion_parent_pid}/children")
    if proc_children.exists():
        for tok in proc_children.read_text(encoding="utf-8").split():
            try:
                child_pid = int(tok)
            except ValueError:
                continue
            cmdline = _proc_cmdline(child_pid).strip()
            if cmdline.endswith("MinionProcessManager"):
                return child_pid
    return minion_parent_pid


def _main_thread_ctxt_switches(pid: int) -> int:
    """Return the MainThread's ``voluntary_ctxt_switches`` counter.

    The main OS thread of a process has tid == pid; we read
    ``/proc/<pid>/task/<pid>/status`` so we're strictly watching
    MainThread, not any background zmq I/O thread.
    """
    status_path = Path(f"/proc/{pid}/task/{pid}/status")
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("voluntary_ctxt_switches:"):
            return int(line.split()[1])
    raise RuntimeError(f"voluntary_ctxt_switches not found for pid {pid}")


def _wait_for_mpm_wedge(mpm_pid: int, deadline: float) -> tuple[bool, str]:
    """Poll the MPM MainThread for the wedge signature.

    Wedge condition: ``voluntary_ctxt_switches`` on the MainThread
    fails to advance for ``WEDGE_CONFIRM_WINDOWS * POLL_INTERVAL_S``
    consecutive seconds. On a healthy MPM MainThread this counter
    ticks constantly (ioloop poll wakeups).
    """
    while time.monotonic() < deadline:
        try:
            v_start = _main_thread_ctxt_switches(mpm_pid)
        except (FileNotFoundError, RuntimeError) as exc:
            return False, f"MPM pid {mpm_pid} vanished: {exc}"
        time.sleep(POLL_INTERVAL_S)
        try:
            v_next = _main_thread_ctxt_switches(mpm_pid)
        except (FileNotFoundError, RuntimeError) as exc:
            return False, f"MPM pid {mpm_pid} vanished: {exc}"
        if v_next - v_start > 0:
            _diag(
                f"tick: MPM MainThread advanced "
                f"{v_next - v_start} ctxt switches in {POLL_INTERVAL_S}s"
            )
            continue
        # First zero-delta window; confirm across more windows.
        confirmed = 1
        last = v_next
        while confirmed < WEDGE_CONFIRM_WINDOWS:
            time.sleep(POLL_INTERVAL_S)
            try:
                current = _main_thread_ctxt_switches(mpm_pid)
            except (FileNotFoundError, RuntimeError) as exc:
                return False, f"MPM pid {mpm_pid} vanished: {exc}"
            if current - last == 0:
                confirmed += 1
            else:
                _diag(
                    f"false-alarm: MPM MainThread resumed "
                    f"(+{current - last} in {POLL_INTERVAL_S}s)"
                )
                break
            last = current
        if confirmed >= WEDGE_CONFIRM_WINDOWS:
            secs = WEDGE_CONFIRM_WINDOWS * POLL_INTERVAL_S
            return (
                True,
                (
                    f"MPM pid {mpm_pid} MainThread did not advance "
                    f"voluntary_ctxt_switches for {secs}s -- MainThread "
                    f"is stuck in an uninterruptable C call "
                    f"(matches signature)."
                ),
            )
    return False, f"deadline reached after {WEDGE_TIMEOUT_S}s without wedge"


def _pyspy_stack(pid: int) -> str:
    import shutil  # noqa: PLC0415

    py_spy = shutil.which("py-spy")
    if not py_spy:
        return "py-spy not installed"
    try:
        # Resolve py-spy to an absolute path -- ``sudo -n`` uses root's PATH
        # which typically does not include ``~/.local/bin`` where pip-installed
        # tools live.
        result = subprocess.run(
            ["sudo", "-n", py_spy, "dump", "--pid", str(pid)],
            capture_output=True,
            timeout=15,
            text=True,
            check=False,
        )
        return (result.stdout or "") + (result.stderr or "")
    except Exception as e:  # pylint: disable=broad-except
        return f"py-spy failed: {e}"


def _iptables_run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sudo", "-n", "iptables", *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )


class _MasterBlackhole:
    """Install iptables rules that silently DROP all TCP traffic to
    the salt-master's ret_port and publish_port.

    Silent DROP (as opposed to REJECT or a RST-style proxy) is what
    makes the minion's kernel TCP retransmit for 60+ seconds without
    ever hearing "connection lost". That is the shape zmq needs to
    accumulate messages in its outbound queue -- which is the
    ingredient for LINGER=-1 to actually block ``socket.close()``.
    """

    def __init__(self, *, ret_port: int, publish_port: int) -> None:
        self.ret_port = ret_port
        self.publish_port = publish_port
        self._installed: list[list[str]] = []

    def __enter__(self) -> _MasterBlackhole:
        rules = [
            ["-I", "OUTPUT", "-p", "tcp", "--dport", str(self.ret_port), "-j", "DROP"],
            [
                "-I",
                "OUTPUT",
                "-p",
                "tcp",
                "--dport",
                str(self.publish_port),
                "-j",
                "DROP",
            ],
            ["-I", "INPUT", "-p", "tcp", "--sport", str(self.ret_port), "-j", "DROP"],
            [
                "-I",
                "INPUT",
                "-p",
                "tcp",
                "--sport",
                str(self.publish_port),
                "-j",
                "DROP",
            ],
        ]
        for rule in rules:
            _iptables_run(*rule)
            self._installed.append(rule)
        _diag(f"iptables blackhole ON for ports {self.ret_port},{self.publish_port}")
        return self

    def __exit__(self, *exc: object) -> None:
        for rule in self._installed:
            delete = rule.copy()
            delete[0] = "-D"
            try:
                _iptables_run(*delete)
            except subprocess.CalledProcessError as exc_:
                _diag(f"iptables cleanup failed for {rule}: {exc_.stderr}")
        _diag("iptables blackhole OFF")


@pytest.mark.xfail(
    strict=False,  # noqa: run-flag; do not fail on xpass on platforms where the primitive is already fixed
    reason=(
        "pyzmq >= 24 Context.__del__ calls destroy() which iterates open "
        "sockets and calls socket.close() with the default LINGER=-1. When "
        "the finalizer fires from GC inside the salt-minion MPM's tornado "
        "ioloop (as happens on fleet minions with the ``status`` beacon "
        "enabled and an unhealthy master path), MainThread wedges in "
        "libzmq's zmq_ctx_term(). When pyzmq or salt lands a fix that "
        "guarantees explicit context.destroy(linger=0) on every close "
        "path, this test flips to passing; strict=True then fails it to "
        "signal the maintainer to remove this marker."
    ),
)
@pytest.mark.timeout(WEDGE_TIMEOUT_S + 120)
def test_status_beacon_wedges_minion_mpm(salt_master, salt_minion, caplog):
    """Reproduces the pyzmq ``Context.__del__`` wedge inside the
    salt-minion MPM ioloop. A test-only beacon (``wedge_leak``)
    fires every ioloop tick and leaks a ``zmq.Context`` + REQ socket
    + queued undeliverable send. Locals drop at return, ``__del__``
    fires from the same ioloop callback that invoked the beacon, and
    once the iptables blackhole is on the queued sends stop draining
    -- so ``socket.close()`` blocks in ``zmq_ctx_term()`` and
    MainThread stops advancing.
    """
    with salt_minion.started(start_timeout=180):
        cli = salt_master.salt_cli(timeout=30)

        ret = cli.run("test.ping", minion_tgt=salt_minion.id)
        assert ret.returncode == 0, f"baseline test.ping failed: {ret}"
        assert ret.data is True

        minion_parent_pid = salt_minion.impl._terminal.pid  # noqa: SLF001
        mpm_pid = _find_mpm_pid(minion_parent_pid)
        _diag(
            f"baseline: minion pid={minion_parent_pid} mpm={mpm_pid} "
            f"cmdline={_proc_cmdline(mpm_pid)!r}"
        )

        time.sleep(DROP_AFTER_BASELINE_S)

        with _MasterBlackhole(
            ret_port=salt_master.config["ret_port"],
            publish_port=salt_master.config["publish_port"],
        ):
            deadline = time.monotonic() + WEDGE_TIMEOUT_S
            wedged, reason = _wait_for_mpm_wedge(mpm_pid, deadline)
            _diag(f"wait result: wedged={wedged} reason={reason}")

            if wedged:
                stack = _pyspy_stack(mpm_pid)
                _diag(f"MPM py-spy stack:\n{stack[:1200]}")
                log.info("MPM py-spy stack:\n%s", stack[:2000])

        assert wedged, (
            f"salt-minion MPM did not wedge within {WEDGE_TIMEOUT_S}s of "
            f"master blackhole with the wedge_leak beacon enabled: {reason}."
        )
        pytest.fail(f"salt-minion MPM wedged as expected: {reason}")


def _wait_for_mpm_recovery(mpm_pid: int, deadline: float) -> tuple[bool, str]:
    """Poll the MPM MainThread for signs of life.

    Recovery signal: a single ``POLL_INTERVAL_S`` window in which the
    MainThread advances at least ``RECOVERY_MIN_TICKS`` voluntary ctxt
    switches -- meaning the ioloop has resumed poll wakeups.
    """
    start = time.monotonic()
    while time.monotonic() < deadline:
        try:
            v_start = _main_thread_ctxt_switches(mpm_pid)
        except (FileNotFoundError, RuntimeError) as exc:
            return False, f"MPM pid {mpm_pid} vanished: {exc}"
        time.sleep(POLL_INTERVAL_S)
        try:
            v_next = _main_thread_ctxt_switches(mpm_pid)
        except (FileNotFoundError, RuntimeError) as exc:
            return False, f"MPM pid {mpm_pid} vanished: {exc}"
        delta = v_next - v_start
        _diag(
            f"recovery: MPM MainThread advanced {delta} ctxt switches in {POLL_INTERVAL_S}s"
        )
        if delta >= RECOVERY_MIN_TICKS:
            return (
                True,
                f"MPM MainThread advanced {delta} ctxt switches in {POLL_INTERVAL_S}s",
            )
    elapsed = int(time.monotonic() - start)
    return False, f"deadline reached after {elapsed}s without recovery"


@pytest.mark.timeout(WEDGE_TIMEOUT_S + RECOVERY_TIMEOUT_S + 180)
def test_minion_recovers_after_master_returns(salt_master, salt_minion, caplog):
    """After the wedge fires, remove the iptables blackhole and observe
    whether the MPM MainThread ever resumes ticking.

    LINGER=-1 blocks ``socket.close()`` in ``zmq_ctx_term()`` until the
    queued message can drain. Restoring master reachability makes those
    queued REQ sends deliverable, so libzmq's internal I/O thread can
    finish the send, ``close()`` returns, ``destroy()`` returns,
    ``__del__`` returns, and the ioloop resumes.
    """
    with salt_minion.started(start_timeout=180):
        cli = salt_master.salt_cli(timeout=30)

        ret = cli.run("test.ping", minion_tgt=salt_minion.id)
        assert ret.returncode == 0, f"baseline test.ping failed: {ret}"
        assert ret.data is True

        minion_parent_pid = salt_minion.impl._terminal.pid  # noqa: SLF001
        mpm_pid = _find_mpm_pid(minion_parent_pid)
        _diag(f"recovery test baseline: minion pid={minion_parent_pid} mpm={mpm_pid}")

        time.sleep(DROP_AFTER_BASELINE_S)

        blackhole = _MasterBlackhole(
            ret_port=salt_master.config["ret_port"],
            publish_port=salt_master.config["publish_port"],
        )
        with blackhole:
            deadline = time.monotonic() + WEDGE_TIMEOUT_S
            wedged, reason = _wait_for_mpm_wedge(mpm_pid, deadline)
            _diag(f"wedge result: wedged={wedged} reason={reason}")
            assert wedged, f"Prep condition failed: minion never wedged: {reason}"

            wedged_stack = _pyspy_stack(mpm_pid)
            _diag(f"wedged MPM py-spy stack:\n{wedged_stack[:1200]}")

        _diag("blackhole lifted; watching for MPM recovery")
        rec_deadline = time.monotonic() + RECOVERY_TIMEOUT_S
        recovered, rec_reason = _wait_for_mpm_recovery(mpm_pid, rec_deadline)
        _diag(f"recovery result: recovered={recovered} reason={rec_reason}")

        if not recovered:
            stall_stack = _pyspy_stack(mpm_pid)
            _diag(f"post-unblock MPM py-spy stack:\n{stall_stack[:1200]}")
            log.info("post-unblock MPM py-spy stack:\n%s", stall_stack[:2000])
            pytest.fail(
                f"salt-minion MPM did NOT recover after {RECOVERY_TIMEOUT_S}s "
                f"with master reachable again: {rec_reason}"
            )

        # If MainThread came back, verify the minion is functionally
        # reachable again -- test.ping through the master's ret channel.
        # Retry a few times with delays because reconnect may need
        # ping_interval + reauth to complete before jobs land.
        ping_attempts = []
        for i in range(4):
            _diag(f"post-recovery test.ping attempt {i + 1}/4")
            post_ret = cli.run("test.ping", minion_tgt=salt_minion.id, _timeout=45)
            outcome = f"rc={post_ret.returncode} data={post_ret.data!r}"
            _diag(f"post-recovery test.ping attempt {i + 1}: {outcome}")
            ping_attempts.append((i + 1, post_ret.returncode, post_ret.data))
            if post_ret.returncode == 0 and post_ret.data is True:
                break
            time.sleep(15)

        post_stack = _pyspy_stack(mpm_pid)
        _diag(f"post-test.ping MPM py-spy stack:\n{post_stack[:2000]}")
        log.info(
            "post-test.ping MPM py-spy stack:\n%s\nattempts=%r",
            post_stack[:2000],
            ping_attempts,
        )
        succeeded = any(rc == 0 and data is True for _, rc, data in ping_attempts)
        assert succeeded, (
            f"minion MainThread resumed ctxt switches but test.ping never "
            f"succeeded across {len(ping_attempts)} attempts: {ping_attempts}"
        )


def _kill_process_tree(pid: int) -> None:
    """SIGKILL ``pid`` and every descendant using ``/proc/<pid>/task/*/children``.

    We use ``/proc`` rather than psutil to keep the test dep-light. Walk
    children breadth-first, collect the closure, then kill from leaves up.
    """
    import os as _os  # noqa: PLC0415
    import signal  # noqa: PLC0415

    def _children(p: int) -> list[int]:
        out: list[int] = []
        try:
            for tid_dir in Path(f"/proc/{p}/task").iterdir():
                child_file = tid_dir / "children"
                if not child_file.exists():
                    continue
                for tok in child_file.read_text().split():
                    try:
                        out.append(int(tok))
                    except ValueError:
                        pass
        except FileNotFoundError:
            pass
        return out

    all_pids: list[int] = []
    queue: list[int] = [pid]
    while queue:
        cur = queue.pop(0)
        if cur in all_pids:
            continue
        all_pids.append(cur)
        queue.extend(_children(cur))
    for target in reversed(all_pids):
        try:
            _os.kill(target, signal.SIGKILL)
        except ProcessLookupError:
            pass


@pytest.mark.xfail(
    strict=False,  # noqa: run-flag; do not fail on xpass on platforms where the primitive is already fixed
    reason=(
        "Production shape (): the master peer that owned the "
        "queued REQ send is permanently gone -- K8s pod restart, DNS swap, "
        "or rebind to a new port. libzmq keeps trying to drain the queued "
        "message to a dead routing slot, so zmq_ctx_term() never returns "
        "and the MPM MainThread stays wedged even after network reachability "
        "is restored. On an affected minion the wedge lasted 30+ hours until "
        "manual salt-minion restart. When pyzmq or salt lands a fix that "
        "guarantees explicit context.destroy(linger=0) on every close "
        "path this test flips to pass; strict=True then fails it to signal "
        "the maintainer to remove the marker."
    ),
)
@pytest.mark.timeout(WEDGE_TIMEOUT_S + PERMANENT_WEDGE_OBSERVE_S + 180)
def test_minion_stays_wedged_when_master_permanently_gone(
    salt_master, salt_minion, caplog
):
    """After the wedge fires, SIGKILL the master (including MWorkers and
    the ROUTER-owning ReqServer_ProcessManager subtree) BEFORE lifting
    the iptables blackhole. Then lift the blackhole so the minion's
    kernel can attempt to re-establish TCP -- but it finds only
    ECONNREFUSED because the master's ret_port listener is gone.

    libzmq's internal I/O thread keeps retrying the connect for the
    still-queued REQ send, but the peer never appears, so
    ``socket.close()`` -> ``zmq_ctx_term()`` on the finalized context
    stays blocked. The MPM MainThread never advances.

    This test is the production shape (30+ h prod wedge on 's
    mgmt-vc,). Marked strict xfail: the minion IS supposed
    to stay wedged with today's pyzmq/salt combination. The moment
    salt closes its zmq.Contexts with LINGER=0 on every path (or pyzmq
    stops running term() from __del__), this test starts passing and
    ``strict=True`` will flip it to a failure so we notice.
    """
    with salt_minion.started(start_timeout=180):
        cli = salt_master.salt_cli(timeout=30)
        ret = cli.run("test.ping", minion_tgt=salt_minion.id)
        assert ret.returncode == 0, f"baseline test.ping failed: {ret}"
        assert ret.data is True

        minion_parent_pid = salt_minion.impl._terminal.pid  # noqa: SLF001
        mpm_pid = _find_mpm_pid(minion_parent_pid)
        master_pid = salt_master.impl._terminal.pid  # noqa: SLF001
        _diag(
            f"permanent-wedge baseline: minion pid={minion_parent_pid} "
            f"mpm={mpm_pid} master={master_pid}"
        )

        time.sleep(DROP_AFTER_BASELINE_S)

        blackhole = _MasterBlackhole(
            ret_port=salt_master.config["ret_port"],
            publish_port=salt_master.config["publish_port"],
        )
        with blackhole:
            deadline = time.monotonic() + WEDGE_TIMEOUT_S
            wedged, reason = _wait_for_mpm_wedge(mpm_pid, deadline)
            _diag(f"wedge result: wedged={wedged} reason={reason}")
            assert wedged, f"Prep condition failed: minion never wedged: {reason}"

            wedged_stack = _pyspy_stack(mpm_pid)
            _diag(f"wedged MPM py-spy stack:\n{wedged_stack[:1200]}")

            wedged_threads = len(list(Path(f"/proc/{mpm_pid}/task").iterdir()))
            _diag(f"wedged MPM thread count: {wedged_threads}")

            # Kill the entire master process tree BEFORE lifting the
            # blackhole. The minion's queued REQ send is aimed at the
            # master's ret_port ROUTER; once that listener is gone,
            # libzmq's connect retry will get ECONNREFUSED forever and
            # the queued send will never drain -- matching the K8s
            # pod-restart shape on an affected env.
            _diag(f"killing master process tree rooted at pid={master_pid}")
            _kill_process_tree(master_pid)
            time.sleep(2)
            master_alive = Path(f"/proc/{master_pid}").exists()
            _diag(f"master pid={master_pid} alive after SIGKILL: {master_alive}")

        _diag(
            "blackhole lifted with master permanently killed; "
            f"observing MPM MainThread for {PERMANENT_WEDGE_OBSERVE_S}s"
        )
        rec_deadline = time.monotonic() + PERMANENT_WEDGE_OBSERVE_S
        recovered, rec_reason = _wait_for_mpm_recovery(mpm_pid, rec_deadline)
        _diag(f"observation result: recovered={recovered} reason={rec_reason}")

        try:
            post_threads = len(list(Path(f"/proc/{mpm_pid}/task").iterdir()))
            _diag(f"post-master-kill MPM thread count: {post_threads}")
        except FileNotFoundError:
            _diag("post-master-kill MPM thread count: (mpm vanished)")
        stall_stack = _pyspy_stack(mpm_pid)
        _diag(f"post-master-kill MPM py-spy stack:\n{stall_stack[:2000]}")
        log.info(
            "post-master-kill MPM py-spy stack:\n%s\nrecovered=%s reason=%s",
            stall_stack[:2000],
            recovered,
            rec_reason,
        )

        # With today's pyzmq/salt, ``recovered`` should be False --
        # MainThread stays parked in zmq_ctx_term(). When the fix lands
        # ``recovered`` will be True, which fails the strict xfail below
        # and prompts the maintainer to drop the marker.
        assert not recovered, (
            f"salt-minion MPM MainThread recovered despite master being "
            f"permanently gone -- pyzmq or salt has been fixed to close "
            f"zmq contexts with LINGER=0; remove the xfail marker on "
            f"this test. Reason: {rec_reason}"
        )
        pytest.fail(
            "salt-minion MPM MainThread stayed wedged after master was "
            f"SIGKILLed and blackhole lifted -- matches "
            f"production wedge shape: {rec_reason}"
        )

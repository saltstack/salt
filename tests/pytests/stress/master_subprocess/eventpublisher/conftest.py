"""
Fixture for isolated ``EventPublisher`` (EP) subprocess stress tests.

Design choice — **real multiprocessing subprocess** (via
``salt.utils.process.ProcessManager.add_process`` — the *actual* production
entrypoint used in ``salt/channel/server.py:2857``):

* Fork semantics, pickle round-trip, IOLoop lifecycle all match production.
* RSS / FD probes run against a distinct PID, which the tests exercise.
* EP crashes are isolated from the pytest driver process.
* Trade-off: talking to EP requires real TCP-IPC sockets, which is exactly
  what production does — so tests double as end-to-end socket-contract
  tests for the EP wire protocol.

The alternative (spin EP up as an asyncio task in-process on a thread)
is faster but obscures the very failure modes we care about: subprocess
crash, FD leak, RSS growth, subprocess-level signal handling.
"""

from __future__ import annotations

import multiprocessing
import os
import pathlib
import shutil
import socket
import time
from dataclasses import dataclass, field

import pytest

import salt.channel.server
import salt.config
import salt.transport.base
import salt.transport.tcp
import salt.utils.files
import salt.utils.process


def _find_free_port() -> int:
    """
    Grab a free TCP port and immediately release it.  Race-prone in
    theory; safe in practice because the EP subprocess will bind here in
    a few ms and we use ``SO_REUSEADDR`` in production sockets.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_master_opts(root: pathlib.Path, overrides: dict | None = None) -> dict:
    """
    Return a minimal master opts dict, sufficient to bring up
    ``MasterPubServerChannel._publish_daemon``.

    We deliberately construct the opts by starting from
    ``salt.config.master_config`` defaults with a nonexistent config
    path (so nothing on the host bleeds in) and layering the tiny set of
    overrides EP actually reads.
    """
    pki_dir = root / "pki"
    cache_dir = root / "cache"
    sock_dir = root / "sock"
    for path in (pki_dir, cache_dir, sock_dir):
        path.mkdir(parents=True, exist_ok=True)

    overrides = dict(overrides or {})
    # ``ipc_mode = ipc`` uses UNIX domain sockets for the event bus.  On
    # Linux, socket path length is capped at ~108 chars — keep sock_dir
    # short by rooting under root/sock (not root/lots/of/nesting/sock).
    base = {
        "id": "stress-ep-master",
        "root_dir": str(root),
        "pki_dir": str(pki_dir),
        "cachedir": str(cache_dir),
        "sock_dir": str(sock_dir),
        "conf_file": str(root / "master"),
        "user": None,
        "transport": "tcp",
        "ipc_mode": "ipc",
        "cluster_id": None,
        "cluster_peers": [],
        # We don't actually use these ports (ipc_mode=ipc uses UNIX
        # sockets), but master_config validates them.
        "publish_port": _find_free_port(),
        "ret_port": _find_free_port(),
    }
    base.update(overrides)
    # ``master_config()`` reads the file at path.  We don't want any host
    # config bleed-in, so drive ``apply_master_config`` directly with our
    # overrides.  This is the same call ``master_config()`` ends with,
    # minus the include-file loading.
    opts = salt.config.apply_master_config(overrides=base)
    # Force our overrides — apply_master_config sometimes reshapes.
    opts["sock_dir"] = str(sock_dir)
    opts["pki_dir"] = str(pki_dir)
    opts["cachedir"] = str(cache_dir)
    opts["id"] = base["id"]
    opts["transport"] = "tcp"
    opts["ipc_mode"] = "ipc"
    opts["cluster_id"] = None
    opts["cluster_peers"] = []
    return opts


@dataclass
class EPHandle:
    """
    Handle exposed to tests for talking to / observing the EP subprocess.
    """

    opts: dict
    pull_path: str
    pub_path: str
    process: multiprocessing.Process
    process_manager: salt.utils.process.ProcessManager
    root: pathlib.Path
    _stopped: bool = field(default=False)

    def is_alive(self) -> bool:
        return self.process is not None and self.process.is_alive()

    def rss_bytes(self) -> int:
        """
        Read RSS for the EP subprocess via ``/proc/<pid>/status`` — no
        external psutil dep, Linux-only.  Returns 0 if the file is
        unavailable or the process is gone.
        """
        try:
            with salt.utils.files.fopen(
                f"/proc/{self.process.pid}/status", encoding="utf-8"
            ) as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) * 1024
        except OSError:
            pass
        return 0

    def fd_count(self) -> int:
        """
        Count open FDs on the EP subprocess.  Linux-specific.
        """
        try:
            return len(os.listdir(f"/proc/{self.process.pid}/fd"))
        except OSError:
            return 0

    def stop(self, timeout: float = 5.0) -> None:
        if self._stopped:
            return
        self._stopped = True
        try:
            self.process_manager.stop_restarting()
            self.process_manager.terminate()
        except Exception:  # pylint: disable=broad-except
            pass
        if self.process is not None and self.process.is_alive():
            self.process.join(timeout=timeout)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1.0)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(timeout=1.0)


def _wait_for_socket(path: str, timeout: float = 15.0) -> None:
    """
    Block until the UNIX socket at *path* exists AND accepts a
    connection.  ``os.path.exists`` alone races EP's ``bind`` vs
    ``listen``.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(path):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect(path)
                s.close()
                return
            except OSError:
                pass
        time.sleep(0.05)
    raise RuntimeError(f"EP socket {path} did not become ready in {timeout}s")


def _spawn_ep(opts: dict, root: pathlib.Path) -> EPHandle:
    """
    Spawn EP as its own subprocess using the same ProcessManager +
    ``MasterPubServerChannel._publish_daemon`` path production uses.
    """
    # Instantiating MasterPubServerChannel in the *parent* process would
    # eagerly build MasterKeys (RSA gen — expensive) and hold a copy of
    # the transport bound in the parent's io_loop.  Production's
    # pre_fork() runs in the parent and hands the callable off to a
    # process; the child process re-imports and re-instantiates.  Do the
    # same: build the channel here, then hand its bound method to
    # ProcessManager.
    channel = salt.channel.server.MasterPubServerChannel.factory(opts)

    pm = salt.utils.process.ProcessManager(name="StressEP")
    proc = pm.add_process(
        channel._publish_daemon,
        kwargs={},
        name="EventPublisher",
    )

    pull_path = os.path.join(opts["sock_dir"], "master_event_pull.ipc")
    pub_path = os.path.join(opts["sock_dir"], "master_event_pub.ipc")
    try:
        _wait_for_socket(pull_path)
        _wait_for_socket(pub_path)
    except RuntimeError:
        # If startup failed dump child status for triage then re-raise.
        pm.stop_restarting()
        pm.terminate()
        raise

    return EPHandle(
        opts=opts,
        pull_path=pull_path,
        pub_path=pub_path,
        process=proc,
        process_manager=pm,
        root=root,
    )


@pytest.fixture
def ep_root(tmp_path_factory) -> pathlib.Path:
    """
    Short-path scratch dir for one EP invocation.  Deliberately
    per-test-function so subprocess crashes don't poison a session-scoped
    fixture.  ``sock_dir`` inside must stay under ~90 chars (UNIX socket
    path limit).
    """
    # ``tmp_path_factory`` roots under ``/tmp/pytest-of-<user>/…`` which
    # can be 60+ chars already — nest minimally.
    base = tmp_path_factory.mktemp("ep", numbered=True)
    yield base
    # Best-effort cleanup — subprocess may still hold FDs briefly.
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture
def ep_opts_overrides() -> dict:
    """
    Override in a test with ``@pytest.mark.parametrize`` or a nested
    fixture to feed opts (e.g. ``publish_drain_timeout``) into the EP
    subprocess.
    """
    return {}


@pytest.fixture
def ep(ep_root, ep_opts_overrides):
    """
    Spawn the EP subprocess once per test.  Yields an ``EPHandle``.
    Teardown terminates the subprocess.
    """
    opts = _build_master_opts(ep_root, overrides=ep_opts_overrides)
    handle = _spawn_ep(opts, ep_root)
    try:
        yield handle
    finally:
        handle.stop()

"""
File-sentinel health probes for Kubernetes (and other supervisors).

Three independent sentinels live under ``<cachedir>/health/``:

* ``startup``   — written once when ``Master.start`` finishes wiring up
                  every subprocess.  Maps to a Kubernetes
                  ``startupProbe`` (``test -f <cachedir>/health/startup``).
* ``ready``     — written once when the master is willing to serve
                  traffic.  For a clustered master that means the Raft
                  ``cluster_ready`` event has fired (the node committed
                  itself as a voter).  For a non-clustered master we
                  write it at the same time as ``startup`` because there
                  is no cluster gate.  Maps to a Kubernetes
                  ``readinessProbe``.
* ``alive``     — touched periodically from the parent process's
                  asyncio loop.  If the loop wedges the mtime stops
                  advancing, so an exec probe ``test $(($(date +%s) -
                  $(stat -c %Y .../health/alive))) -lt 30`` flips
                  ``unready`` and Kubernetes restarts the pod.  Maps to
                  a Kubernetes ``livenessProbe``.

Why files (not HTTP):

  * No new listening port, no extra dependency, no thread/process for
    a tiny web server.
  * ``exec`` probes work everywhere (kubelet, docker-compose
    healthchecks, systemd ``ExecStartPost`` waits).
  * Easy to inspect by hand: ``ls -l /var/cache/salt/master/health/``.

Why three sentinels (not one):

  * **Cardinal rule from etcd's incident history**: liveness must never
    reflect cluster state.  Making liveness depend on Raft leader
    availability caused kubelet to SIGKILL pods *during* legitimate
    leader elections, preventing the elections from completing.  Each
    sentinel answers a distinct question (Initialised? Routable?
    Responsive?) so the answers can disagree.

References:
  * https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/
  * https://github.com/etcd-io/etcd/issues/13340
"""

import logging
import os
import pathlib
import shutil
import time

log = logging.getLogger(__name__)

#: Subdirectory under ``cachedir`` that holds the three sentinels.
HEALTH_DIR = "health"

#: Sentinel filename for the startup probe.
STARTUP_SENTINEL = "startup"

#: Sentinel filename for the readiness probe.
READY_SENTINEL = "ready"

#: Sentinel filename for the liveness probe.
ALIVE_SENTINEL = "alive"

#: Default interval in seconds between ``touch_alive`` heartbeats.  Pair
#: with a Kubernetes ``livenessProbe`` ``periodSeconds: 15`` and a
#: staleness threshold of 30 s in the exec probe.
DEFAULT_ALIVE_INTERVAL = 5


def health_dir(opts):
    """
    Return the on-disk path of ``<cachedir>/health``.

    Returns ``None`` if ``opts`` has no ``cachedir`` (typical of unit
    tests using a stripped opts dict); callers treat that as "no
    health checks configured" and silently skip.  This keeps the
    helpers safe to wire into shared code paths like
    ``_signal_cluster_ready`` that run in production *and* in tests
    with hand-crafted opts.
    """
    cachedir = opts.get("cachedir")
    if not cachedir:
        return None
    return pathlib.Path(cachedir) / HEALTH_DIR


def reset_health_dir(opts):
    """
    Wipe and recreate ``<cachedir>/health/``.

    Called once near the top of ``Master.start`` so a stale ``startup``
    or ``ready`` sentinel from a previous run cannot pass a probe before
    the freshly-started master is actually ready.

    Errors are logged and swallowed: a missing health dir is *not* a
    reason to refuse to start the master, so health-check writes are
    best-effort.
    """
    path = health_dir(opts)
    if path is None:
        return
    try:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("healthchecks: could not reset %s: %s", path, exc)


def _write_sentinel(opts, name, body=""):
    """Write a sentinel file atomically.  Best-effort; logs and returns on error."""
    base = health_dir(opts)
    if base is None:
        return
    path = base / name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic-ish: write to ``.tmp`` then rename.  Avoids a probe
        # observing a half-written file even though our payloads are
        # tiny.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.warning("healthchecks: could not write %s: %s", path, exc)


def mark_startup_complete(opts):
    """
    Write ``<cachedir>/health/startup`` once master init is done.

    Body is the unix epoch second the master finished bootstrapping —
    handy for ``kubectl describe`` and post-mortems.
    """
    _write_sentinel(opts, STARTUP_SENTINEL, body=str(int(time.time())))
    log.info("healthchecks: startup sentinel written at %s", health_dir(opts))


def mark_cluster_ready(opts):
    """
    Write ``<cachedir>/health/ready`` when the master is willing to serve
    traffic.  Idempotent — a second call is harmless.
    """
    _write_sentinel(opts, READY_SENTINEL, body=str(int(time.time())))
    log.info("healthchecks: readiness sentinel written at %s", health_dir(opts))


def touch_alive(opts):
    """
    Refresh the mtime of ``<cachedir>/health/alive``.

    The exec probe compares ``time.time() - stat(alive).st_mtime`` to a
    threshold (recommend 3× ``DEFAULT_ALIVE_INTERVAL``).  Stops
    advancing if the parent process's asyncio loop wedges, which is the
    exact failure mode liveness is supposed to catch.
    """
    base = health_dir(opts)
    if base is None:
        return
    path = base / ALIVE_SENTINEL
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # ``open(...) + close()`` would work but pathlib.Path.touch is
        # one syscall on Python 3.10+.
        path.touch(exist_ok=True)
        # ``Path.touch`` on Python < 3.10 only updates atime/mtime if
        # the file already exists *and* doesn't always bump them on
        # every filesystem.  Force a definite mtime update via
        # os.utime so ``stat -c %Y`` always advances.
        now = time.time()
        os.utime(path, (now, now))
    except OSError as exc:
        log.warning("healthchecks: could not touch %s: %s", path, exc)


def is_clustered(opts):
    """``True`` if the master is configured for cluster mode."""
    return bool(opts.get("cluster_id") and opts.get("cluster_peers") is not None)

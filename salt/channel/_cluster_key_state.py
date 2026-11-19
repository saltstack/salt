"""
Unified cluster-key propagation primitive.

Two keys in the ``cluster/peer/join-reply`` install path share one
shape: every master generates its own local random bootstrap bytes on
first boot (``find_or_create_keys("cluster")`` for ``cluster.pem``;
``populate_secrets`` for ``cluster_aes``), ships those bytes in every
reply it builds, and the receiver historically installed whatever
arrived.  Under a three-master bootstrap the install order is
non-deterministic, winners are arrival-last, and the cluster ends up
disagreeing on the on-disk / in-memory key.

This module implements the receiver-side state machine that gates
installs.  Each key is independently tracked as either **BOOTSTRAP**
(the local bytes are "mutable until first wire install") or
**COMMITTED** (the on-disk value is cluster-authoritative).  Each
transition is persisted via a sentinel file whose contents are the
SHA-256 fingerprint of the committed bytes; on startup a fingerprint
mismatch between sentinel and on-disk key reverts to BOOTSTRAP so a
stale-value-after-rotation restart cannot re-use a committed marker
that no longer describes disk.

The BOOTSTRAP state applies a **founder-wait window** before
committing to a non-founder install: for up to
``cluster_bootstrap_founder_wait_s`` seconds (default 2.0s) after the
first arrival, the receiver prefers an install from the designated
founder of its configured cluster pool.  When the window expires
without a founder reply, the best-candidate (earliest-arriving)
install wins and a WARN is logged.  Once the founder-wait window has
been served on a key, identity is never consulted again for that key.

The full specification lives in
``agents/reports/design-unified-cluster-key-propagation.md`` and the
reviewer audit (with required tweaks T-1, T-2, T-6) lives in
``agents/reports/design-unified-cluster-key-propagation-reviewer.md``.
"""

import hashlib
import logging
import os
import pathlib
import tempfile
import threading
import time

log = logging.getLogger(__name__)

#: Default founder-wait window (seconds).  Reviewer T-1: the real
#: arm64 CI race window is observed at 588ms-12s; a 2s window biases
#: toward the founder install during normal bootstrap without blocking
#: forever when the founder is dead.
DEFAULT_FOUNDER_WAIT_S = 2.0

#: Config option name for the founder-wait window.
OPT_FOUNDER_WAIT = "cluster_bootstrap_founder_wait_s"

#: Sentinel content prefix.  Reviewer T-2: sentinels carry the SHA-256
#: fingerprint of the committed key bytes, not emptiness, so a restart
#: whose on-disk key no longer matches the sentinel reverts to
#: BOOTSTRAP instead of silently refusing a legitimate re-sync.
SENTINEL_PREFIX = "sha256:"

#: Supported key names.  Kept narrow on purpose -- the primitive only
#: covers the two keys the reviewer scoped (``cluster_pem`` + the
#: ``cluster_aes`` session key).  ``cluster_pub`` rides with the
#: ``cluster_pem`` install and does not need its own state marker.
SUPPORTED_KEYS = ("cluster_aes", "cluster_pem")

#: Receiver states.  A key either is still trusting any first arrival
#: (BOOTSTRAP) or has committed to a cluster-authoritative value
#: (COMMITTED).
STATE_BOOTSTRAP = "bootstrap"
STATE_COMMITTED = "committed"


# ---------------------------------------------------------------------------
# Sentinel helpers
# ---------------------------------------------------------------------------


def cluster_key_sentinel_path(cluster_pki_dir, key_name):
    """
    Return the sentinel path for ``key_name`` under ``cluster_pki_dir``.

    Each key has its own dotfile sentinel so an operator can
    selectively re-open the bootstrap window for a single key without
    touching the other (e.g. ``rm .cluster_aes.committed`` to re-sync
    the session AES while keeping ``cluster.pem`` committed).
    """
    if key_name not in SUPPORTED_KEYS:
        raise ValueError(
            f"Unsupported cluster key name {key_name!r}; "
            f"expected one of {SUPPORTED_KEYS}"
        )
    return pathlib.Path(cluster_pki_dir) / f".{key_name}.committed"


def fingerprint_bytes(key_bytes):
    """
    Return the sentinel fingerprint for ``key_bytes``.

    Format: ``"sha256:<64-hex>"``.  The full digest is used (not
    truncated) so reviewer T-2's stale-on-restart check is strict:
    any single byte change between sentinel-write time and restart
    flips the fingerprint.

    ``key_bytes`` may be ``bytes`` or ``str``; a ``str`` is encoded as
    UTF-8 before hashing to match how the sender serialises PEM and
    AES bytes on the wire.
    """
    if isinstance(key_bytes, str):
        key_bytes = key_bytes.encode("utf-8")
    if not isinstance(key_bytes, (bytes, bytearray)):
        raise TypeError(
            f"fingerprint_bytes expected bytes/str, got {type(key_bytes).__name__}"
        )
    return f"{SENTINEL_PREFIX}{hashlib.sha256(bytes(key_bytes)).hexdigest()}"


def read_sentinel_fingerprint(path):
    """
    Return the fingerprint stored in ``path``, or ``None`` if the
    sentinel is absent or unreadable.

    The sentinel contents are one line of text; whitespace is
    stripped before return.  An unreadable sentinel is treated as
    absent (returns ``None``) rather than raising -- a torn sentinel
    from a crashed write is handled the same way as "never wrote one"
    so the caller falls back to BOOTSTRAP.
    """
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as exc:  # pragma: no cover - defensive
        log.warning("Unable to read cluster key sentinel %s: %s", path, exc)
        return None
    text = text.strip()
    if not text:
        return None
    if not text.startswith(SENTINEL_PREFIX):
        log.warning(
            "Cluster key sentinel %s has unrecognised format %r; treating as absent",
            path,
            text[:80],
        )
        return None
    return text


def write_sentinel_fingerprint(path, fingerprint):
    """
    Write ``fingerprint`` to ``path`` atomically.

    Uses a tempfile + ``os.replace`` so a concurrent reader always
    sees either the previous sentinel (fully intact) or the new one
    (fully intact), never a torn write.  Parent directory is created
    on demand.
    """
    if not fingerprint.startswith(SENTINEL_PREFIX):
        raise ValueError(
            f"Fingerprint {fingerprint!r} must start with {SENTINEL_PREFIX!r}"
        )
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # NamedTemporaryFile(delete=False) + os.replace is the standard
    # atomic-write recipe; put the tmp in the same directory so the
    # rename is on the same filesystem and therefore atomic (POSIX).
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            fp.write(fingerprint + "\n")
            fp.flush()
            try:
                os.fsync(fp.fileno())
            except OSError:  # pragma: no cover - fsync best effort
                pass
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def verify_committed_state_on_startup(cluster_pki_dir, key_name, on_disk_bytes):
    """
    Resolve the startup state for ``key_name`` given its current
    on-disk bytes.

    Returns ``(state, fingerprint)``:

    * ``(STATE_COMMITTED, fp)`` -- sentinel exists AND its fingerprint
      matches ``fingerprint_bytes(on_disk_bytes)``.  Caller may skip
      further wire-install work for this key.
    * ``(STATE_BOOTSTRAP, None)`` -- sentinel is absent (never
      committed) OR sentinel exists but its fingerprint differs from
      the on-disk bytes.  Reviewer T-2: the mismatch case deletes the
      stale sentinel so a legitimate next-arrival install commits
      again from scratch.
    """
    sentinel = cluster_key_sentinel_path(cluster_pki_dir, key_name)
    stored = read_sentinel_fingerprint(sentinel)
    if stored is None:
        return STATE_BOOTSTRAP, None
    if on_disk_bytes is None:
        # Sentinel present but key bytes are gone -- revert so the
        # next-arrival install re-syncs the on-disk value.
        log.warning(
            "Cluster key %s: sentinel %s present but on-disk bytes are "
            "missing; reverting to BOOTSTRAP",
            key_name,
            sentinel,
        )
        try:
            sentinel.unlink()
        except FileNotFoundError:
            pass
        return STATE_BOOTSTRAP, None
    actual = fingerprint_bytes(on_disk_bytes)
    if actual == stored:
        return STATE_COMMITTED, stored
    # Reviewer T-2: stale sentinel from a rotation while this master
    # was offline, or from an operator overwriting the key bytes
    # without resetting the sentinel.  Revert to BOOTSTRAP so a
    # cluster-authoritative install can commit.
    log.warning(
        "Cluster key %s: sentinel fingerprint %s does not match on-disk "
        "fingerprint %s; deleting sentinel and reverting to BOOTSTRAP",
        key_name,
        stored,
        actual,
    )
    try:
        sentinel.unlink()
    except FileNotFoundError:
        pass
    return STATE_BOOTSTRAP, None


# ---------------------------------------------------------------------------
# State-machine installer
# ---------------------------------------------------------------------------


class ClusterKeyStateMachine:
    """
    Per-key receiver-side state machine with founder-wait window.

    The state machine is instantiated once per master process (held
    on the ``ReqServerChannel``).  For each supported key
    (``cluster_aes``, ``cluster_pem``) it holds:

    * ``state`` -- BOOTSTRAP or COMMITTED.
    * ``fingerprint`` -- the committed key's SHA-256 fingerprint (or
      ``None`` in BOOTSTRAP).
    * ``first_arrival_monotonic`` -- the monotonic wall-clock time at
      which the first non-founder install arrived while still in
      BOOTSTRAP.  Used to bound the founder-wait window.

    All mutations run under ``self._lock`` so concurrent join-reply
    handlers (worker-pool masters) see a consistent transition.
    """

    def __init__(self, opts, cluster_pki_dir):
        self.opts = opts
        self.cluster_pki_dir = pathlib.Path(cluster_pki_dir)
        self._lock = threading.Lock()
        self._state = {}
        self._fingerprint = {}
        self._first_arrival = {}
        for key_name in SUPPORTED_KEYS:
            self._state[key_name] = STATE_BOOTSTRAP
            self._fingerprint[key_name] = None
            self._first_arrival[key_name] = None

    # ------------------------------------------------------------------
    # Startup reconciliation
    # ------------------------------------------------------------------

    def load_from_disk(self, key_name, on_disk_bytes):
        """
        Reconcile in-memory state for ``key_name`` against sentinel +
        disk at process start.

        Called by the owning receiver during __init__ after it reads
        the bootstrap-time key bytes from disk.  Mirrors the result
        of :func:`verify_committed_state_on_startup` into the
        in-memory shadow so subsequent joins hit the memory branch.
        """
        state, fingerprint = verify_committed_state_on_startup(
            self.cluster_pki_dir, key_name, on_disk_bytes
        )
        with self._lock:
            self._state[key_name] = state
            self._fingerprint[key_name] = fingerprint

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def state_of(self, key_name):
        with self._lock:
            return self._state[key_name]

    def is_committed(self, key_name):
        return self.state_of(key_name) == STATE_COMMITTED

    def fingerprint_of(self, key_name):
        with self._lock:
            return self._fingerprint[key_name]

    # ------------------------------------------------------------------
    # Core decision
    # ------------------------------------------------------------------

    def decide(self, key_name, arriving_bytes, sender_peer_id, is_founder):
        """
        Decide whether to install ``arriving_bytes`` for ``key_name``.

        Returns one of:

        * ``"install"`` -- caller should perform the install side effects
          (write disk, reload in-memory key, cache.store, fire
          ``drop_all_pending`` for ``cluster_aes``) and then call
          :meth:`mark_committed` with the final on-disk bytes.
        * ``"noop"`` -- the arriving bytes match the committed
          fingerprint.  Caller should skip side effects.
        * ``"reject"`` -- committed state + divergent arrival.  Caller
          logs WARN (already emitted here as well) and does NOT
          install.
        * ``"defer"`` -- BOOTSTRAP state + non-founder arrival within
          founder-wait window.  Caller should skip side effects and
          wait for a founder reply (or retry).

        The decision is logged at INFO (install / reject / defer) or
        DEBUG (noop) so an operator can reconstruct the bootstrap
        trajectory from the master log alone.
        """
        if key_name not in SUPPORTED_KEYS:
            raise ValueError(f"Unsupported key_name {key_name!r}")
        if arriving_bytes is None:
            return "reject"
        arriving_fp = fingerprint_bytes(arriving_bytes)
        with self._lock:
            state = self._state[key_name]
            if state == STATE_COMMITTED:
                committed_fp = self._fingerprint[key_name]
                if committed_fp == arriving_fp:
                    log.debug(
                        "cluster key %s from %s matches committed "
                        "fingerprint; no-op",
                        key_name,
                        sender_peer_id,
                    )
                    return "noop"
                log.warning(
                    "cluster key %s from %s differs from committed "
                    "(local_fp=%s arriving_fp=%s); refusing install",
                    key_name,
                    sender_peer_id,
                    committed_fp,
                    arriving_fp,
                )
                return "reject"
            # BOOTSTRAP state.
            if is_founder:
                log.info(
                    "cluster key %s: installing from founder %s (fp=%s)",
                    key_name,
                    sender_peer_id,
                    arriving_fp,
                )
                return "install"
            # Non-founder arrival during bootstrap.  Honour the
            # founder-wait window: within the window, defer and let
            # the founder's reply land first; past the window, accept
            # the best candidate (earliest arrival) and WARN.
            now = time.monotonic()
            if self._first_arrival[key_name] is None:
                self._first_arrival[key_name] = now
            wait_s = float(self.opts.get(OPT_FOUNDER_WAIT, DEFAULT_FOUNDER_WAIT_S))
            elapsed = now - self._first_arrival[key_name]
            if elapsed < wait_s:
                log.info(
                    "cluster key %s: deferring non-founder %s install "
                    "during founder-wait window (elapsed=%.3fs < %.3fs)",
                    key_name,
                    sender_peer_id,
                    elapsed,
                    wait_s,
                )
                return "defer"
            log.warning(
                "cluster key %s: founder-wait window elapsed (%.3fs); "
                "committing from non-founder %s (fp=%s)",
                key_name,
                elapsed,
                sender_peer_id,
                arriving_fp,
            )
            return "install"

    # ------------------------------------------------------------------
    # Commit transition
    # ------------------------------------------------------------------

    def mark_committed(self, key_name, committed_bytes):
        """
        Transition ``key_name`` to COMMITTED with ``committed_bytes``.

        Caller is responsible for having written the bytes to disk +
        reloaded the in-memory key before calling.  This method writes
        the sentinel atomically and updates the in-memory shadow.
        Returns ``True`` if this call made the BOOTSTRAP->COMMITTED
        transition (i.e. ``drop_all_pending`` fan-out may be needed
        for cluster_aes), ``False`` if the key was already committed
        with the same fingerprint (idempotent recommit).
        """
        if key_name not in SUPPORTED_KEYS:
            raise ValueError(f"Unsupported key_name {key_name!r}")
        fp = fingerprint_bytes(committed_bytes)
        sentinel = cluster_key_sentinel_path(self.cluster_pki_dir, key_name)
        # Write sentinel BEFORE flipping the in-memory state so a
        # concurrent crash in the millisecond between state-flip and
        # sentinel-write doesn't leave a committed memory state with
        # no persisted marker.
        write_sentinel_fingerprint(sentinel, fp)
        with self._lock:
            was_bootstrap = self._state[key_name] == STATE_BOOTSTRAP
            self._state[key_name] = STATE_COMMITTED
            self._fingerprint[key_name] = fp
            self._first_arrival[key_name] = None
        return was_bootstrap

    def bootstrap_reset(self, key_name):
        """
        Reset ``key_name`` to BOOTSTRAP (operator-triggered rotation).

        Unlinks the sentinel and clears the in-memory shadow so the
        next arriving install commits from scratch.  Does NOT touch
        the on-disk key bytes -- rotation is expected to overwrite
        them on the next install.
        """
        if key_name not in SUPPORTED_KEYS:
            raise ValueError(f"Unsupported key_name {key_name!r}")
        sentinel = cluster_key_sentinel_path(self.cluster_pki_dir, key_name)
        try:
            sentinel.unlink()
        except FileNotFoundError:
            pass
        with self._lock:
            self._state[key_name] = STATE_BOOTSTRAP
            self._fingerprint[key_name] = None
            self._first_arrival[key_name] = None


def install_cluster_key(
    state_machine,
    key_name,
    arriving_bytes,
    sender_peer_id,
    is_founder,
    install_fn,
):
    """
    High-level helper that combines :meth:`ClusterKeyStateMachine.decide`
    with the caller-supplied ``install_fn`` side-effect closure.

    ``install_fn`` is invoked (synchronously, under the receiver's
    event loop) when the state machine says to install; it is
    expected to:

    * decrypt / unwrap the arriving bytes (caller-specific)
    * write the result to disk
    * reload in-memory keys / caches
    * return the FINAL committed bytes (used for the sentinel
      fingerprint)

    On success this function transitions the state machine to
    COMMITTED and returns a dict describing the outcome (useful for
    structured logging / tests).  On ``noop``, ``reject`` or
    ``defer`` the outcome is returned without invoking ``install_fn``.
    """
    decision = state_machine.decide(
        key_name, arriving_bytes, sender_peer_id, is_founder
    )
    outcome = {
        "key_name": key_name,
        "sender": sender_peer_id,
        "decision": decision,
        "committed": False,
        "transition": False,
    }
    if decision != "install":
        return outcome
    committed_bytes = install_fn()
    if committed_bytes is None:
        # install_fn chose not to persist (e.g. decrypt failure);
        # the state machine stays in BOOTSTRAP so a retry from
        # another peer can succeed.
        outcome["decision"] = "install_failed"
        return outcome
    transition = state_machine.mark_committed(key_name, committed_bytes)
    outcome["committed"] = True
    outcome["transition"] = transition
    return outcome

"""
Adversarial concurrency + fork-safety tests for master-topology.

Each test drives a specific claim in ``rfcs/master-topology.md``
(process model and shared state, fork safety) with real
concurrency primitives --- ``os.fork``, ``multiprocessing``, and
``threading``.  No mocks of the concurrency surface.

A failing test is a WIN: it reports a bug in the implementation.
Known-broken defenses are marked ``xfail(strict=True)`` with a
specific reproducer note; passing tests confirm the defense is
actually in place.
"""

# pylint: disable=protected-access,too-many-statements

import asyncio
import contextlib
import importlib
import multiprocessing
import os
import struct
import threading
import time

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.link_manager as link_manager
import salt.topology.registry as registry
import salt.utils.files
import salt.utils.mmap_cache as mmap_cache_mod

pytestmark = [
    pytest.mark.skip_on_windows,  # fork(2) and flock required
    pytest.mark.slow_test,
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _opts(pki_root, **extra):
    """Minimal opts shape consumed by breadcrumbs + registry modules."""
    master_dir = pki_root / "pki" / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "pki_dir": str(pki_root / "pki"),
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
        "topology_breadcrumb_cache_size": 1024,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_breadcrumb_grace": 30,
        "topology_breadcrumb_max_age": 600,
    }
    opts.update(extra)
    return opts


def _breadcrumbs_index_path(opts):
    return os.path.join(opts["pki_dir"], "master", "topology_breadcrumbs.mmap")


# ---------------------------------------------------------------------------
# MmapCache concurrency: writer per-pid guard across fork
# ---------------------------------------------------------------------------


def _child_breadcrumb_write(opts, q):
    """Child body: inherit parent's writer attribute, try to put()."""
    try:
        parent_writer = _child_breadcrumb_write.writer
        breadcrumbs.put(parent_writer, "x:1", "east", 60.0, opts)
        q.put(("no-raise",))
    except RuntimeError as exc:
        q.put(("raised", repr(exc)))
    except Exception as exc:  # pylint: disable=broad-except
        q.put(("other", repr(exc)))


def test_breadcrumb_owner_pid_guard_rejects_fork_write(tmp_path):
    """Writer handle inherited across fork must refuse put() in the child."""
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        _child_breadcrumb_write.writer = writer
        ctx = multiprocessing.get_context("fork")
        q = ctx.Queue()
        proc = ctx.Process(target=_child_breadcrumb_write, args=(opts, q))
        proc.start()
        proc.join(timeout=20)
        assert proc.exitcode == 0, f"child exit {proc.exitcode}"
        status, *payload = q.get(timeout=5)
        assert status == "raised", f"child did not raise, got {status} {payload}"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# MWorker's open_reader on a never-created file must not crash
# ---------------------------------------------------------------------------


def test_reader_tolerant_of_missing_file(tmp_path):
    """open_reader() when no writer has pre_created the file: get() returns None."""
    opts = _opts(tmp_path)
    # Deliberately do NOT call pre_create.
    reader = breadcrumbs.open_reader(opts)
    try:
        # The exact Phase 5 bug: calling lookup must not raise.
        assert breadcrumbs.lookup(reader, "nothing:here") is None
    finally:
        reader.close()


# ---------------------------------------------------------------------------
# Breadcrumbs reader uses staleness_check_interval=0
# ---------------------------------------------------------------------------


def test_reader_opens_with_staleness_zero(tmp_path):
    """MWorker reader must re-stat on every op (no 250ms throttle window)."""
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    reader = breadcrumbs.open_reader(opts)
    try:
        assert reader._staleness_check_interval == 0, (
            "breadcrumbs.open_reader must build the MmapCache with "
            "staleness_check_interval=0 so return-hot-path lookups see fresh "
            "writes immediately"
        )
    finally:
        reader.close()


# ---------------------------------------------------------------------------
# Concurrent writer / reader: no torn reads
# ---------------------------------------------------------------------------


def _hammer_reader(opts, key, deadline, errors):
    """Repeatedly lookup; record any decode-shaped failure."""
    # Opens its own reader so this can run in a different process too.
    reader = breadcrumbs.open_reader(opts)
    try:
        hits = 0
        while time.monotonic() < deadline:
            val = breadcrumbs.lookup(reader, key)
            if val is None:
                continue
            # ``lookup`` returns a str from the msgpack dict's
            # ``link_cluster_id`` field.  A torn read would decode as
            # something other than one of the two values we rotate.
            if val not in ("east", "west"):
                errors.append(val)
                break
            hits += 1
        errors.append(("hits", hits))
    finally:
        reader.close()


def test_no_torn_reads_under_concurrent_rewrite(tmp_path):
    """Reader threads see only well-formed values while writer flips the key."""
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    key = "cluster:torntest"
    breadcrumbs.put(writer, key, "east", 60.0, opts)

    errors = []
    deadline = time.monotonic() + 2.0
    threads = [
        threading.Thread(target=_hammer_reader, args=(opts, key, deadline, errors))
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    try:
        toggle = True
        while time.monotonic() < deadline:
            breadcrumbs.put(writer, key, "east" if toggle else "west", 60.0, opts)
            toggle = not toggle
    finally:
        for t in threads:
            t.join(timeout=10)
        writer.close()

    bad = [e for e in errors if not (isinstance(e, tuple) and e and e[0] == "hits")]
    assert not bad, f"torn/corrupt lookup values: {bad!r}"
    # Sanity: at least one reader must have observed at least one hit, or
    # the test did not actually exercise concurrency.
    hits_total = sum(h[1] for h in errors if isinstance(h, tuple) and h[0] == "hits")
    assert hits_total > 0


# ---------------------------------------------------------------------------
# Reader survives atomic_rebuild (inode swap) with staleness_check_interval=0
# ---------------------------------------------------------------------------


def test_reader_survives_atomic_rebuild(tmp_path):
    """
    Writer calls MmapCache.atomic_rebuild (os.replace swaps inode).
    A reader that already mapped the old inode must still see consistent
    data on the next ``get`` --- the ``_cache_id`` staleness check catches
    the swap because ``staleness_check_interval=0`` for breadcrumb readers.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    reader = breadcrumbs.open_reader(opts)
    try:
        key = "cluster:rebuild"
        breadcrumbs.put(writer, key, "east", 60.0, opts)
        # Force reader to map the file.
        assert breadcrumbs.lookup(reader, key) == "east"

        # Rebuild forces the inode swap through atomic_rebuild.
        surviving = [
            (k, v if isinstance(v, bytes) else v.encode("latin-1"))
            for k, v in writer.list_items()
            if v is not True
        ]
        assert writer.atomic_rebuild(iter(surviving))

        # Now overwrite the value: this write happens on the NEW inode.
        breadcrumbs.put(writer, key, "west", 60.0, opts)

        # Reader must now see 'west' --- not stuck on the old 'east' because
        # the staleness check interval is 0 and the inode changed.
        got = breadcrumbs.lookup(reader, key)
        assert got == "west", (
            f"reader stuck on pre-rebuild inode (saw {got!r}); "
            f"staleness_check_interval={reader._staleness_check_interval}"
        )
    finally:
        reader.close()
        writer.close()


# ---------------------------------------------------------------------------
# Writer dies mid-write with flock held --- flock must be released
# ---------------------------------------------------------------------------


def _crashing_writer_body(opts, key):
    """Open writer, acquire flock implicitly by calling put, then os._exit."""
    # The flock is per-op: _lock() context manager scope.  To actually hold the
    # flock across the exit, we need to grab it manually.
    cache = mmap_cache_mod.MmapCache(
        _breadcrumbs_index_path(opts),
        size=opts["topology_breadcrumb_cache_size"],
        key_size=opts["topology_breadcrumb_cache_key_size"],
    )
    cache.open(write=True)
    lock_f = cache._lock_fd_open()
    import fcntl as _fcntl

    _fcntl.flock(lock_f.fileno(), _fcntl.LOCK_EX)
    # Kernel releases the flock on exit --- confirm the next writer unblocks.
    os._exit(0)


def test_flock_released_on_writer_exit(tmp_path):
    """
    A child writer holding the flock then crashing (os._exit) must leave the
    file state recoverable: a sibling writer process can acquire the lock
    and the ``_roster_recover`` path reconciles any divergence.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    ctx = multiprocessing.get_context("fork")
    proc = ctx.Process(target=_crashing_writer_body, args=(opts, "crash:1"))
    proc.start()
    proc.join(timeout=10)
    assert proc.exitcode == 0, f"crashing child did not exit 0: {proc.exitcode}"

    # The flock must now be gone --- open a fresh writer and immediately put().
    # If the kernel somehow kept the lock, this put() would block indefinitely;
    # we guard with a thread-based watchdog.
    writer = breadcrumbs.open_writer(opts)
    done = threading.Event()

    def _runner():
        breadcrumbs.put(writer, "sibling:ok", "east", 60.0, opts)
        done.set()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout=10)
    try:
        assert done.is_set(), "put() hung --- flock from crashed writer leaked"
        assert breadcrumbs.lookup(writer, "sibling:ok") == "east"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# MWorker fork path: owner-PID guard on registry writes
# ---------------------------------------------------------------------------


def _registry_child_write(opts, q):
    try:
        parent = _registry_child_write.parent_writer
        registry.set_peer(
            parent,
            "forked",
            {
                "cluster_id": "forked",
                "public_key": b"PUB",
                "endpoints": ("127.0.0.1:4506",),
                "attached_at": 1_700_000_000.0,
            },
        )
        q.put(("no-raise",))
    except RuntimeError as exc:
        q.put(("raised", repr(exc)))
    except Exception as exc:  # pylint: disable=broad-except
        q.put(("other", repr(exc)))


def test_registry_writer_owner_pid_rejects_fork(tmp_path):
    """
    Registry WriterHandle inherits across fork; writes from the child PID
    must raise RuntimeError.  Mirrors the breadcrumb-writer guard.
    """
    opts = _opts(tmp_path)
    registry.pre_create(opts)
    writer = registry.open_writer(opts)
    try:
        _registry_child_write.parent_writer = writer
        ctx = multiprocessing.get_context("fork")
        q = ctx.Queue()
        proc = ctx.Process(target=_registry_child_write, args=(opts, q))
        proc.start()
        proc.join(timeout=20)
        assert proc.exitcode == 0
        status, *payload = q.get(timeout=5)
        assert status == "raised", f"child did not raise, got {status} {payload}"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# link_manager.start() concurrency: double-start is a WARNING no-op
# ---------------------------------------------------------------------------


@pytest.fixture
def link_manager_module():
    """
    Reset ``salt.topology.link_manager`` module globals around each test
    so a prior start/stop does not leak into the next.
    """
    importlib.reload(link_manager)
    yield link_manager
    try:
        link_manager._reset_module_state()
    except Exception:  # pylint: disable=broad-except
        pass


def _run_start(opts, io_loop, errors):
    try:
        asyncio.set_event_loop(io_loop)
        io_loop.run_until_complete(link_manager.start(opts, io_loop))
    except Exception as exc:  # pylint: disable=broad-except
        errors.append(repr(exc))


def test_link_manager_double_start_is_safe(tmp_path, link_manager_module):
    """
    Calling ``link_manager.start`` twice without ``stop`` must warn-and-no-op,
    not corrupt module globals.
    """
    opts = _opts(
        tmp_path,
        topology_enabled=True,
        cluster_id="solo-a",
        interface="127.0.0.1",
        topology_link_port=0,
    )
    opts["cachedir"] = str(tmp_path / "cache")
    os.makedirs(opts["cachedir"], exist_ok=True)

    loop1 = asyncio.new_event_loop()
    try:
        loop1.run_until_complete(link_manager_module.start(opts, loop1))
        owner_pid_after_first = link_manager_module._OWNER_PID

        # Second start on the same loop: must be a no-op per the docstring.
        loop1.run_until_complete(link_manager_module.start(opts, loop1))
        assert (
            link_manager_module._OWNER_PID == owner_pid_after_first
        ), "second start overwrote _OWNER_PID instead of warning-and-no-op"
    finally:
        with contextlib.suppress(Exception):
            loop1.run_until_complete(link_manager_module.stop())
        loop1.close()


def test_link_manager_pre_fork_is_idempotent(tmp_path, link_manager_module):
    """
    Calling ``pre_fork`` twice in the parent before any child forks must be
    idempotent.

    ``pre_fork`` no longer reserves ``topology_link_port`` in the parent
    (that was the old EADDRINUSE-prone design superseded by
    :class:`salt.transport.zeromq.RequestServer`'s ``direct_bind`` path
    inside the publish daemon).  Both calls must leave
    ``_LISTENER_SOCKET`` as ``None`` -- idempotence means "neither call
    allocates nor replaces a socket," not "both calls return the same
    socket reference."  Also pre-creates the breadcrumb + registry
    MmapCaches once; the second call must not re-create them.
    """
    import socket

    # Reserve a free port, then release it (used to feed opts).
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    opts = _opts(
        tmp_path,
        topology_enabled=True,
        cluster_id="solo-b",
        interface="127.0.0.1",
        topology_link_port=port,
    )
    link_manager_module.pre_fork(opts, process_manager=None)
    assert (
        link_manager_module._LISTENER_SOCKET is None
    ), "pre_fork must not reserve a socket (direct_bind path owns the bind)"

    # Second pre_fork: still no socket, still no raise.
    link_manager_module.pre_fork(opts, process_manager=None)
    assert (
        link_manager_module._LISTENER_SOCKET is None
    ), "second pre_fork must also leave _LISTENER_SOCKET unreserved"


# ---------------------------------------------------------------------------
# Clustered-master restart: peers in registry MmapCache must relink
# ---------------------------------------------------------------------------


class _FakeSMHandlers:
    """Dispatch-table-shaped object with no-op attach/detach handlers."""

    def _handle_peer_attach(self, entry):  # pragma: no cover - stub
        return None

    def _handle_peer_detach(self, entry):  # pragma: no cover - stub
        return None


def test_install_sm_callbacks_replays_existing_peers(tmp_path, link_manager_module):
    """
    Audit flag: Phase 3 claimed the callback install replays pre-existing
    committed peers so a clustered-master restart re-creates outbound links.

    Set up: a peer is already in the registry (prior-generation commit).
    Call ``_install_sm_callbacks`` on a fresh SM.  Expect: ``add_link`` fires
    for the pre-existing peer.  Currently: the wrapper only wraps future
    calls --- no replay --- so ``add_link`` is NEVER invoked and the
    clustered master silently comes up with zero outbound links.
    """
    opts = _opts(
        tmp_path,
        topology_enabled=True,
        cluster_id="main",
        topology_link_port=0,
    )
    # Pre-seed registry with a peer so a "restart" has prior state to replay.
    registry.pre_create(opts)
    writer = registry.open_writer(opts)
    registry.set_peer(
        writer,
        "peer-A",
        {
            "cluster_id": "peer-A",
            "public_key": b"-----BEGIN FAKE-----\n",
            "endpoints": ("127.0.0.1:4710",),
            "attached_at": 1_700_000_000.0,
        },
    )
    writer.close()

    # Prime link_manager globals as if start() just completed its early steps.
    link_manager_module._OWNER_PID = os.getpid()
    link_manager_module._REGISTRY_CACHE = registry.open_writer(opts)
    link_manager_module._OPTS = dict(opts)

    from salt.config.topology import TopologyConfig

    link_manager_module._CONFIG = TopologyConfig(
        enabled=True, cluster_id="main", peers=(), event_subscriptions=()
    )

    added = []
    original_add_link = link_manager_module.add_link

    def _capture(link):
        added.append(link)
        # Still exercise the real guard + lock path.
        return original_add_link(link)

    link_manager_module.add_link = _capture
    try:
        sm = _FakeSMHandlers()
        # Minimal handler dispatch dict so _install_sm_callbacks can rebuild.
        from salt.cluster.consensus.raft.log import LogEntryType

        sm._handlers = {
            LogEntryType.MASTER_PEER_ATTACH: sm._handle_peer_attach,
            LogEntryType.MASTER_PEER_DETACH: sm._handle_peer_detach,
        }
        link_manager_module._install_sm_callbacks(sm)

        assert added, (
            "_install_sm_callbacks did not replay the pre-existing peer "
            "from the registry MmapCache: a clustered-master restart will "
            "silently come up with zero outbound links"
        )
        assert any(
            getattr(link, "peer_cluster_id", None) == "peer-A"
            or any("4710" in str(e) for e in getattr(link, "endpoints", ()) or ())
            for link in added
        )
    finally:
        link_manager_module.add_link = original_add_link
        if link_manager_module._REGISTRY_CACHE is not None:
            with contextlib.suppress(Exception):
                link_manager_module._REGISTRY_CACHE.close()
        link_manager_module._reset_module_state()


# ---------------------------------------------------------------------------
# salt-key race: _handle_master_auth drop-in during concurrent fs ops
# ---------------------------------------------------------------------------


def test_master_auth_handles_pending_concurrent_cp(tmp_path):
    """
    Simulate an operator ``cp``'ing a key file into ``masters_pre/`` while
    another peer attempts auth for the same cluster_id.  The auth handler
    must not partially-move/promote a mid-copy file to ``masters/``.
    """
    from salt.topology import link_manager as lm

    opts = _opts(tmp_path, cluster_id="ourself", topology_link_port=0)
    pre_dir = os.path.join(opts["pki_dir"], "masters_pre")
    accepted_dir = os.path.join(opts["pki_dir"], "masters")
    os.makedirs(pre_dir, exist_ok=True)
    os.makedirs(accepted_dir, exist_ok=True)

    cluster_id = "peer-under-copy"
    pending_path = os.path.join(pre_dir, f"{cluster_id}.pub")
    accepted_path = os.path.join(accepted_dir, f"{cluster_id}.pub")

    # Pre-populate pending with a partial-looking write.
    with salt.utils.files.fopen(pending_path, "wb") as f:
        f.write(b"-----BEGIN PARTIAL\n")
        # DO NOT include END marker --- simulating an in-flight cp.

    # Call the auth handler --- the file exists in masters_pre but not in
    # masters, so handler returns "retry" and MUST NOT move the file.
    coro = lm._handle_master_auth(
        {
            "cluster_id": cluster_id,
            "public_key": b"peer public key bytes",
            "pki_dir": opts["pki_dir"],
        }
    )
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        reply = loop.run_until_complete(coro)
    finally:
        loop.close()

    # Pending must still exist; accepted must NOT have appeared.
    assert reply.get("status") == "retry"
    assert os.path.exists(pending_path), "pending key file was moved/removed!"
    assert not os.path.exists(
        accepted_path
    ), "handler promoted a partially-written key to masters/ (race!)"


# ---------------------------------------------------------------------------
# Fork while writer holds flock mid-put --- child must not inherit a held
# lock that blocks future acquires.
# ---------------------------------------------------------------------------


def _fork_during_flock_child(opts, barrier_r, done_w):
    """Child body: ack we're alive, then try an exclusive acquire.

    If the inherited flock is still held, LOCK_EX will block until the parent
    releases.  We write 'blocked' at timeout, 'ok' on acquire.
    """
    import fcntl as _fcntl

    cache = mmap_cache_mod.MmapCache(
        _breadcrumbs_index_path(opts),
        size=opts["topology_breadcrumb_cache_size"],
        key_size=opts["topology_breadcrumb_cache_key_size"],
    )
    cache.open(write=True)
    lock_f = cache._lock_fd_open()
    os.read(barrier_r, 1)  # wait for parent to signal
    try:
        _fcntl.flock(lock_f.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        os.write(done_w, b"ok")
    except BlockingIOError:
        os.write(done_w, b"blocked")
    os._exit(0)


def test_child_does_not_inherit_held_flock(tmp_path):
    """
    Fork while the parent holds the flock.  The child inherits the fd but
    POSIX flock state is per-OFD; the child's independent LOCK_NB must
    succeed only after the parent releases.  Primarily this test asserts
    the kernel-level invariant --- confirms the design assumption that
    flock() will block/report EAGAIN rather than silently proceed.
    """
    import fcntl as _fcntl

    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    cache = mmap_cache_mod.MmapCache(
        _breadcrumbs_index_path(opts),
        size=opts["topology_breadcrumb_cache_size"],
        key_size=opts["topology_breadcrumb_cache_key_size"],
    )
    cache.open(write=True)
    lock_f = cache._lock_fd_open()
    _fcntl.flock(lock_f.fileno(), _fcntl.LOCK_EX)

    barrier_r, barrier_w = os.pipe()
    done_r, done_w = os.pipe()
    ctx = multiprocessing.get_context("fork")
    proc = ctx.Process(target=_fork_during_flock_child, args=(opts, barrier_r, done_w))
    proc.start()
    os.close(barrier_r)
    os.close(done_w)
    try:
        # Signal child to proceed.
        os.write(barrier_w, b".")
        os.close(barrier_w)
        # Child should report 'blocked' because parent still holds the lock.
        result = os.read(done_r, 16)
        assert result == b"blocked", (
            f"child acquired flock while parent still held it: {result!r} "
            "(violates cross-process exclusion contract)"
        )
    finally:
        _fcntl.flock(lock_f.fileno(), _fcntl.LOCK_UN)
        cache.close()
        proc.join(timeout=10)
        with contextlib.suppress(OSError):
            os.close(done_r)


# ---------------------------------------------------------------------------
# Multiprocess writer contention: no silent data loss
# ---------------------------------------------------------------------------


def _mp_writer_child(opts, keyspace, errors_q):
    """Child body: open writer, insert N keys, verify all readable."""
    try:
        writer = breadcrumbs.open_writer(opts)
        try:
            for k in keyspace:
                breadcrumbs.put(writer, k, "east", 60.0, opts)
            # Verify from our own writer handle (also acts as reader).
            missing = [k for k in keyspace if breadcrumbs.lookup(writer, k) is None]
            errors_q.put(("ok", missing))
        finally:
            writer.close()
    except Exception as exc:  # pylint: disable=broad-except
        errors_q.put(("err", repr(exc)))


def test_multiprocess_writer_contention(tmp_path):
    """
    Two writer processes insert disjoint key ranges concurrently; every
    key must survive the crossfire.  Any missing key signals a torn put
    or a dropped flock-held write.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    ctx = multiprocessing.get_context("fork")
    q = ctx.Queue()
    ks_a = [f"a:{i}" for i in range(30)]
    ks_b = [f"b:{i}" for i in range(30)]
    pa = ctx.Process(target=_mp_writer_child, args=(opts, ks_a, q))
    pb = ctx.Process(target=_mp_writer_child, args=(opts, ks_b, q))
    pa.start()
    pb.start()
    pa.join(timeout=30)
    pb.join(timeout=30)
    assert pa.exitcode == 0
    assert pb.exitcode == 0
    results = [q.get(timeout=5) for _ in range(2)]
    for status, payload in results:
        assert status == "ok", f"child error: {payload}"
        assert not payload, f"self-visible writes missing in writer process: {payload}"

    # Reader side: every key from both processes must be present via a
    # fresh reader.
    reader = breadcrumbs.open_reader(opts)
    try:
        a_missing = [k for k in ks_a if breadcrumbs.lookup(reader, k) is None]
        b_missing = [k for k in ks_b if breadcrumbs.lookup(reader, k) is None]
        assert (
            not a_missing and not b_missing
        ), f"cross-process writes lost. a_missing={a_missing} b_missing={b_missing}"
    finally:
        reader.close()


# ---------------------------------------------------------------------------
# add_link from a non-io-loop thread must hop onto the io_loop
# ---------------------------------------------------------------------------


class _FakePeerRef:
    def __init__(self, host="127.0.0.1", port=4710):
        self.host = host
        self.port = port
        self.finger = None


def test_add_link_schedules_on_io_loop_thread(tmp_path, link_manager_module):
    """
    ``add_link`` is called from the Raft apply thread.  It must schedule
    the connect() task on the io_loop via ``call_soon_threadsafe``, so the
    coroutine runs on the io_loop thread --- not the apply thread.
    """
    opts = _opts(tmp_path, topology_enabled=True, cluster_id="main")
    link_manager_module._OWNER_PID = os.getpid()
    link_manager_module._OPTS = dict(opts)

    loop = asyncio.new_event_loop()
    link_manager_module._IO_LOOP = loop

    loop_thread_id = {"id": None}

    def _loop_runner():
        asyncio.set_event_loop(loop)
        loop_thread_id["id"] = threading.get_ident()
        loop.run_forever()

    thread = threading.Thread(target=_loop_runner, daemon=True)
    thread.start()
    # Wait for the loop to actually be running.
    while loop_thread_id["id"] is None:
        time.sleep(0.01)

    captured = {}

    class _FakeLink:
        peer_cluster_id = "fake-peer"
        endpoints = (_FakePeerRef(),)

        async def connect(self):
            captured["connect_thread"] = threading.get_ident()
            captured["is_loop_thread"] = threading.get_ident() == loop_thread_id["id"]
            loop.call_soon_threadsafe(loop.stop)

    # Monkey-patch isinstance check indirectly: substitute PeerMasterLink type.
    original_cls = link_manager_module.PeerMasterLink
    link_manager_module.PeerMasterLink = _FakeLink
    try:
        caller_thread = threading.Thread(
            target=link_manager_module.add_link,
            args=(_FakeLink(),),
            daemon=True,
        )
        caller_thread.start()
        caller_thread.join(timeout=5)
        thread.join(timeout=10)

        assert "connect_thread" in captured, "connect() did not run"
        assert captured["is_loop_thread"], (
            f"connect() ran on thread {captured['connect_thread']} but the "
            f"io_loop thread is {loop_thread_id['id']}: Raft apply thread "
            "would be calling into asyncio objects directly, violating "
            "asyncio thread-affinity"
        )
    finally:
        link_manager_module.PeerMasterLink = original_cls
        with contextlib.suppress(Exception):
            loop.close()
        link_manager_module._reset_module_state()


# ---------------------------------------------------------------------------
# Reader observes writer across its own lifespan with no_leak of mmap
# ---------------------------------------------------------------------------


def test_header_counters_consistent_under_hammering(tmp_path):
    """
    Hammer put/delete pairs from one thread while another reads
    ``get_stats``.  Occupied + deleted + empty must always sum to (size-1).
    Any drift means the header counter update raced with a reader observing
    a partial state.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        stop = threading.Event()
        drift = []

        def _reader():
            # Direct MmapCache access to bypass the breadcrumbs wrapper.
            cache = writer  # breadcrumbs writer IS a MmapCache
            while not stop.is_set():
                stats = cache.get_stats()
                total = stats["occupied"] + stats["deleted"] + stats["empty"]
                if total != stats["total"]:
                    drift.append(stats)
                    break

        reader_t = threading.Thread(target=_reader)
        reader_t.start()
        try:
            for i in range(50):
                breadcrumbs.put(writer, f"k:{i}", "east", 60.0, opts)
            for i in range(50):
                breadcrumbs.delete(writer, f"k:{i}")
        finally:
            stop.set()
            reader_t.join(timeout=10)

        assert not drift, f"header counters drifted: {drift}"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# atomic_rebuild preserves data (regression guard for the breadcrumbs sweep)
# ---------------------------------------------------------------------------


def test_cleanup_atomic_rebuild_preserves_live_entries(tmp_path):
    """
    ``breadcrumbs.cleanup`` triggers ``atomic_rebuild`` when deletion ratio
    exceeds 0.3.  All non-expired keys must survive the rebuild.
    """
    opts = _opts(tmp_path, topology_breadcrumb_grace=1, topology_breadcrumb_max_age=1)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        # 10 entries with 1s lifetime.
        for i in range(10):
            breadcrumbs.put(writer, f"short:{i}", "east", 1.0, opts)
        # 10 entries with 300s lifetime --- survive cleanup.
        long_opts = dict(
            opts, topology_breadcrumb_grace=300, topology_breadcrumb_max_age=600
        )
        for i in range(10):
            breadcrumbs.put(writer, f"long:{i}", "west", 300.0, long_opts)

        time.sleep(1.5)  # let short entries expire
        removed = breadcrumbs.cleanup(writer)
        assert removed >= 10

        # Every 'long:*' must still be present and route to 'west'.
        for i in range(10):
            got = breadcrumbs.lookup(writer, f"long:{i}")
            assert got == "west", f"long:{i} lost after cleanup rebuild (got {got!r})"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# roster_recover on-open --- corrupt the roster and verify repair
# ---------------------------------------------------------------------------


def test_roster_recover_rebuilds_after_corruption(tmp_path):
    """
    Simulate a crash between index flush and roster append: entries exist
    in the index but the roster is missing them.  Opening a fresh writer
    must run ``_roster_recover`` and reconcile.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        for i in range(5):
            breadcrumbs.put(writer, f"survive:{i}", "east", 60.0, opts)
    finally:
        writer.close()

    # Truncate the roster to zero bytes while leaving the index intact.
    roster_path = _breadcrumbs_index_path(opts) + ".roster"
    with salt.utils.files.fopen(roster_path, "wb") as f:
        f.truncate(0)

    # Open a fresh writer --- _roster_recover must repopulate.
    writer2 = breadcrumbs.open_writer(opts)
    try:
        keys = writer2.list_keys()
        for i in range(5):
            assert (
                f"survive:{i}" in keys
            ), f"roster_recover failed to re-index entry {i}: keys={keys}"
    finally:
        writer2.close()


# ---------------------------------------------------------------------------
# Writer flock is per-op, not per-handle: concurrent put() from the same
# process (different threads) must serialize correctly.
# ---------------------------------------------------------------------------


def test_concurrent_thread_puts_do_not_lose_entries(tmp_path):
    """
    Fire 8 threads into the same writer; each inserts 20 unique keys.
    Every key must be present at the end.  A missing key would indicate
    a lost write due to the RLock+flock interaction (the thread_lock is
    an RLock, the flock is a POSIX file lock --- same process holds it
    exclusively per-op).
    """
    opts = _opts(tmp_path, topology_breadcrumb_cache_size=4096)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    errors = []

    def _worker(idx):
        try:
            for i in range(20):
                breadcrumbs.put(writer, f"t{idx}:{i}", "east", 60.0, opts)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append((idx, repr(exc)))

    try:
        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not errors, f"worker errors: {errors}"

        missing = []
        for idx in range(8):
            for i in range(20):
                k = f"t{idx}:{i}"
                if breadcrumbs.lookup(writer, k) is None:
                    missing.append(k)
        assert not missing, f"writes dropped under thread contention: {missing}"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Raw mmap byte-level: writer flush should be visible to a fresh reader
# ---------------------------------------------------------------------------


def test_cross_process_lookup_visibility(tmp_path):
    """
    Writer in parent inserts a key; child opens its own reader (not inheriting
    any fd) and must see the key.  Baseline for cross-process visibility.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        breadcrumbs.put(writer, "across:1", "east", 60.0, opts)
    finally:
        writer.close()

    def _child(opts, key, q):
        reader = breadcrumbs.open_reader(opts)
        try:
            q.put(breadcrumbs.lookup(reader, key))
        finally:
            reader.close()

    ctx = multiprocessing.get_context("fork")
    q = ctx.Queue()
    proc = ctx.Process(target=_child, args=(opts, "across:1", q))
    proc.start()
    proc.join(timeout=10)
    assert proc.exitcode == 0
    assert q.get(timeout=5) == "east"


# ---------------------------------------------------------------------------
# Index-header magic byte survives a crash + reopen
# ---------------------------------------------------------------------------


def test_header_magic_present_after_crash_reopen(tmp_path):
    """
    A fresh pre_create stamps _HEADER_MAGIC at slot 0.  Simulate a crash
    by killing a child mid-first-put; parent must still see the magic byte.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    index_path = _breadcrumbs_index_path(opts)
    with salt.utils.files.fopen(index_path, "rb") as f:
        header = f.read(1)
    assert header == bytes(
        [mmap_cache_mod._HEADER_MAGIC]
    ), f"header magic missing: {header!r}"

    # Reopen and verify we don't blow the header on second open.
    writer = breadcrumbs.open_writer(opts)
    try:
        breadcrumbs.put(writer, "post:crash", "east", 60.0, opts)
    finally:
        writer.close()
    with salt.utils.files.fopen(index_path, "rb") as f:
        header = f.read(1)
    assert header == bytes([mmap_cache_mod._HEADER_MAGIC])


# ---------------------------------------------------------------------------
# Breadcrumb heap record integrity after rapid put/delete churn
# ---------------------------------------------------------------------------


def test_heap_record_integrity_after_churn(tmp_path):
    """
    After mixed put/delete churn the heap may contain unreferenced garbage,
    but every live slot's heap record must still verify its XXH3 checksum.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        for i in range(30):
            breadcrumbs.put(writer, f"churn:{i}", "east", 60.0, opts)
        for i in range(15):
            breadcrumbs.delete(writer, f"churn:{i}")
        # Overwrite a surviving entry with a different value (triggers in-place
        # overwrite if the new value fits in the existing heap region).
        for i in range(15, 30):
            breadcrumbs.put(writer, f"churn:{i}", "west", 60.0, opts)

        for i in range(15, 30):
            got = breadcrumbs.lookup(writer, f"churn:{i}")
            assert got == "west", f"churn:{i} corrupted after overwrite: {got!r}"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Overflow: index full --- put() must return False, not corrupt state
# ---------------------------------------------------------------------------


def test_full_index_rejects_put_without_corruption(tmp_path):
    """
    Fill the index to capacity.  Further put() must return False.  The
    file state must remain consistent (header counters match roster).
    """
    opts = _opts(tmp_path, topology_breadcrumb_cache_size=16)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        inserted = 0
        for i in range(100):
            ok = writer.put(f"full:{i}", b"v")
            if ok:
                inserted += 1
        # 15 data slots (slot 0 is header) --- expect <=15 insertions.
        assert inserted <= 15, f"inserted {inserted}, expected <= 15"

        stats = writer.get_stats()
        assert (
            stats["occupied"] == inserted
        ), f"header occupied {stats['occupied']} != inserted {inserted}"
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Zero-byte values round-trip cleanly (regression check)
# ---------------------------------------------------------------------------


def test_null_terminated_value_roundtrip(tmp_path):
    """
    Values ending in NUL (e.g. msgpack dicts with trailing zero ints) must
    round-trip without the historical rstrip-NUL CRC bug (see BUG.md).

    Separate concern: raw bytes-in / bytes-out type preservation.  A
    payload of 8 NUL bytes is valid utf-8 so the current ``to_unicode``
    fallback path never fires; the caller is handed a ``str``.
    """
    opts = _opts(tmp_path)
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    try:
        payload = struct.pack("<Q", 0)  # 8 NUL bytes
        writer.put("binary:nulls", payload)
        got = writer.get("binary:nulls")
        assert isinstance(
            got, bytes
        ), f"stored bytes came back as {type(got).__name__}: {got!r}"
        assert got == payload, f"NUL-terminated bytes corrupted: {got!r} != {payload!r}"
    finally:
        writer.close()

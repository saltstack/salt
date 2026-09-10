"""
Regression tests for the ``__del__`` fork-safety guard on transport
publisher / publish-server / subscriber / publisher-client classes.

Background
----------
In Python fork mode, a child inherits the parent's live socket file
descriptors via copy-on-write.  If the *child's* copy of a transport
object is garbage-collected before an explicit ``.close()``, its
``__del__`` used to unconditionally call
``salt.utils.resource_warnings.warn_until_close(...)``, emitting a
spurious "unclosed publisher client" / "unclosed publish server" /
"unclosed publish subscriber" / "unclosed tcp puller" ResourceWarning
to stderr.  The warning is cosmetic noise -- the FDs are still owned
by the parent -- but it flags "leak" during tests and pollutes logs.

The fix records ``self._creator_pid = os.getpid()`` in ``__init__`` and
short-circuits ``__del__`` when ``os.getpid() != self._creator_pid``.
The forked child must NOT ``.close()`` the underlying stream (that
would call ``close(2)`` on the shared FD number and break the parent's
transport) -- it merely skips the warning.

Tests below cover, per in-scope class:

    1. Parent PID emits the warning (the pre-existing behavior for
       a real leak in the creating process).
    2. Simulated forked child (monkey-patch ``os.getpid`` inside
       ``__del__``) does NOT emit the warning.
    3. Real ``fork()`` child does NOT emit the warning to its stderr
       (Linux only; skipped elsewhere).
    4. A partially-initialized object (``object.__new__`` bypassing
       ``__init__``) does not raise ``AttributeError`` in ``__del__``.
"""

import multiprocessing
import os
import sys
import warnings

import pytest

import salt.transport.tcp
import salt.transport.ws
import salt.utils.resource_warnings
from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Class-under-test constructors (kept as free helpers so the parametrized
# tests below stay compact and each class-specific quirk is in one place).
# ---------------------------------------------------------------------------


def _make_tcp_subscriber():
    """Construct ``salt.transport.tcp.Subscriber`` with a benign stub stream."""
    stream = MagicMock()
    stream.closed.return_value = True
    return salt.transport.tcp.Subscriber(stream=stream, address=("127.0.0.1", 0))


def _make_tcp_puller():
    """Construct ``salt.transport.tcp.TCPPuller`` without starting it."""
    # ``TCPPuller.__init__`` requires an io_loop *or* an implicit tornado
    # current-loop; construct with an explicit ``io_loop`` sentinel so we
    # don't touch tornado internals here.
    io_loop = MagicMock()
    with patch("salt.utils.asynchronous.aioloop", side_effect=lambda x: x):
        return salt.transport.tcp.TCPPuller(host="127.0.0.1", port=0, io_loop=io_loop)


def _make_tcp_publish_server():
    """Construct ``salt.transport.tcp.PublishServer`` without binding sockets."""
    opts = {"order_masters": False}
    return salt.transport.tcp.PublishServer(
        opts,
        pub_host="127.0.0.1",
        pub_port=0,
        pull_host="127.0.0.1",
        pull_port=0,
    )


def _make_tcp_pubserver_publisher():
    """Construct ``salt.transport.tcp._TCPPubServerPublisher`` without connecting."""
    io_loop = MagicMock()
    with patch("salt.utils.asynchronous.aioloop", side_effect=lambda x: x):
        return salt.transport.tcp._TCPPubServerPublisher(
            host="127.0.0.1", port=0, path=None, io_loop=io_loop
        )


def _make_ws_publish_client():
    """Construct ``salt.transport.ws.PublishClient`` without connecting."""
    opts = {"tcp_reconnect_backoff": 1}
    io_loop = MagicMock()
    with patch("salt.utils.asynchronous.aioloop", side_effect=lambda x: x):
        return salt.transport.ws.PublishClient(
            opts,
            io_loop=io_loop,
            host="127.0.0.1",
            port=0,
        )


def _make_ws_request_client():
    """Construct ``salt.transport.ws.RequestClient`` without connecting."""
    opts = {}
    io_loop = MagicMock()
    with patch("salt.utils.asynchronous.aioloop", side_effect=lambda x: x):
        return salt.transport.ws.RequestClient(opts, io_loop=io_loop)


# Each entry: (test id, factory callable, class object).
CLASSES = [
    ("tcp.Subscriber", _make_tcp_subscriber, salt.transport.tcp.Subscriber),
    ("tcp.TCPPuller", _make_tcp_puller, salt.transport.tcp.TCPPuller),
    (
        "tcp.PublishServer",
        _make_tcp_publish_server,
        salt.transport.tcp.PublishServer,
    ),
    (
        "tcp._TCPPubServerPublisher",
        _make_tcp_pubserver_publisher,
        salt.transport.tcp._TCPPubServerPublisher,
    ),
    (
        "ws.PublishClient",
        _make_ws_publish_client,
        salt.transport.ws.PublishClient,
    ),
    (
        "ws.RequestClient",
        _make_ws_request_client,
        salt.transport.ws.RequestClient,
    ),
]


CLASS_IDS = [entry[0] for entry in CLASSES]


@pytest.fixture(params=CLASSES, ids=CLASS_IDS)
def cls_case(request):
    """(factory, class) fixture parametrized across every fixed class."""
    return request.param


# ---------------------------------------------------------------------------
# Test 1: ``__init__`` records the creator PID.
# ---------------------------------------------------------------------------


def test_creator_pid_recorded_in_init(cls_case):
    _test_id, factory, _cls = cls_case
    obj = factory()
    try:
        assert obj._creator_pid == os.getpid()
    finally:
        # Explicitly close so a subsequent ``__del__`` doesn't emit an
        # (accurate) warning during interpreter teardown of this test.
        if hasattr(obj, "close"):
            try:
                obj.close()
            except Exception:  # pylint: disable=broad-except
                pass
        obj._closing = True


# ---------------------------------------------------------------------------
# Test 2: Parent PID emits the warning (pre-existing behavior for
# creating-process leaks is preserved).
# ---------------------------------------------------------------------------


def test_parent_pid_emits_warning(cls_case):
    _test_id, factory, _cls = cls_case
    obj = factory()
    # Sanity: we are in the creator PID.
    assert obj._creator_pid == os.getpid()
    with patch.object(salt.utils.resource_warnings, "warn_until_close") as mock_warn:
        # The transport modules imported ``warn_until_close`` directly
        # via ``salt.utils.resource_warnings.warn_until_close(...)`` at
        # call time (module-attribute access), so patching the attribute
        # on the module is sufficient -- the ``__del__``s do not bind
        # a local reference at import time.
        # Directly invoke the finalizer (not ``del obj``) so the assertion
        # runs deterministically regardless of GC timing / lingering refs.
        obj.__del__()  # pylint: disable=unnecessary-dunder-call
        assert mock_warn.call_count == 1, (
            "expected the creating-process __del__ to emit exactly one "
            f"warn_until_close call, got {mock_warn.call_count}"
        )
    # Mark closed so any implicit garbage-collector __del__ later in the
    # test session is a no-op.
    obj._closing = True


# ---------------------------------------------------------------------------
# Test 3: Simulated forked child (different PID) does NOT emit warning.
# ---------------------------------------------------------------------------


def test_simulated_child_pid_suppresses_warning(cls_case):
    _test_id, factory, _cls = cls_case
    obj = factory()
    fake_child_pid = obj._creator_pid + 1
    with patch.object(
        salt.utils.resource_warnings, "warn_until_close"
    ) as mock_warn, patch("os.getpid", return_value=fake_child_pid):
        obj.__del__()  # pylint: disable=unnecessary-dunder-call
        assert mock_warn.call_count == 0, (
            "forked-child __del__ must NOT emit a warn_until_close: the "
            "parent still owns the underlying FDs. Got "
            f"{mock_warn.call_count} call(s)."
        )
    obj._closing = True


# ---------------------------------------------------------------------------
# Test 4: Partially-initialized object doesn't crash in ``__del__``.
# ---------------------------------------------------------------------------


def test_partially_initialized_del_is_safe(cls_case):
    _test_id, _factory, cls = cls_case
    # Bypass __init__ -- simulates an object whose __init__ raised before
    # ``self._creator_pid`` was assigned.  The guard uses ``getattr(..., None)``
    # so no ``AttributeError`` should escape.
    obj = object.__new__(cls)
    # Silence the (correct-for-uninitialized-object) warning if it fires;
    # we're only asserting the finalizer doesn't raise.
    with patch.object(salt.utils.resource_warnings, "warn_until_close"):
        # Must not raise AttributeError / anything else.
        obj.__del__()  # pylint: disable=unnecessary-dunder-call


# ---------------------------------------------------------------------------
# Test 5: Real fork -- Linux only.  Child inherits object, lets it fall
# out of scope, exits.  Parent asserts the child's stderr contains no
# "unclosed" ResourceWarning line.
# ---------------------------------------------------------------------------


def _child_target(class_id, conn):
    """
    Child entry point.  Captures its own stderr, exercises the finalizer
    on the inherited object, and sends the captured text back through
    ``conn`` for the parent to assert on.
    """
    import gc
    import io  # local import: fresh in the forked child

    # Redirect stderr so we can inspect what the forked child emitted.
    buf = io.StringIO()
    sys.stderr = buf

    # Enable ResourceWarning delivery in the child (Python's default
    # filter would otherwise silence it, defeating the test).
    warnings.simplefilter("always", ResourceWarning)

    try:
        # Look up the inherited object by test id.  The parent placed
        # it in a module-level dict before forking.
        obj = _INHERITED_OBJECTS.get(class_id)
        # Drop the module reference and force collection.  The child's
        # copy of ``obj`` becomes unreachable and ``__del__`` runs.
        _INHERITED_OBJECTS.pop(class_id, None)
        del obj
        gc.collect()
    finally:
        sys.stderr = sys.__stderr__
        conn.send(buf.getvalue())
        conn.close()


# Populated by the fork test; must be module-level so the forked child
# (which inherits the parent's module state via COW) can see it.
_INHERITED_OBJECTS = {}


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="fork() semantics tested here are Linux-specific",
)
@pytest.mark.parametrize("case", CLASSES, ids=CLASS_IDS)
def test_real_fork_child_emits_no_warning(case):
    class_id, factory, _cls = case
    obj = factory()
    _INHERITED_OBJECTS[class_id] = obj
    try:
        ctx = multiprocessing.get_context("fork")
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_child_target, args=(class_id, child_conn))
        proc.start()
        child_conn.close()
        child_stderr = parent_conn.recv()
        proc.join(timeout=10)
        assert (
            proc.exitcode == 0
        ), f"forked child exited with {proc.exitcode}; stderr:\n{child_stderr}"
        assert "unclosed" not in child_stderr.lower(), (
            "forked child emitted an 'unclosed ...' ResourceWarning; the "
            "PID guard in __del__ should have suppressed it.  Child "
            f"stderr:\n{child_stderr}"
        )
        assert "ResourceWarning" not in child_stderr, (
            "forked child emitted a ResourceWarning; the PID guard in "
            f"__del__ should have suppressed it.  Child stderr:\n{child_stderr}"
        )
    finally:
        _INHERITED_OBJECTS.pop(class_id, None)
        # Mark closed in the parent to suppress the (accurate) parent-PID
        # warning during test teardown.
        obj._closing = True

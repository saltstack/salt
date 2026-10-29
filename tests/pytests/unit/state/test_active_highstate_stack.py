"""
Tests for the per-execution-context active-HighState stack (#63056).

Concurrent state runs -- e.g. reactor orchestrations rendered in parallel
reactor worker threads -- previously shared a single class-level
``HighState.stack`` list. One run's ``push_active`` was therefore visible to
another, so ``HighState.get_active`` could return the wrong HighState in the
middle of a render (surfacing downstream as ``IndexError`` popping an empty
pydsl render stack, or ``KeyError: '__env__'`` from a spuriously detected
conflicting ID). The stack is now isolated per execution context via a
ContextVar.
"""

import threading

import salt.state
from tests.support.mock import patch


class _Marker(salt.state.HighState):
    # A cheap stand-in that skips HighState's heavy __init__ but inherits the
    # real push/pop/get/clear accessors under test.
    def __init__(self, tag):  # pylint: disable=super-init-not-called
        self.tag = tag


def test_active_stack_push_pop_get_clear():
    HighState = salt.state.HighState
    HighState.clear_active()
    assert HighState.get_active() is None

    a = _Marker("a")
    b = _Marker("b")

    a.push_active()
    assert HighState.get_active() is a
    b.push_active()
    assert HighState.get_active() is b
    b.pop_active()
    assert HighState.get_active() is a
    a.pop_active()
    assert HighState.get_active() is None

    # clear_active() resets the stack for the current context.
    a.push_active()
    HighState.clear_active()
    assert HighState.get_active() is None


def test_active_stack_isolated_across_threads():
    HighState = salt.state.HighState
    HighState.clear_active()

    results = {}
    # Two barriers make the failure deterministic on a *shared* stack: every
    # thread pushes before any reads (so the shared top holds both markers),
    # and every thread reads before any pops (so a fast pop can't restore the
    # reader's own marker by luck). With a shared stack both threads then read
    # whichever marker was pushed last -- two identical tags, never {A, B}.
    both_pushed = threading.Barrier(2)
    both_read = threading.Barrier(2)

    def worker(tag):
        marker = _Marker(tag)
        marker.push_active()
        both_pushed.wait(timeout=10)
        try:
            active = HighState.get_active()
            results[tag] = None if active is None else active.tag
            both_read.wait(timeout=10)
        finally:
            marker.pop_active()

    threads = [
        threading.Thread(target=worker, args=("A",)),
        threading.Thread(target=worker, args=("B",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    # Each thread sees only the HighState it pushed, despite the concurrent
    # push from the other thread. On the old shared stack both threads would
    # read whichever marker was pushed last.
    assert results == {"A": "A", "B": "B"}


def test_sshhighstate_shares_active_stack_with_highstate():
    """
    salt-ssh's ``SSHHighState`` subclasses ``BaseHighState`` (not ``HighState``)
    and its state wrapper calls ``st_.push_active()`` on every run. The
    active-stack accessors therefore have to live on ``BaseHighState``: when
    they lived on ``HighState``, ``SSHHighState`` had no ``push_active`` and
    every salt-ssh state execution raised
    ``'SSHHighState' object has no attribute 'push_active'``.

    Also pins the cross-subclass contract the pydsl renderer depends on: a
    non-``HighState`` ``BaseHighState`` subclass that pushes itself is visible
    to ``HighState.get_active()``.
    """
    from salt.client.ssh.state import SSHHighState

    assert issubclass(SSHHighState, salt.state.BaseHighState)
    assert not issubclass(SSHHighState, salt.state.HighState)
    for name in ("push_active", "pop_active", "get_active", "clear_active"):
        assert hasattr(SSHHighState, name), f"SSHHighState lost {name}"
    # Inherited from the shared base, not redefined per subclass.
    assert SSHHighState.push_active is salt.state.BaseHighState.push_active

    class _SSHMarker(SSHHighState):
        # Skip SSHHighState's heavy __init__; only the inherited accessors are
        # under test.
        def __init__(self):  # pylint: disable=super-init-not-called
            pass

    salt.state.BaseHighState.clear_active()
    try:
        marker = _SSHMarker()
        marker.push_active()
        assert salt.state.HighState.get_active() is marker
        marker.pop_active()
        assert salt.state.HighState.get_active() is None
    finally:
        salt.state.BaseHighState.clear_active()


def test_active_stack_falls_back_when_contextvars_unavailable():
    """
    On a salt-ssh target without a usable ``contextvars`` (e.g. Python 3.6,
    where the module is only available through the thin's backport and can pull
    in an incompatible ``typing_extensions``), ``import contextvars`` is guarded
    and ``_active_highstates`` is ``None``. The active-stack accessors must then
    degrade to a shared class-level list instead of raising -- salt-ssh runs a
    single execution per target, so a shared stack is safe there.
    """
    HighState = salt.state.HighState
    with patch.object(salt.state, "_active_highstates", None):
        salt.state.BaseHighState._shared_active_stack.clear()
        HighState.clear_active()
        assert HighState.get_active() is None

        a = _Marker("a")
        b = _Marker("b")
        a.push_active()
        assert HighState.get_active() is a
        b.push_active()
        assert HighState.get_active() is b
        b.pop_active()
        assert HighState.get_active() is a
        a.pop_active()
        assert HighState.get_active() is None

        a.push_active()
        HighState.clear_active()
        assert HighState.get_active() is None
    salt.state.BaseHighState._shared_active_stack.clear()

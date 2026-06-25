"""
Deterministic regression tests for the fork-safety fix (issues #68940
and #65709).

The bug: ``State.call_parallel()`` forks parallel-state children with
``multiprocessing.Process``.  On Linux's default ``fork`` start method
the child inherits the parent's live ZeroMQ REQ socket / tornado IOLoop
held by ``salt.fileclient.RemoteClient``, ``salt.crypt.AsyncAuth`` /
``SAuth`` and ``salt.utils.event.SaltEvent``.  Two sibling children
racing the inherited socket deadlock the asyncio loop (~100% CPU, never
completing).

The fix registers ``os.register_at_fork(after_in_child=...)`` handlers
on those classes that drop the inherited handles in any forked child;
the next use rebuilds them lazily.

These tests assert that contract directly instead of trying to
reproduce the deadlock.  Reproducing the deadlock end to end needs a
real master + ZeroMQ transport and is an inherently flaky "did not
hang" assertion (a green run only means the race did not fire that
time).  Salt's in-process functional test harness uses ``FSClient``,
which has no ZeroMQ socket, so it cannot reproduce it at all.  Forking
here and checking that the inherited references were cleared is
deterministic, fast, and fails immediately if the at-fork registration
is ever removed or broken.
"""

import os

import pytest

import salt.channel.client
import salt.crypt
import salt.fileclient
import salt.utils.event
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_on_windows(
        reason="os.fork / os.register_at_fork are POSIX-only",
    ),
]


def _run_in_fork(child_verdict):
    """Fork, run ``child_verdict`` in the child, and return the child's
    exit code to the caller in the parent.

    ``child_verdict`` returns an int: 0 means the post-fork state was
    correct, any other value identifies which assertion failed.  The
    child uses ``os._exit`` so it never runs pytest teardown.  The
    parent only inspects the exit status, so the result is fully
    deterministic and carries no shared state back.
    """
    pid = os.fork()
    if pid == 0:  # pragma: no cover - runs only in the forked child
        code = 99
        try:
            code = child_verdict()
        except BaseException:  # pylint: disable=broad-except
            code = 98
        finally:
            os._exit(code)
    _, status = os.waitpid(pid, 0)
    assert os.WIFEXITED(status), "forked child did not exit cleanly"
    return os.WEXITSTATUS(status)


def test_remoteclient_drops_channel_in_forked_child(minion_opts):
    """``RemoteClient`` is the direct #68940 / #65709 path: ``cp.hash_file``
    (file.managed) and ``cp.cache_file`` (cmd.script) both go through its
    ZeroMQ REQ channel.  After a fork the child must see ``_channel`` and
    ``_auth`` cleared so it builds its own channel instead of racing the
    parent's socket; the parent must keep its channel untouched.
    """
    mock_channel = MagicMock(name="ReqChannel", auth="sentinel-auth")
    with patch.object(
        salt.channel.client.ReqChannel, "factory", return_value=mock_channel
    ):
        client = salt.fileclient.RemoteClient(minion_opts)

    # Parent: eager construction installed the channel.
    assert client._channel is mock_channel
    assert client._auth == "sentinel-auth"

    def child_verdict():
        if client._channel is not None:
            return 11
        if client._auth != "":
            return 12
        return 0

    code = _run_in_fork(child_verdict)
    assert code == 0, {
        11: "_channel was inherited by the forked child (not cleared)",
        12: "_auth was inherited by the forked child (not cleared)",
        98: "child raised while checking RemoteClient state",
    }.get(code, f"unexpected child exit code {code}")

    # Parent must be untouched by the child's at-fork handler.
    assert client._channel is mock_channel
    assert client._auth == "sentinel-auth"


def test_asyncauth_sauth_clear_singletons_but_keep_creds_in_forked_child():
    """``AsyncAuth``/``SAuth`` singletons are bound to a tornado IOLoop
    that cannot cross a fork, so their instance maps must be empty in the
    child.  ``creds_map`` is deliberately preserved -- AES creds stay
    valid after fork and keeping them avoids a re-auth roundtrip; losing
    it would itself be a regression of the documented behaviour.
    """
    salt.crypt.AsyncAuth._register_atfork()
    salt.crypt.SAuth._register_atfork()

    class _Ref:
        """Bare ``object()`` is not weakref-able in CPython; a trivial
        user-defined class is, which is what the Weak*Dictionary
        containers require."""

    instance_key = _Ref()  # weakref-able + hashable
    sauth_value = _Ref()  # weakref-able value for the WeakValueDictionary
    salt.crypt.AsyncAuth.instance_map[instance_key] = "sentinel-instance"
    salt.crypt.AsyncAuth.creds_map["fork-test-key"] = "sentinel-creds"
    salt.crypt.SAuth.instances["fork-test-key"] = sauth_value

    try:
        assert instance_key in salt.crypt.AsyncAuth.instance_map
        assert salt.crypt.AsyncAuth.creds_map["fork-test-key"] == "sentinel-creds"
        assert "fork-test-key" in salt.crypt.SAuth.instances

        def child_verdict():
            if len(salt.crypt.AsyncAuth.instance_map) != 0:
                return 21
            if len(salt.crypt.SAuth.instances) != 0:
                return 22
            if salt.crypt.AsyncAuth.creds_map.get("fork-test-key") != "sentinel-creds":
                return 23
            return 0

        code = _run_in_fork(child_verdict)
        assert code == 0, {
            21: "AsyncAuth.instance_map was inherited (not reset) in the child",
            22: "SAuth.instances was inherited (not reset) in the child",
            23: "creds_map was wrongly dropped in the child (should persist)",
            98: "child raised while checking AsyncAuth/SAuth state",
        }.get(code, f"unexpected child exit code {code}")

        # Parent keeps everything.
        assert instance_key in salt.crypt.AsyncAuth.instance_map
        assert salt.crypt.AsyncAuth.creds_map["fork-test-key"] == "sentinel-creds"
        assert "fork-test-key" in salt.crypt.SAuth.instances
    finally:
        salt.crypt.AsyncAuth.instance_map.pop(instance_key, None)
        salt.crypt.AsyncAuth.creds_map.pop("fork-test-key", None)
        salt.crypt.SAuth.instances.pop("fork-test-key", None)


def test_saltevent_drops_sockets_in_forked_child(minion_opts):
    """A connected ``SaltEvent`` carries a subscriber/pusher socket and
    the ``cpub``/``cpush`` connected flags.  After a fork the child must
    see all four reset so ``connect_pub``/``connect_pull`` reopen fresh
    sockets instead of racing the parent's; the parent must keep its
    connection state.
    """
    event = salt.utils.event.SaltEvent("minion", opts=minion_opts, listen=False)

    # Simulate an already-connected bus without touching real sockets.
    sentinel_sub = object()
    sentinel_push = object()
    event.subscriber = sentinel_sub
    event.pusher = sentinel_push
    event.cpub = True
    event.cpush = True

    def child_verdict():
        if event.subscriber is not None:
            return 31
        if event.pusher is not None:
            return 32
        if event.cpub is not False:
            return 33
        if event.cpush is not False:
            return 34
        return 0

    code = _run_in_fork(child_verdict)
    assert code == 0, {
        31: "subscriber socket was inherited by the forked child",
        32: "pusher socket was inherited by the forked child",
        33: "cpub flag was inherited by the forked child",
        34: "cpush flag was inherited by the forked child",
        98: "child raised while checking SaltEvent state",
    }.get(code, f"unexpected child exit code {code}")

    # Parent must keep its connection state.
    assert event.subscriber is sentinel_sub
    assert event.pusher is sentinel_push
    assert event.cpub is True
    assert event.cpush is True

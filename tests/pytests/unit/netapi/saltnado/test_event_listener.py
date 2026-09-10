"""
Tests for ``salt.netapi.rest_tornado.saltnado.EventListener``.
"""

import asyncio
import inspect
from collections import defaultdict

from tornado.concurrent import Future

import salt.netapi.rest_tornado.saltnado as saltnado_app
from tests.support.mock import MagicMock, patch


def _make_event_listener():
    """
    Build an EventListener without touching the real master event bus.
    """
    event_listener = saltnado_app.EventListener.__new__(saltnado_app.EventListener)
    event_listener.tag_map = defaultdict(list)
    event_listener.request_map = defaultdict(list)
    event_listener.timeout_map = {}
    event_listener.event = MagicMock()
    return event_listener


def test_handle_event_socket_recv_is_coroutine_function():
    """
    Regression test for #66177.

    ``EventListener._handle_event_socket_recv`` is registered as the on_recv
    callback for the publish IPC client. The TCP-based publish client wraps
    the callback in ``asyncio.create_task(callback(msg))`` -- if the callback
    is a plain (sync) function returning ``None`` this raises
    ``TypeError: a coroutine was expected, got None`` (older Python versions
    reported ``TypeError: object NoneType can't be used in 'await'
    expression``), flooding salt-api / salt-master logs and silently dropping
    events.

    Asserting the callback is a coroutine function pins the contract so the
    bug cannot regress.
    """
    assert inspect.iscoroutinefunction(
        saltnado_app.EventListener._handle_event_socket_recv
    ), (
        "EventListener._handle_event_socket_recv must be an async function so "
        "that asyncio.create_task(callback(msg)) in the TCP publish client's "
        "on_recv_handler receives a coroutine rather than None. See issue "
        "#66177."
    )


async def test_handle_event_socket_recv_returns_awaitable():
    """
    Companion to ``test_handle_event_socket_recv_is_coroutine_function`` --
    verifies the callback can actually be wrapped with
    ``asyncio.create_task`` (the operation the TCP publish client performs)
    without raising ``TypeError``.
    """
    mod_opts = MagicMock()
    opts = MagicMock()
    with patch.object(saltnado_app.salt.utils.event, "get_event") as get_event:
        event = MagicMock()
        event.unpack.return_value = ("salt/job/123/ret/minion", {})
        get_event.return_value = event
        listener = saltnado_app.EventListener(mod_opts, opts)

    # The TCP publish client does this with the callback returned by the
    # on_recv path -- if _handle_event_socket_recv is sync this raises
    # TypeError: a coroutine was expected, got None.
    coro = listener._handle_event_socket_recv(b"raw-msg")
    try:
        assert inspect.isawaitable(coro), (
            "_handle_event_socket_recv must return an awaitable so the "
            "transport layer can schedule it with asyncio.create_task. "
            "See issue #66177."
        )
        task = asyncio.ensure_future(coro)
        await task
    finally:
        if inspect.iscoroutine(coro):
            coro.close()


async def test_handle_event_socket_recv_delivers_to_all_waiters():
    """
    A single matching event must resolve every future waiting on that tag.

    Regression test for #35798: the delivery loop used to remove futures from
    the very list it was iterating, skipping every other waiter so that only
    some websocket clients received the event.
    """
    event_listener = _make_event_listener()
    matcher = saltnado_app.EventListener.exact_matcher
    key = ("evt1", matcher)

    futures = [Future() for _ in range(4)]
    for future in futures:
        event_listener.tag_map[key].append(future)

    # event.unpack(raw) -> (mtag, data)
    event_listener.event.unpack.return_value = ("evt1", {"data": "foo"})

    await event_listener._handle_event_socket_recv("raw")

    for future in futures:
        assert future.done()
        assert future.result() == {"data": {"data": "foo"}, "tag": "evt1"}

    # every delivered future should be removed from the tag_map list
    assert event_listener.tag_map[key] == []


async def test_handle_event_socket_recv_websocket_default_subscription_35798():
    """
    One event must reach every concurrent websocket client subscribed through
    the production entry point.

    This is the exact #35798 scenario: AllEventsHandler.on_message in
    saltnado_websockets.py subscribes each client with
    ``event_listener.get_event(self)`` and nothing else, so the decisive
    arguments are the defaults, ``tag=""`` with ``prefix_matcher``, which
    every event matches. All clients therefore share a single tag_map entry,
    and a single incoming event must resolve all of their futures.
    """
    event_listener = _make_event_listener()

    # one future per connected websocket client, registered exactly the way
    # the websocket handlers do it: get_event(request) with no tag/matcher
    requests = [MagicMock() for _ in range(3)]
    futures = [event_listener.get_event(request) for request in requests]

    event_listener.event.unpack.return_value = (
        "salt/job/20260705000000000000/ret/minion1",
        {"data": "foo"},
    )

    await event_listener._handle_event_socket_recv("raw")

    for future in futures:
        assert future.done()
        assert future.result() == {
            "data": {"data": "foo"},
            "tag": "salt/job/20260705000000000000/ret/minion1",
        }

    key = ("", saltnado_app.EventListener.prefix_matcher)
    assert event_listener.tag_map[key] == []


async def test_handle_event_socket_recv_ignores_done_and_unmatched_35798():
    """
    Guard against overcorrection in the #35798 fix: iterating a snapshot of
    the futures list must not widen delivery. A future that is already done
    (for example one that timed out) must keep its original result and must
    not be re-resolved, and a future waiting on a different exact tag must
    stay pending and stay registered. This test passes with and without the
    fix.
    """
    event_listener = _make_event_listener()
    # exact_matcher is what SaltAPIHandler.get_minion_returns passes in
    # production (saltnado.py) for salt/job and syndic/job return tags
    matcher = saltnado_app.EventListener.exact_matcher
    matched_key = ("evt1", matcher)
    other_key = ("evt2", matcher)

    done_future = Future()
    done_future.set_result("already-done")
    pending_future = Future()
    other_future = Future()
    event_listener.tag_map[matched_key].extend([done_future, pending_future])
    event_listener.tag_map[other_key].append(other_future)

    event_listener.event.unpack.return_value = ("evt1", {"data": "foo"})

    await event_listener._handle_event_socket_recv("raw")

    # an already-done future must not be re-resolved with the event payload
    assert done_future.result() == "already-done"
    # the pending waiter on the matching tag still receives the event
    assert pending_future.result() == {"data": {"data": "foo"}, "tag": "evt1"}
    # a waiter on a non-matching exact tag must not receive the event
    assert not other_future.done()
    assert event_listener.tag_map[other_key] == [other_future]
    # done futures are skipped by the delivery loop, not removed
    assert event_listener.tag_map[matched_key] == [done_future]

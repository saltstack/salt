"""
Tests for ``salt.netapi.rest_tornado.saltnado.EventListener``.
"""

import asyncio
import inspect

import salt.netapi.rest_tornado.saltnado as saltnado_app
from tests.support.mock import MagicMock, patch


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

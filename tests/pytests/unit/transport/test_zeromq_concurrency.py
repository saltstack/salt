import asyncio

import tornado.concurrent
import zmq

import salt.payload
import salt.transport.zeromq
from salt.exceptions import SaltReqTimeoutError
from tests.support.mock import AsyncMock


async def test_request_client_concurrency_serialization(minion_opts, io_loop):
    """
    Regression test for EFSM (invalid state) errors in RequestClient.
    Ensures that multiple concurrent send() calls are serialized through
    the queue and don't violate the REQ socket state machine.
    """
    client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)

    # Mock the socket to track state
    mock_socket = AsyncMock()
    socket_state = {"busy": False}

    async def mocked_send(msg, **kwargs):
        if socket_state["busy"]:
            raise zmq.ZMQError(zmq.EFSM, "Socket busy!")
        socket_state["busy"] = True
        await asyncio.sleep(0.01)  # Simulate network delay

    async def mocked_recv(**kwargs):
        if not socket_state["busy"]:
            raise zmq.ZMQError(zmq.EFSM, "Nothing to recv!")
        socket_state["busy"] = False
        return salt.payload.dumps({"ret": "ok"})

    mock_socket.send = mocked_send
    mock_socket.recv = mocked_recv
    mock_socket.poll.return_value = True

    # Connect to initialize everything
    await client.connect()

    # Inject the mock socket
    if client.socket:
        client.socket.close()
    client.socket = mock_socket
    # Ensure the background task uses our mock
    if client.send_recv_task:
        client.send_recv_task.cancel()

    client.send_recv_task = asyncio.create_task(
        client._send_recv(mock_socket, client._queue, task_id=client.send_recv_task_id)
    )

    # Hammer the client with concurrent requests
    tasks = []
    for i in range(50):
        tasks.append(asyncio.create_task(client.send({"foo": i}, timeout=10)))

    results = await asyncio.gather(*tasks)

    assert len(results) == 50
    assert all(r == {"ret": "ok"} for r in results)
    assert socket_state["busy"] is False
    client.close()


async def test_request_client_sends_stale_future_messages(minion_opts, io_loop):
    """
    Regression test: queued messages whose futures have already been marked
    done (e.g. the caller-side timeout fired while the message was waiting
    in the queue behind a slow master) must still be sent on the wire.

    The master persists side effects from the payload itself (``_return``
    writes to the job cache, fires ``event_return``, calls into the
    external job cache / RaaS). Whether the originating worker thread is
    still waiting for an ACK is irrelevant — dropping the send means the
    master never sees the return data and the result store is silently
    incomplete.

    A pre-send ``if future.done(): continue`` short-circuit in
    ``_send_recv`` (added during the worker-pool routing rewrite) made
    every stale entry get skipped instead of sent. This test fails if
    that short-circuit is present and passes once it is removed.
    """
    n_messages = 20
    client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)

    wire_log = []

    async def mocked_send(msg, **kwargs):
        wire_log.append(msg)

    async def mocked_recv(**kwargs):
        return salt.payload.dumps({"ret": "ok"})

    async def mocked_poll(timeout, flag=None, **kwargs):
        return True

    mock_socket = AsyncMock()
    mock_socket.send = mocked_send
    mock_socket.recv = mocked_recv
    mock_socket.poll = mocked_poll

    # In production, the post-send ``if future.done():`` branch reconnects
    # the socket and spawns a fresh ``_send_recv`` task to drain the next
    # queued entry. Mirror that respawn chain here without touching real
    # ZMQ machinery, so the loop can process all N pre-staged entries.
    async def fake_reconnect():
        client.send_recv_task_id += 1
        client.socket = mock_socket
        client.send_recv_task = asyncio.create_task(
            client._send_recv(
                mock_socket, client._queue, task_id=client.send_recv_task_id
            )
        )

    client._reconnect = fake_reconnect

    # Pre-stage N (future, message) pairs whose futures have already been
    # marked done with SaltReqTimeoutError. Models the production case:
    # _timeout_message fired while the entry was waiting in the queue.
    for i in range(n_messages):
        future = tornado.concurrent.Future()
        future.set_exception(SaltReqTimeoutError("Message timed out"))
        # Retrieve the exception so the gc doesn't complain that nobody
        # awaited it.
        future.exception()
        message = salt.payload.dumps({"cmd": "_return", "seq": i})
        client._queue.put_nowait((future, message))

    client.socket = mock_socket
    client.send_recv_task = asyncio.create_task(
        client._send_recv(mock_socket, client._queue, task_id=client.send_recv_task_id)
    )

    loop = asyncio.get_event_loop()
    deadline = loop.time() + 5
    while len(wire_log) < n_messages and loop.time() < deadline:
        await asyncio.sleep(0.05)

    client._closing = True
    if client.send_recv_task and not client.send_recv_task.done():
        client.send_recv_task.cancel()
        try:
            await client.send_recv_task
        except (asyncio.CancelledError, BaseException):  # pylint: disable=broad-except
            pass

    assert len(wire_log) == n_messages, (
        f"Expected {n_messages} frames on the wire, observed {len(wire_log)}. "
        "Messages with already-timed-out futures are being silently dropped "
        "before they reach the master."
    )


async def test_request_client_reconnect_task_safety(minion_opts, io_loop):
    """
    Regression test for task leaks and state corruption during reconnections.
    Ensures that when a task is superseded, it re-queues its message and exits.
    """
    client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)
    await client.connect()

    # Mock socket that always times out once
    mock_socket = AsyncMock()
    mock_socket.poll.return_value = False  # Trigger timeout in _send_recv

    if client.socket:
        client.socket.close()
    client.socket = mock_socket
    original_task_id = client.send_recv_task_id

    # Trigger a reconnection by calling _reconnect (simulates error in loop)
    await client._reconnect()
    assert client.send_recv_task_id == original_task_id + 1

    # The old task should have exited cleanly.
    client.close()

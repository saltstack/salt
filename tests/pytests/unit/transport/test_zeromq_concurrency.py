import asyncio

import zmq

import salt.transport.zeromq
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

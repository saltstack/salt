"""Repeated ZeroMQ requests through a synchronous wrapper on an active loop."""

import queue
import threading

import zmq

import salt.transport.zeromq
from salt.utils.asynchronous import SyncWrapper


async def test_request_worker_survives_wrapped_sends(minion_opts):
    ready = queue.Queue()
    errors = []

    def serve():
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.setsockopt(zmq.RCVTIMEO, 3000)
        try:
            ready.put(socket.bind_to_random_port("tcp://127.0.0.1"))
            for _ in range(2):
                socket.send(socket.recv())
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)
        finally:
            socket.close(linger=0)
            context.destroy(linger=0)

    thread = threading.Thread(target=serve)
    thread.start()
    port = ready.get(timeout=5)
    opts = dict(minion_opts, master_uri=f"tcp://127.0.0.1:{port}")
    client = SyncWrapper(
        salt.transport.zeromq.RequestClient,
        args=(opts,),
        async_methods=["send"],
        close_methods=["close"],
        loop_kwarg="io_loop",
    )
    try:
        assert client.send("first", timeout=1) == "first"
        assert not client.obj.send_recv_task.done()
        assert client.send("second", timeout=1) == "second"
    finally:
        client.close()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert not errors

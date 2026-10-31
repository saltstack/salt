"""Exercise master pings through real TCP and ZeroMQ request transports."""

import asyncio
import queue
import socketserver
import threading
from types import SimpleNamespace

import pytest

import salt.client
import salt.config
import salt.modules.status as status
import salt.payload
import salt.transport.frame
import salt.utils.msgpack
from tests.support.mock import AsyncMock, MagicMock

pytestmark = [pytest.mark.timeout(30)]


class PingHandler(socketserver.BaseRequestHandler):
    def handle(self):
        unpacker = salt.utils.msgpack.Unpacker(raw=False)
        while data := self.request.recv(4096):
            unpacker.feed(data)
            for message in unpacker:
                self.server.requests.put(message["body"])
                if self.server.reply:
                    self.request.sendall(
                        salt.transport.frame.frame_msg(True, header=message["head"])
                    )


@pytest.fixture(params=["tcp", "zeromq"])
def master_server(request):
    transport = request.param
    requests = queue.Queue()
    if transport == "tcp":
        with socketserver.ThreadingTCPServer(("127.0.0.1", 0), PingHandler) as server:
            server.daemon_threads = True
            server.requests = requests
            server.reply = True
            thread = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
            )
            thread.start()
            try:
                yield transport, server.server_address[1], requests, server
            finally:
                server.shutdown()
                thread.join(5)
    else:
        zmq = pytest.importorskip("zmq")
        ready = queue.Queue()
        stop = threading.Event()
        options = type("ServerOptions", (), {"reply": True})()

        def serve():
            context = zmq.Context()
            socket = context.socket(zmq.REP)
            try:
                port = socket.bind_to_random_port("tcp://127.0.0.1")
                ready.put(port)
                while not stop.is_set():
                    if not socket.poll(50):
                        continue
                    requests.put(salt.payload.loads(socket.recv()))
                    if options.reply:
                        socket.send(salt.payload.dumps(True))
                    else:
                        stop.wait(10)
                        return
            finally:
                socket.close(linger=0)
                context.term()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            yield transport, ready.get(timeout=5), requests, options
        finally:
            stop.set()
            thread.join(5)
            assert not thread.is_alive()


@pytest.fixture
def ping_client(master_server, monkeypatch):
    transport, port, _, _ = master_server
    opts = dict(salt.config.DEFAULT_MINION_OPTS)
    opts.update(
        transport=transport,
        master="127.0.0.1",
        master_port=port,
        master_uri=f"tcp://127.0.0.1:{port}",
        ipv6=False,
        auth_timeout=2,
    )
    event = MagicMock()
    event.__enter__.return_value = event
    event.fire_event_async = AsyncMock(return_value=True)
    monkeypatch.setattr(status, "__opts__", opts, raising=False)
    monkeypatch.setattr(salt.utils.event, "get_event", MagicMock(return_value=event))
    transports = []
    factory = salt.transport.request_client

    def record(*args, **kwargs):
        client = factory(*args, **kwargs)
        transports.append(client)
        return client

    monkeypatch.setattr(salt.transport, "request_client", record)
    return opts, event, transports


async def test_repeated_pings_release_request_resources(master_server, ping_client):
    transport, _, requests, _ = master_server
    _, event, clients = ping_client
    loop = asyncio.get_running_loop()
    original_tasks = asyncio.all_tasks()
    original_timers = set(loop._scheduled)
    for _ in range(5):
        assert await status.ping_master("127.0.0.1") is True
    assert requests.qsize() == 5
    for _ in range(5):
        request = requests.get_nowait()
        assert request["enc"] == "clear"
        assert request["load"] == {"cmd": "ping"}
    assert event.fire_event_async.await_count == 5
    assert len(clients) == 5
    assert all(client._closing for client in clients)
    if transport == "zeromq":
        assert all(
            client.context is None and client.socket is None for client in clients
        )
        assert all(client.send_recv_task.done() for client in clients)
    else:
        assert all(client._stream is None and client.task is None for client in clients)

    await asyncio.sleep(0)
    assert not asyncio.all_tasks().difference(original_tasks)
    assert not [
        handle
        for handle in loop._scheduled
        if handle not in original_timers and not handle.cancelled()
    ]


async def test_unresponsive_master_releases_transport_without_failback(
    master_server, ping_client
):
    transport, _, _, server = master_server
    opts, event, clients = ping_client
    server.reply = False
    opts["auth_timeout"] = 0.1
    assert await status.ping_master("127.0.0.1") is False
    event.fire_event_async.assert_not_awaited()
    assert len(clients) == 1
    assert clients[0]._closing
    if transport == "zeromq":
        assert clients[0].context is None and clients[0].socket is None
    else:
        assert clients[0]._stream is None and clients[0].task is None


@pytest.mark.parametrize("reply", [False, True])
def test_public_caller_ping_returns_bool_over_real_transport(
    master_server, ping_client, reply
):
    _, _, requests, server = master_server
    opts, event, clients = ping_client
    server.reply = reply
    opts["auth_timeout"] = 0.1 if not reply else 2
    caller = object.__new__(salt.client.Caller)
    caller.sminion = SimpleNamespace(
        functions={"status.ping_master": status.ping_master}
    )
    assert caller.cmd("status.ping_master", "127.0.0.1") is reply
    assert requests.qsize() == 1
    assert clients[0]._closing
    assert event.fire_event_async.await_count == int(reply)


def test_public_caller_empty_master_is_false():
    caller = object.__new__(salt.client.Caller)
    caller.sminion = SimpleNamespace(
        functions={"status.ping_master": status.ping_master}
    )
    assert caller.cmd("status.ping_master", "") is False

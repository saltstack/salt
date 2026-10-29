"""Exercise master pings through real TCP and ZeroMQ request transports."""

import asyncio
import queue
import socketserver
import threading

import pytest

import salt.config
import salt.modules.status as status
import salt.payload
import salt.transport.frame
import salt.utils.asynchronous
import salt.utils.msgpack
from tests.support.mock import MagicMock

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
    monkeypatch.setattr(status, "__opts__", opts, raising=False)
    monkeypatch.setattr(salt.utils.event, "get_event", MagicMock(return_value=event))
    bridge = salt.utils.asynchronous.LoopBridge()
    monkeypatch.setattr(salt.utils.asynchronous, "get_bridge", lambda: bridge)
    transports = []
    factory = salt.transport.request_client

    def record(*args, **kwargs):
        client = factory(*args, **kwargs)
        transports.append(client)
        return client

    monkeypatch.setattr(salt.transport, "request_client", record)
    try:
        yield opts, event, bridge, transports
    finally:
        bridge.shutdown()


def test_repeated_pings_release_request_resources(master_server, ping_client):
    transport, _, requests, _ = master_server
    _, event, bridge, clients = ping_client
    loop = bridge._loop
    for _ in range(5):
        assert status.ping_master("127.0.0.1") is True
        assert bridge._loop is loop
    assert requests.qsize() == 5
    for _ in range(5):
        request = requests.get_nowait()
        assert request["enc"] == "clear"
        assert request["load"] == {"cmd": "ping"}
    assert event.fire_event.call_count == 5
    assert len(clients) == 5
    assert all(client._closing for client in clients)
    if transport == "zeromq":
        assert all(
            client.context is None and client.socket is None for client in clients
        )
        assert all(client.send_recv_task.done() for client in clients)
    else:
        assert all(client._stream is None and client.task is None for client in clients)

    async def remaining_work():
        await asyncio.sleep(0)
        tasks = asyncio.all_tasks() - {asyncio.current_task()}
        timers = [handle for handle in loop._scheduled if not handle.cancelled()]
        return len(tasks), len(timers)

    assert bridge.run(remaining_work()) == (0, 0)


def test_unresponsive_master_releases_transport_without_failback(
    master_server, ping_client
):
    transport, _, _, server = master_server
    opts, event, _, clients = ping_client
    server.reply = False
    opts["auth_timeout"] = 0.1
    assert status.ping_master("127.0.0.1") is False
    event.fire_event.assert_not_called()
    assert len(clients) == 1
    assert clients[0]._closing
    if transport == "zeromq":
        assert clients[0].context is None and clients[0].socket is None
    else:
        assert clients[0]._stream is None and clients[0].task is None

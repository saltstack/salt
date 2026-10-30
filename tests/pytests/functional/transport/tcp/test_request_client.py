"""
Tests for the TCP RequestClient while the master is down or unreachable.

See #66966.
"""

import asyncio
import inspect
import logging
import os
import time

import pytest
import pytestshellutils.utils.ports
import tornado.iostream

import salt.channel.client
import salt.exceptions
import salt.transport
import salt.transport.tcp
import salt.utils.channel
from tests.support.mock import patch

pytestmark = [
    pytest.mark.core_test,
]


class Master:
    """
    A TCP RequestServer that echoes every request back. Its port is bound
    right away so nothing else takes it, but connections are refused until
    start() is called.
    """

    def __init__(self, opts, process_manager, io_loop):
        self.opts = opts
        self.process_manager = process_manager
        self.io_loop = io_loop
        self.requests = []
        self._bind()

    def _bind(self):
        self.server = salt.transport.request_server(self.opts)
        self.server.pre_fork(self.process_manager)

    async def _handler(self, payload):
        self.requests.append(payload)
        return payload

    def start(self):
        if self.server is None:
            self._bind()
        self.server.post_fork(self._handler, self.io_loop)

    def stop(self):
        if self.server is not None:
            self.server.close()
            self.server = None

    def connections(self):
        return len(self.server.req_server.clients)


class GatedConnect:
    """
    Stand-in for TCPClient.connect that doesn't connect until released.
    """

    def __init__(self, connect):
        self._connect = connect
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.cancelled = 0

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        self.entered.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        return await self._connect(*args, **kwargs)


@pytest.fixture
def master(io_loop, master_opts, process_manager):
    opts = master_opts.copy()
    opts["transport"] = "tcp"
    opts["ret_port"] = pytestshellutils.utils.ports.get_unused_localhost_port()
    master = Master(opts, process_manager, io_loop)
    try:
        yield master
    finally:
        master.stop()


@pytest.fixture
def client_opts(minion_opts, master):
    opts = minion_opts.copy()
    opts["transport"] = "tcp"
    opts["master_uri"] = f"tcp://{master.opts['interface']}:{master.opts['ret_port']}"
    opts["tcp_reconnect_backoff"] = 0.2
    return opts


@pytest.fixture
def request_client(io_loop, client_opts):
    client = salt.transport.request_client(client_opts, io_loop)
    try:
        yield client
    finally:
        client.close()


def _readers():
    return [
        task
        for task in asyncio.all_tasks()
        if not task.done()
        and task.get_coro().__qualname__ == "RequestClient._stream_return"
    ]


async def test_send_times_out_while_master_is_down(request_client):
    """
    Nothing listens on the master port. send() raises SaltReqTimeoutError
    after its timeout instead of waiting for the master to come back.
    """
    start = time.monotonic()
    with pytest.raises(salt.exceptions.SaltReqTimeoutError):
        await asyncio.wait_for(request_client.send({"cmd": "ping"}, timeout=1), 10)
    assert 0.9 < time.monotonic() - start < 5
    assert request_client.send_future_map == {}


async def test_send_times_out_while_connect_hangs(request_client):
    """
    The master never answers the connect (a blackholed address). The
    timeout still covers it.
    """
    gated = GatedConnect(request_client._tcp_client.connect)
    with patch.object(request_client._tcp_client, "connect", gated):
        start = time.monotonic()
        with pytest.raises(salt.exceptions.SaltReqTimeoutError):
            await asyncio.wait_for(request_client.send({"cmd": "ping"}, timeout=1), 10)
        assert 0.9 < time.monotonic() - start < 5
        assert gated.calls == 1


async def test_channel_tries_while_master_is_down(io_loop, client_opts):
    """
    A channel send gives up after tries * timeout, as on zeromq.
    """
    channel = salt.channel.client.AsyncReqChannel.factory(
        client_opts, crypt="clear", io_loop=io_loop
    )
    try:
        start = time.monotonic()
        with pytest.raises(salt.exceptions.SaltReqTimeoutError):
            await asyncio.wait_for(
                channel.send({"cmd": "ping"}, tries=2, timeout=1), 15
            )
        assert 1.8 < time.monotonic() - start < 8
    finally:
        channel.close()


async def test_concurrent_sends_share_one_connection(request_client, master):
    """
    Requests sent while the master is down wait on one connect attempt and
    go out in order on one connection once the master is up.
    """
    sends = [
        asyncio.ensure_future(request_client.send({"seq": seq}, timeout=30))
        for seq in range(3)
    ]
    # Let a few connect attempts fail first.
    await asyncio.sleep(1)
    assert not any(send.done() for send in sends)
    master.start()
    replies = await asyncio.wait_for(asyncio.gather(*sends), 15)
    assert replies == [{"seq": 0}, {"seq": 1}, {"seq": 2}]
    assert master.requests == replies
    assert master.connections() == 1
    assert len(_readers()) == 1


async def test_concurrent_sends_over_ipc_share_one_connection(
    io_loop, master_opts, process_manager
):
    """
    A master sends requests to its worker pools over ipc://. Concurrent
    first sends on a new client share one connection.
    """
    opts = master_opts.copy()
    opts["transport"] = "tcp"
    opts["ipc_mode"] = "ipc"
    opts["workers_ipc_name"] = "workers-66966.ipc"
    master = Master(opts, process_manager, io_loop)
    try:
        master.start()
        # PoolRoutingChannel builds its clients from the master's opts.
        client_opts = opts.copy()
        path = os.path.join(opts["sock_dir"], opts["workers_ipc_name"])
        client_opts["master_uri"] = f"ipc://{path}"
        client = salt.utils.channel.create_request_client(client_opts, io_loop)
        try:
            sends = [client.send({"seq": seq}, timeout=30) for seq in range(5)]
            replies = await asyncio.wait_for(asyncio.gather(*sends), 15)
            assert replies == [{"seq": seq} for seq in range(5)]
            assert master.connections() == 1
            assert len(_readers()) == 1
        finally:
            client.close()
    finally:
        master.stop()


async def test_timed_out_request_is_not_sent_after_connect(request_client, master):
    """
    A request that timed out while the client was connecting is never
    sent, and its timeout doesn't cancel the connect attempt another
    request is waiting on.
    """
    master.start()
    gated = GatedConnect(request_client._tcp_client.connect)
    with patch.object(request_client._tcp_client, "connect", gated):
        expired = asyncio.ensure_future(request_client.send({"seq": 0}, timeout=1))
        waiting = asyncio.ensure_future(request_client.send({"seq": 1}, timeout=30))
        await asyncio.wait_for(gated.entered.wait(), 5)
        with pytest.raises(salt.exceptions.SaltReqTimeoutError):
            await asyncio.wait_for(expired, 10)
        assert gated.calls == 1
        assert gated.cancelled == 0
        assert not waiting.done()
        gated.release.set()
        assert await asyncio.wait_for(waiting, 10) == {"seq": 1}
    assert master.requests == [{"seq": 1}]
    assert master.connections() == 1


async def test_cancelled_send_is_not_sent(request_client, master):
    """
    A caller that cancels send() while it waits for the connection leaves
    nothing behind, doesn't cancel the connect attempt, and its request is
    never sent.
    """
    master.start()
    gated = GatedConnect(request_client._tcp_client.connect)
    with patch.object(request_client._tcp_client, "connect", gated):
        send = asyncio.ensure_future(request_client.send({"seq": 0}, timeout=30))
        await asyncio.wait_for(gated.entered.wait(), 5)
        send.cancel()
        with pytest.raises(asyncio.CancelledError):
            await send
        assert request_client.send_future_map == {}
        assert gated.cancelled == 0
        gated.release.set()
        reply = await asyncio.wait_for(request_client.send({"seq": 1}, timeout=10), 15)
        assert reply == {"seq": 1}
    assert master.requests == [{"seq": 1}]


async def test_write_error_fails_request(request_client, master):
    """
    A write that fails right away fails the request without waiting for
    its timeout.
    """
    master.start()
    reply = await asyncio.wait_for(request_client.send({"seq": 0}, timeout=10), 15)
    assert reply == {"seq": 0}
    with patch.object(
        request_client._stream,
        "write",
        side_effect=tornado.iostream.StreamClosedError(),
    ):
        start = time.monotonic()
        with pytest.raises(tornado.iostream.StreamClosedError):
            await asyncio.wait_for(request_client.send({"seq": 1}, timeout=30), 10)
        assert time.monotonic() - start < 5
    assert request_client.send_future_map == {}
    assert master.requests == [{"seq": 0}]


async def test_timeout_during_large_write(request_client, master, caplog):
    """
    The master accepts the connection but never reads. A large request
    still times out, and nothing is logged as an error.
    """
    # Listen without a server: the kernel accepts, nobody reads.
    master.server.socket.listen(5)
    load = {"blob": "x" * (32 * 1024 * 1024)}
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(salt.exceptions.SaltReqTimeoutError):
            await asyncio.wait_for(request_client.send(load, timeout=1), 10)
        await asyncio.sleep(0.2)
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert errors == []


@pytest.mark.parametrize("stuck_in", ["connect", "backoff"])
async def test_close_cancels_connect_in_flight(request_client, stuck_in):
    """
    close() stops a connect attempt that is still running, fails the
    request waiting on it and leaves no tasks behind.
    """
    before = asyncio.all_tasks()
    gated = GatedConnect(request_client._tcp_client.connect)
    with patch.object(request_client._tcp_client, "connect", gated):
        if stuck_in == "backoff":
            # Fail the connect and sleep before the next attempt.
            gated.release.set()
            request_client.backoff = 60
        send = asyncio.ensure_future(request_client.send({"cmd": "ping"}, timeout=None))
        await asyncio.wait_for(gated.entered.wait(), 5)
        # For "backoff", let the refused connect fail and the client sleep.
        await asyncio.sleep(0.5)
        request_client.close()
        with pytest.raises(salt.transport.tcp.ClosingError):
            await asyncio.wait_for(send, 5)
    assert gated.calls == 1
    assert gated.cancelled == (1 if stuck_in == "connect" else 0)
    assert request_client._connect_task.done()
    assert [task for task in asyncio.all_tasks() - before if not task.done()] == []


async def test_close_before_connect_attempt_starts(request_client):
    """
    close() right after send(), before the shared connect attempt has run
    at all, still fails the request with ClosingError.
    """
    send = asyncio.ensure_future(request_client.send({"cmd": "ping"}, timeout=None))
    while request_client._connect_task is None:
        await asyncio.sleep(0)
    connect = request_client._connect_task.get_coro()
    assert inspect.getcoroutinestate(connect) == inspect.CORO_CREATED
    request_client.close()
    with pytest.raises(salt.transport.tcp.ClosingError):
        await asyncio.wait_for(send, 5)
    assert request_client.send_future_map == {}


def test_close_with_loop_stopped_leaves_no_tasks(io_loop, request_client):
    """
    close() from sync code (loop not running) while a connect attempt is
    retrying leaves no pending task on the loop.
    """
    loop = io_loop.asyncio_loop
    with pytest.raises(salt.exceptions.SaltReqTimeoutError):
        loop.run_until_complete(
            asyncio.wait_for(request_client.send({"cmd": "ping"}, timeout=0.5), 5)
        )
    assert [task for task in asyncio.all_tasks(loop) if not task.done()]
    request_client.close()
    assert [task for task in asyncio.all_tasks(loop) if not task.done()] == []


async def test_sync_channel_close_from_async_code(client_opts, caplog):
    """
    A sync channel used from code running on another loop closes without
    errors after a send timed out.
    """
    channel = salt.channel.client.ReqChannel.factory(client_opts, crypt="clear")
    try:
        with pytest.raises(salt.exceptions.SaltReqTimeoutError):
            channel.send({"cmd": "ping"}, tries=1, timeout=1)
    finally:
        with caplog.at_level(logging.ERROR):
            channel.close()
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert errors == []


async def test_send_without_timeout_waits_for_master(request_client, master):
    """
    timeout=None still means wait until the master answers.
    """
    send = asyncio.ensure_future(request_client.send({"cmd": "ping"}, timeout=None))
    await asyncio.sleep(2)
    assert not send.done()
    master.start()
    assert await asyncio.wait_for(send, 10) == {"cmd": "ping"}


async def test_send_after_master_restart(request_client, master):
    """
    Once connected, the client still reconnects when the master restarts.
    """
    master.start()
    reply = await asyncio.wait_for(request_client.send({"seq": 0}, timeout=10), 15)
    assert reply == {"seq": 0}
    stream = request_client._stream
    master.stop()
    # Wait for the client to see the connection drop.
    start = time.monotonic()
    while request_client._stream is stream:
        assert time.monotonic() - start < 5
        await asyncio.sleep(0.05)
    send = asyncio.ensure_future(request_client.send({"seq": 1}, timeout=30))
    await asyncio.sleep(0.5)
    assert not send.done()
    master.start()
    assert await asyncio.wait_for(send, 15) == {"seq": 1}
    assert master.requests == [{"seq": 0}, {"seq": 1}]
    assert master.connections() == 1
    assert len(_readers()) == 1

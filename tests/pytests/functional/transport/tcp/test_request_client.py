"""
Tests for the TCP RequestClient while the master is down or unreachable.

See #66966.
"""

import asyncio
import gc
import inspect
import logging
import os
import sys
import time

import pytest
import pytestshellutils.utils.ports
import tornado.iostream

import salt.channel.client
import salt.exceptions
import salt.transport
import salt.transport.frame
import salt.transport.tcp
import salt.utils.channel
import salt.utils.msgpack
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


class FakeStream:
    """
    Stand-in for the client's IOStream. The test completes each read by
    hand, so it decides what the client's reader wakes up to, and when.
    """

    def __init__(self):
        self.pending_read = None
        self.requests = []
        self._closed = False

    def read_bytes(self, num_bytes, partial=False):
        self.pending_read = asyncio.get_running_loop().create_future()
        return self.pending_read

    def write(self, data):
        if self._closed:
            raise tornado.iostream.StreamClosedError()
        msg = salt.utils.msgpack.loads(data)
        self.requests.append(salt.transport.frame.decode_embedded_strs(msg))

    def close(self):
        # Like IOStream, fail the pending read right away.
        self._closed = True
        if self.pending_read is not None and not self.pending_read.done():
            self.pending_read.set_exception(tornado.iostream.StreamClosedError())

    async def received(self, body):
        """
        Wait until the client has sent this request and is reading.
        """
        while (
            body not in [request["body"] for request in self.requests]
            or self.pending_read is None
            or self.pending_read.done()
        ):
            await asyncio.sleep(0.01)

    def reply(self, body):
        """
        Answer the request that carried this body with the same body.
        """
        mid = next(req["head"]["mid"] for req in self.requests if req["body"] == body)
        self.pending_read.set_result(
            salt.transport.frame.frame_msg(body, header={"mid": mid})
        )

    def reply_without_body(self):
        """
        Send a reply the client can't parse.
        """
        self.pending_read.set_result(salt.utils.msgpack.dumps({"head": {}}))


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


@pytest.fixture
def fake_streams(request_client):
    """
    Each connect of request_client gets a new FakeStream, appended to the
    list this yields.
    """
    streams = []

    async def getstream(**kwargs):
        streams.append(FakeStream())
        return streams[-1]

    with patch.object(request_client, "getstream", getstream):
        yield streams


def _worker_pool_opts(master_opts):
    """
    The opts of a master that sends requests to its worker pools over
    ipc://, and the opts of the clients its PoolRoutingChannel builds.
    """
    opts = master_opts.copy()
    opts["transport"] = "tcp"
    opts["ipc_mode"] = "ipc"
    opts["workers_ipc_name"] = "workers-66966.ipc"
    client_opts = opts.copy()
    path = os.path.join(opts["sock_dir"], opts["workers_ipc_name"])
    client_opts["master_uri"] = f"ipc://{path}"
    return opts, client_opts


def _readers():
    return [
        task
        for task in asyncio.all_tasks()
        if not task.done()
        and task.get_coro().__qualname__ == "RequestClient._stream_return"
    ]


async def _sent(streams, body):
    """
    Wait until the client has connected, sent this request and is reading.
    Return its stream.
    """
    while not streams:
        await asyncio.sleep(0.01)
    await streams[-1].received(body)
    return streams[-1]


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
    opts, client_opts = _worker_pool_opts(master_opts)
    master = Master(opts, process_manager, io_loop)
    try:
        master.start()
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


async def test_send_over_ipc_waits_for_workers(io_loop, master_opts, process_manager):
    """
    A request to a worker pool whose socket refuses connections keeps
    retrying under its timeout, and is answered once the workers listen.
    """
    opts, client_opts = _worker_pool_opts(master_opts)
    client_opts["tcp_reconnect_backoff"] = 0.2
    # The socket is bound, but connects are refused until start().
    master = Master(opts, process_manager, io_loop)
    try:
        client = salt.utils.channel.create_request_client(client_opts, io_loop)
        try:
            send = asyncio.ensure_future(client.send({"seq": 0}, timeout=30))
            # Let a few connect attempts fail first.
            await asyncio.sleep(1)
            assert not send.done()
            master.start()
            assert await asyncio.wait_for(send, 15) == {"seq": 0}
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


async def test_cancel_as_reply_arrives(request_client, fake_streams):
    """
    A caller cancels send() in the loop iteration its reply arrives in.
    Other requests on the connection still get their replies.
    """
    other = asyncio.ensure_future(request_client.send({"seq": 0}, timeout=30))
    cancelled = asyncio.ensure_future(request_client.send({"seq": 1}, timeout=30))
    stream = await asyncio.wait_for(_sent(fake_streams, {"seq": 1}), 5)
    await asyncio.wait_for(stream.received({"seq": 0}), 5)
    # The reply wakes the reader up before the cancel wakes send() up.
    stream.reply({"seq": 1})
    cancelled.cancel()
    await asyncio.sleep(0.1)
    assert cancelled.cancelled()
    assert not other.done()
    stream.reply({"seq": 0})
    assert await asyncio.wait_for(other, 5) == {"seq": 0}
    assert len(fake_streams) == 1


async def test_cancel_as_connection_drops(request_client, fake_streams):
    """
    A caller cancels send() in the loop iteration the connection drops in.
    The client reconnects, and later requests are answered.
    """
    cancelled = asyncio.ensure_future(request_client.send({"seq": 0}, timeout=30))
    stream = await asyncio.wait_for(_sent(fake_streams, {"seq": 0}), 5)
    # The drop wakes the reader up before the cancel wakes send() up.
    stream.close()
    cancelled.cancel()
    await asyncio.sleep(0.1)
    assert cancelled.cancelled()
    assert len(fake_streams) == 2
    send = asyncio.ensure_future(request_client.send({"seq": 1}, timeout=30))
    await asyncio.wait_for(fake_streams[1].received({"seq": 1}), 5)
    fake_streams[1].reply({"seq": 1})
    assert await asyncio.wait_for(send, 5) == {"seq": 1}


async def test_cancel_as_bad_reply_arrives(request_client, fake_streams):
    """
    A caller cancels send() in the loop iteration a reply the client can't
    parse arrives in. The client reconnects, and later requests are
    answered.
    """
    cancelled = asyncio.ensure_future(request_client.send({"seq": 0}, timeout=30))
    stream = await asyncio.wait_for(_sent(fake_streams, {"seq": 0}), 5)
    # The bad reply wakes the reader up before the cancel wakes send() up.
    stream.reply_without_body()
    cancelled.cancel()
    await asyncio.sleep(0.1)
    assert cancelled.cancelled()
    assert len(fake_streams) == 2
    send = asyncio.ensure_future(request_client.send({"seq": 1}, timeout=30))
    await asyncio.wait_for(fake_streams[1].received({"seq": 1}), 5)
    fake_streams[1].reply({"seq": 1})
    assert await asyncio.wait_for(send, 5) == {"seq": 1}


async def test_reader_cancelled_while_reconnecting(request_client, fake_streams):
    """
    Something other than close() cancels the reader while it reconnects
    after the connection dropped. The new connection still gets a reader,
    and later requests are answered.
    """
    gate = asyncio.Event()
    getstream = request_client.getstream

    async def gated_getstream(**kwargs):
        # Hold the reconnect until the reader is cancelled.
        if fake_streams:
            await gate.wait()
        return await getstream(**kwargs)

    with patch.object(request_client, "getstream", gated_getstream):
        dropped = asyncio.ensure_future(request_client.send({"seq": 0}, timeout=30))
        stream = await asyncio.wait_for(_sent(fake_streams, {"seq": 0}), 5)
        reader = request_client.task
        stream.close()
        with pytest.raises(tornado.iostream.StreamClosedError):
            await asyncio.wait_for(dropped, 5)
        # The reader now waits on the reconnect.
        reader.cancel()
        await asyncio.wait([reader], timeout=5)
        assert reader.cancelled()
        gate.set()
        await asyncio.sleep(0.1)
    assert len(fake_streams) == 2
    assert len(_readers()) == 1
    send = asyncio.ensure_future(request_client.send({"seq": 1}, timeout=30))
    await asyncio.wait_for(fake_streams[1].received({"seq": 1}), 5)
    fake_streams[1].reply({"seq": 1})
    assert await asyncio.wait_for(send, 5) == {"seq": 1}


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


@pytest.mark.parametrize(
    "master_state",
    [
        "down",
        pytest.param(
            "silent",
            marks=pytest.mark.skipif(
                sys.version_info < (3, 11),
                reason=(
                    "On Python 3.10 SyncWrapper cancels the client's reader,"
                    " and the send never returns"
                ),
            ),
        ),
    ],
)
async def test_sync_channel_close_from_async_code(
    client_opts, master, caplog, master_state
):
    """
    A sync channel used from code running on another loop, closed after a
    send timed out, logs no errors, also once the client is garbage
    collected. The master is down, or accepts the connection and never
    answers.
    """
    if master_state == "silent":
        # Listen without a server: the kernel accepts, nobody reads.
        master.server.socket.listen(5)
    # ERROR only: a captured warning's traceback would keep the client alive
    # past gc.collect().
    with caplog.at_level(logging.ERROR):
        channel = salt.channel.client.ReqChannel.factory(client_opts, crypt="clear")
        try:
            with pytest.raises(salt.exceptions.SaltReqTimeoutError):
                channel.send({"cmd": "ping"}, tries=1, timeout=1)
            if master_state == "silent":
                # Connected, so close() also has a reader to stop.
                assert channel.obj.transport.task is not None
        finally:
            channel.close()
            # asyncio logs a task close() left pending when it is collected.
            gc.collect()
    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert errors == []


@pytest.mark.parametrize("master_state", ["down", "silent"])
def test_close_after_loop_is_closed(
    client_opts, master, caplog, monkeypatch, master_state
):
    """
    The loop is closed while a request waits for the master, and the
    client is closed and garbage collected after that, as when a minion is
    destroyed after its loop was closed. close() doesn't raise, the
    request's coroutine closes cleanly, and the tasks close() stops aren't
    reported as destroyed while pending. The master is down, or accepts
    the connection and never answers.
    """
    if master_state == "silent":
        # Listen without a server: the kernel accepts, nobody reads.
        master.server.socket.listen(5)
    unraisable = []
    monkeypatch.setattr(sys, "unraisablehook", unraisable.append)
    loop = asyncio.new_event_loop()
    client = salt.transport.request_client(client_opts, loop)
    send = loop.create_task(client.send({"cmd": "ping"}, timeout=None))
    loop.run_until_complete(asyncio.sleep(0.5))
    assert not send.done()
    if master_state == "silent":
        # Connected, so close() also has a reader to stop.
        assert client.task is not None
    loop.close()
    with caplog.at_level(logging.ERROR):
        client.close()
        del send, client
        gc.collect()
    assert [(hook.err_msg, repr(hook.object)) for hook in unraisable] == []
    # send(), and its _do_send() task while connecting, are reported: the
    # loop was closed under them, which close() can't undo.
    destroyed = [
        record.getMessage()
        for record in caplog.records
        if "Task was destroyed" in record.getMessage()
    ]
    stopped = ("RequestClient._connect()", "RequestClient._stream_return()")
    assert [msg for msg in destroyed if any(name in msg for name in stopped)] == []


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

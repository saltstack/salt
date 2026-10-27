"""
The tcp ``RequestClient`` driven the way a minion's file client drives it:
through ``salt.utils.asynchronous.SyncWrapper`` (each ``send()`` an
``io_loop.run_sync`` cycle on the wrapper's private loop, the reader task
parked in between), with idle gaps, delayed replies and channel churn,
against a real mutual-TLS server.

Regression for the cancelled reader: ``RequestClient._stream_return``
swallowed its CancelledError, survived as a zombie that reconnected forever,
and the SyncWrapper drain that cancelled it never completed (these tests
hung in teardown).  Also covers the production close path
(``close_methods=["close"]``, as ``ReqChannel.factory`` builds it), which
must not raise once the reader ends cancelled.
"""

import asyncio
import threading
import time

import pytest
import tornado.iostream
import tornado.tcpserver

import salt.transport.base
import salt.transport.frame
import salt.transport.tcp
import salt.utils.asynchronous
import salt.utils.msgpack

pytest.importorskip("cryptography")

pytestmark = [
    pytest.mark.core_test,
]


@pytest.fixture
def pki(ssl_ca_cert_key, ssl_server_cert_key, ssl_client_cert_key):
    return {
        "ca": ssl_ca_cert_key[0],
        "server": ssl_server_cert_key[0],
        "server_key": ssl_server_cert_key[1],
        "client": ssl_client_cert_key[0],
        "client_key": ssl_client_cert_key[1],
    }


class _FramedTLSServer(tornado.tcpserver.TCPServer):
    """
    Stand-in for the master's request server with the same framing loop as
    ``SaltMessageServer``: mTLS, salt-framed msgpack request/reply, with
    per-request reply delays to create the fleet's ~2 s "master compiling
    the next reply" windows.
    """

    def __init__(self, ssl_ctx, delays):
        super().__init__(ssl_options=ssl_ctx)
        self.delays = delays
        self.count = 0

    async def handle_stream(self, stream, address):
        unpacker = salt.utils.msgpack.Unpacker()
        try:
            while True:
                wire_bytes = await stream.read_bytes(4096, partial=True)
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    header = framed_msg["head"]
                    n = self.count
                    self.count += 1
                    delay = self.delays.get(n, 0)
                    if delay:
                        await asyncio.sleep(delay)
                    try:
                        await stream.write(
                            salt.transport.frame.frame_msg({"ok": n}, header=header)
                        )
                    except tornado.iostream.StreamClosedError:
                        return
        except tornado.iostream.StreamClosedError:
            return


class _ServerThread:
    """The master lives in its own process on the fleet; its own loop+thread here."""

    def __init__(self, paths, delays):
        self.paths = paths
        self.delays = delays
        self.port = None
        self._ready = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        assert self._ready.wait(10)

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def main():
            ssl_ctx = salt.transport.base.ssl_context(
                {
                    "certfile": self.paths["server"],
                    "keyfile": self.paths["server_key"],
                    "ca_certs": self.paths["ca"],
                    "cert_reqs": "CERT_REQUIRED",
                },
                server_side=True,
            )
            self._stopping = asyncio.Event()
            server = _FramedTLSServer(ssl_ctx, self.delays)
            server.listen(0, address="127.0.0.1")
            self.port = server._sockets[list(server._sockets)[0]].getsockname()[1]
            self._ready.set()
            await self._stopping.wait()
            server.stop()

        try:
            self.loop.run_until_complete(main())
        finally:
            self.loop.close()

    def stop(self):
        self.loop.call_soon_threadsafe(self._stopping.set)
        self._thread.join(10)
        assert not self._thread.is_alive()


def _client_opts(paths, port):
    return {
        "transport": "tcp",
        "master": "127.0.0.1",
        "master_ip": "127.0.0.1",
        "master_port": port,
        "master_uri": f"tcp://127.0.0.1:{port}",
        "sock_dir": "/",
        "cachedir": "/",
        "tcp_reconnect_backoff": 0.05,
        "ssl": {
            "certfile": paths["client"],
            "keyfile": paths["client_key"],
            "ca_certs": paths["ca"],
            "cert_reqs": "CERT_REQUIRED",
        },
    }


def _make_client(paths, port):
    # The exact file-client construction: SyncWrapper around the real
    # transport client, driven through run_sync per send.
    return salt.utils.asynchronous.SyncWrapper(
        salt.transport.tcp.RequestClient,
        (_client_opts(paths, port),),
        {},
        loop_kwarg="io_loop",
        async_methods=["send", "connect", "close"],
    )


def _collect_errors(clients):
    errors = []
    for client in clients:
        obj = client.obj
        for mid, fut in list(getattr(obj, "send_future_map", {}).items()):
            if fut.done() and fut.exception():
                errors.append(fut.exception())
    return errors


def test_runsync_cycles_with_delayed_reply(pki):
    """
    SyncWrapper run_sync cycles with idle gaps and ~2 s-delayed replies --
    the fleet highstate pattern.  Every reply must arrive on one persistent
    TLS stream and no SSLError may surface.
    """
    # Reply #5 and #14 take ~2 s to produce, like the master's pillar/file
    # compile; the client idles ~2 s before each of them, like the state
    # code between file fetches.
    delays = {5: 2.0, 14: 2.0}
    server = _ServerThread(pki, delays)
    server.start()
    try:
        client = _make_client(pki, server.port)
        try:
            for i in range(25):
                ret = client.send({"cmd": "fetch", "i": i}, timeout=30)
                assert ret == {"ok": i}, (i, ret)
                if i in (4, 13):
                    # Fleet idle: state execution between file fetches; the
                    # SyncWrapper's loop is stopped, the reader is parked.
                    time.sleep(2.0)
            assert not _collect_errors([client])
        finally:
            client.close()
    finally:
        server.stop()


def test_channel_churn_with_delayed_reply(pki):
    """
    Fleet channel-churn variant: the forked child's file channel is dropped
    and rebuilt between fetches (short-lived connections, ~100 ms apart in
    the fleet strace), with idle gaps and a delayed reply landing on the
    connection that follows.  All replies must arrive with no SSLError.
    """
    delays = {12: 2.0}
    server = _ServerThread(pki, delays)
    server.start()
    try:
        clients = []
        try:
            for i in range(20):
                # A fresh channel per fetch, like the fleet; the previous
                # ones are neither used nor closed immediately (GC timing).
                client = _make_client(pki, server.port)
                clients.append(client)
                ret = client.send({"cmd": "fetch", "i": i}, timeout=30)
                assert ret == {"ok": i}, (i, ret)
                if i in (5, 11):
                    time.sleep(2.0)
            assert not _collect_errors(clients)
        finally:
            for client in clients:
                try:
                    client.close()
                except Exception:  # pylint: disable=broad-except
                    pass
    finally:
        server.stop()


def test_close_of_connected_client_through_close_methods(pki):
    """
    The production close shape: ``SyncWrapper(..., close_methods=["close"])``
    (``ReqChannel.factory``) closes a connected client from outside any
    running loop.  The reader ends cancelled; ``close()`` must swallow that
    rather than raise CancelledError out of ``SyncWrapper.close()``.
    """
    server = _ServerThread(pki, {})
    server.start()
    try:
        client = salt.utils.asynchronous.SyncWrapper(
            salt.transport.tcp.RequestClient,
            (_client_opts(pki, server.port),),
            {},
            loop_kwarg="io_loop",
            async_methods=["send", "connect"],
            close_methods=["close"],
        )
        assert client.send({"cmd": "fetch"}, timeout=30) == {"ok": 0}
        reader = client.obj.task
        assert reader is not None and not reader.done()
        client.close()
        assert reader.done()
    finally:
        server.stop()

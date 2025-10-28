"""
Asyncio-based TCP transport implementation.

This transport is experimental and coexists with the existing Tornado-based TCP
transport.  It intentionally shares the same framing logic and message handler
interfaces so it can be plugged into Salt without changing higher level code.
"""

import asyncio
import inspect
import logging
import multiprocessing
import os
import urllib.parse
from contextlib import suppress

import salt.payload
import salt.transport.base
import salt.transport.frame
import salt.utils.msgpack
from salt.exceptions import SaltException, SaltReqTimeoutError
from salt.transport.tcp import _null_callback
from salt.utils.asynchronous import AsyncLoopAdapter, get_io_loop
from salt.utils.network import ip_bracket

log = logging.getLogger(__name__)


class _SocketProxy:
    """
    Minimal proxy to provide ``getpeercert`` where the tornado IOStream exposes
    it.  The asyncio transport doesn't expose certificates directly, so we
    return ``None``.
    """

    def getpeercert(self):
        return None


class AsyncStreamWrapper:
    """
    Provide a tornado-like interface for Salt's message handlers while using an
    asyncio ``StreamWriter`` underneath.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        loop: AsyncLoopAdapter,
    ):
        self.reader = reader
        self.writer = writer
        self.loop = loop
        self.socket = _SocketProxy()

    def write(self, data: bytes):
        async def _do_write():
            self.writer.write(data)
            await self.writer.drain()

        # Mirror tornado's behaviour of returning a Future while still
        # progressing even if the caller doesn't await it.
        return self.loop.create_task(_do_write())

    def close(self):
        self.writer.close()
        return self.loop.create_task(self.writer.wait_closed())


class RequestClient(salt.transport.base.RequestClient):
    """
    Asyncio TCP request client.
    """

    ttype = "tcpv2"
    async_methods = [
        "connect",
        "send",
        "close_async",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, opts, io_loop=None, **kwargs):
        super().__init__(opts, io_loop, **kwargs)
        self.opts = opts
        self.loop_adapter = get_io_loop(io_loop)
        self.path = kwargs.get("path")
        self.connect_callback = kwargs.get("connect_callback", _null_callback)
        self.disconnect_callback = kwargs.get("disconnect_callback", _null_callback)
        parsed = urllib.parse.urlparse(self.opts["master_uri"])
        host, port = parsed.netloc.rsplit(":", 1)
        self.host = host
        self.port = int(port)
        self.reader = None
        self.writer = None
        self._unpacker = salt.utils.msgpack.Unpacker()
        self._lock = asyncio.Lock()

    async def connect(
        self, timeout=None
    ):  # pylint: disable=arguments-differ,invalid-overridden-method
        await self._ensure_connection(timeout=timeout)

    async def send(self, load, timeout=60):
        async with self._lock:
            await self._ensure_connection()
            payload = salt.transport.frame.frame_msg(load)
            self.writer.write(payload)
            await self.writer.drain()
            try:
                response = await asyncio.wait_for(self._read_msg(), timeout)
            except asyncio.TimeoutError as exc:
                raise SaltReqTimeoutError("Message timed out") from exc
            return response

    async def close_async(self):
        if self.writer is not None:
            self.writer.close()
            with suppress(asyncio.CancelledError):
                await self.writer.wait_closed()
        self.reader = None
        self.writer = None
        if self.disconnect_callback:
            result = self.disconnect_callback()
            if inspect.isawaitable(result):
                await result

    def close(self):
        loop = getattr(self.loop_adapter, "asyncio_loop", None)
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if loop is not None and running_loop is loop and loop.is_running():
            loop.create_task(self.close_async())
            return

        adapter = self.loop_adapter
        if adapter is not None:
            try:
                adapter.run_sync(self.close_async)
                return
            except RuntimeError:
                pass

        if loop is not None:
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(self.close_async(), loop)
                try:
                    future.result()
                except (asyncio.CancelledError, RuntimeError):
                    pass
                return
            loop.run_until_complete(self.close_async())
            return

        asyncio.run(self.close_async())

    async def _ensure_connection(self, timeout=None):
        if self.writer is not None and not self.writer.is_closing():
            return

        if self.path:
            connect_coro = asyncio.open_unix_connection(self.path)
        else:
            host = ip_bracket(self.host, strip=True)
            connect_coro = asyncio.open_connection(host, self.port)

        if timeout is not None:
            self.reader, self.writer = await asyncio.wait_for(connect_coro, timeout)
        else:
            self.reader, self.writer = await connect_coro

        self._unpacker = salt.utils.msgpack.Unpacker()
        if self.connect_callback:
            result = self.connect_callback(True)
            if inspect.isawaitable(result):
                await result

    async def _read_msg(self):
        while True:
            chunk = await self.reader.read(4096)
            if not chunk:
                raise SaltException("Connection closed while waiting for reply")
            self._unpacker.feed(chunk)
            for msg in self._unpacker:
                msg = salt.transport.frame.decode_embedded_strs(msg)
                if isinstance(msg, dict) and "body" in msg:
                    return msg["body"]
                return msg


class RequestServer(salt.transport.base.DaemonizedRequestServer):
    """Asyncio TCP request/reply server mirroring the tornado implementation."""

    ttype = "tcpv2"
    backlog = 5
    async_methods = [
        "close",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, opts):
        self.opts = opts
        self.loop_adapter = None
        self.io_loop = None
        self._server = None
        self._closing = False
        self.message_handler = None

    async def publisher(
        self,
        publish_payload,
        presence_callback=None,
        remove_presence_callback=None,
        io_loop=None,
    ):
        raise NotImplementedError("tcpv2 PublishServer.publisher is not implemented")

    def connect(self, timeout=None):
        raise NotImplementedError("tcpv2 PublishServer.connect is not implemented")

    def pre_fork(self, process_manager):  # pylint: disable=unused-argument
        """No special pre-fork setup required for the asyncio server."""
        return None

    def close(self):
        self._closing = True
        if self._server is not None and self.io_loop is not None:
            self._server.close()
            self.io_loop.create_task(self._server.wait_closed())
            self._server = None

    def post_fork(self, message_handler, io_loop):
        self.message_handler = message_handler
        self.loop_adapter = get_io_loop(io_loop)
        self.io_loop = self.loop_adapter

        async def start_server():
            host = self.opts["interface"]
            port = int(self.opts["ret_port"])
            self._server = await asyncio.start_server(
                self._handle_client,
                host,
                port,
                reuse_port=self.opts.get("reuse_port", False),
                backlog=self.backlog,
            )

        loop = self.io_loop.asyncio_loop
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(start_server(), loop)
            future.result()
        else:
            self.io_loop.run_sync(start_server)

    async def _handle_client(self, reader, writer, is_worker=False):
        stream = AsyncStreamWrapper(reader, writer, self.io_loop)
        unpacker = salt.utils.msgpack.Unpacker()
        peername = writer.get_extra_info("peername")
        log.debug("TCP async client connected from %s", peername)
        try:
            while not self._closing:
                try:
                    data = await reader.read(4096)
                except ConnectionResetError:
                    break
                if not data:
                    break
                unpacker.feed(data)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    header = framed_msg.get("head", {})
                    body = framed_msg.get("body")
                    log.debug("tcpv2 request server handling message header=%s", header)
                    await self.handle_message(stream, body, header)
        except Exception:  # pylint: disable=broad-except
            log.exception("Unhandled exception in tcpv2 client handler")
        finally:
            with suppress(Exception):
                await stream.close()
            log.debug("TCP async client disconnected from %s", peername)

    async def handle_message(self, stream, payload, header=None):
        payload = self.decode_payload(payload)
        reply = await self.message_handler(payload)
        if reply is not None:
            framed = salt.transport.frame.frame_msg(reply, header=header)
            await stream.write(framed)

    def decode_payload(self, payload):
        return payload


class PublishClient(salt.transport.base.PublishClient):
    ttype = "tcpv2"
    async_methods = [
        "connect",
        "send",
        "close_async",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, opts, io_loop, **kwargs):  # pylint: disable=W0231
        super().__init__(opts, io_loop, **kwargs)
        self.opts = opts
        self.loop_adapter = get_io_loop(io_loop)
        self.reader = None
        self.writer = None
        self.unpacker = salt.utils.msgpack.Unpacker()
        self.host = kwargs.get("host")
        self.port = kwargs.get("port")
        self.path = kwargs.get("path")
        self.ssl = kwargs.get("ssl")
        self.source_ip = kwargs.get("source_ip") or self.opts.get("source_ip")
        self.source_port = kwargs.get("source_port") or self.opts.get(
            "source_publish_port"
        )
        self._closing = False
        self.on_recv_task = None
        self.connect_callback = kwargs.get("connect_callback", _null_callback)
        self.disconnect_callback = kwargs.get("disconnect_callback", _null_callback)

    async def _open_connection(self, host, port):
        return await asyncio.open_connection(host, port)

    async def _ensure_connection(self, timeout=None):
        if self.writer is not None and not self.writer.is_closing():
            return

        if self.path:
            connect_coro = asyncio.open_unix_connection(self.path)
        else:
            host = self.host or "127.0.0.1"
            connect_coro = self._open_connection(host, self.port)

        if timeout is not None:
            self.reader, self.writer = await asyncio.wait_for(connect_coro, timeout)
        else:
            self.reader, self.writer = await connect_coro

        self.unpacker = salt.utils.msgpack.Unpacker()
        if self.connect_callback:
            result = self.connect_callback(True)
            if inspect.isawaitable(result):
                await result

    async def connect(  # pylint: disable=arguments-differ,invalid-overridden-method
        self,
        port=None,
        connect_callback=None,
        disconnect_callback=None,
        timeout=None,
    ):
        self._closing = False
        if port is not None:
            self.port = port
        if connect_callback is not None:
            self.connect_callback = connect_callback
        if disconnect_callback is not None:
            self.disconnect_callback = disconnect_callback

        await self._ensure_connection(timeout=timeout)

    async def connect_uri(self, uri, connect_callback=None, disconnect_callback=None):
        parsed = urllib.parse.urlparse(uri)
        host, port = parsed.netloc.rsplit(":", 1)
        await self.connect(
            port=int(port),
            connect_callback=connect_callback,
            disconnect_callback=disconnect_callback,
        )

    async def recv(self, timeout=None):
        if not self.reader:
            return None

        async def _recv_once():
            while True:
                data = await self.reader.read(4096)
                if not data:
                    if self.disconnect_callback:
                        result = self.disconnect_callback()
                        if inspect.isawaitable(result):
                            await result
                    self.close()
                    return None
                self.unpacker.feed(data)
                for message in self.unpacker:
                    return self._decode_messages(message)

        if timeout is not None:
            try:
                return await asyncio.wait_for(_recv_once(), timeout)
            except asyncio.TimeoutError:
                return None
        return await _recv_once()

    async def on_recv_handler(self, callback):
        while self.reader is None:
            await asyncio.sleep(0.05)
        pending = set()
        try:
            while not self._closing:
                msg = await self.recv()
                if msg is None:
                    break
                task = asyncio.create_task(callback(msg))
                pending.add(task)
                task.add_done_callback(pending.discard)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            pass
        finally:
            for task in pending:
                task.cancel()

    def on_recv(self, callback):
        if self.on_recv_task:
            self.on_recv_task.cancel()
        if callback is None:
            self.on_recv_task = None
        else:
            self.on_recv_task = self.loop_adapter.create_task(
                self.on_recv_handler(callback)
            )

    def _decode_messages(self, message):
        decoded_message = salt.transport.frame.decode_embedded_strs(message)
        if isinstance(decoded_message, dict):
            body = decoded_message.get("body", decoded_message)
            if isinstance(body, dict):
                body = salt.transport.frame.decode_embedded_strs(body)
        else:
            body = decoded_message
            if isinstance(body, dict) and "body" in body:
                body = body["body"]
        if isinstance(body, (bytes, bytearray)):
            try:
                body = salt.payload.loads(body)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "tcpv2 publish client failed to decode payload from bytes"
                )
        else:
            log.debug(
                "tcpv2 publish client received non-bytes body type=%s", type(body)
            )
        if isinstance(body, dict):
            log.debug("tcpv2 publish client decoded dict keys=%s", list(body.keys()))
        else:
            snippet = body[:60] if isinstance(body, (bytes, bytearray)) else body
            log.debug(
                "tcpv2 publish client decoded payload type=%s value=%r",
                type(body),
                snippet,
            )
        return body

    async def send_id(self, tok, force_auth):
        message = {"enc": "clear", "load": {"id": self.opts["id"], "tok": tok}}
        payload = salt.transport.frame.frame_msg(message)
        await self.send(payload)
        return True

    async def send(self, payload):
        if not self.writer:
            raise SaltException("Publish client is not connected")
        self.writer.write(payload)
        await self.writer.drain()

    async def close_async(self):
        self._closing = True
        if self.on_recv_task:
            self.on_recv_task.cancel()
            self.on_recv_task = None
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader = None
        self.writer = None
        if self.disconnect_callback:
            result = self.disconnect_callback()
            if inspect.isawaitable(result):
                await result

    def close(self):
        if self.loop_adapter is None:
            asyncio.run(self.close_async())
            return
        try:
            self.loop_adapter.run_sync(self.close_async)
        except RuntimeError:
            self.loop_adapter.create_task(self.close_async())


class PublishServer(salt.transport.base.DaemonizedPublishServer):
    ttype = "tcpv2"
    backlog = 128
    async_methods = [
        "publisher",
        "publish_payload",
        "publish",
    ]
    close_methods = [
        "close",
    ]

    def __init__(
        self,
        opts,
        pub_host=None,
        pub_port=None,
        pub_path=None,
        pull_host=None,
        pull_port=None,
        pull_path=None,
        pull_path_perms=0o600,
        pub_path_perms=0o600,
        started=None,
    ):
        self.opts = opts
        log.debug(
            "Initializing tcpv2 PublishServer for transport=%s",
            opts.get("transport"),
        )
        self.pub_host = pub_host
        self.pub_port = pub_port
        self.pub_path = pub_path
        self.pull_host = pull_host
        self.pull_port = pull_port
        self.pull_path = pull_path
        self.pull_path_perms = pull_path_perms
        self.pub_path_perms = pub_path_perms
        if started is None:
            self.started = multiprocessing.Event()
        else:
            self.started = started
        self.io_loop = None
        self.loop_adapter = None
        self._server = None
        self.clients = set()
        self._reader_tasks = set()
        self.presence_callback = None
        self.remove_presence_callback = None
        self._pull_server = None
        self._pull_tasks = set()

    @classmethod
    def support_ssl(cls):
        return False

    def topic_support(self):
        return False

    def pre_fork(self, process_manager):  # pylint: disable=unused-argument
        """No pre-fork setup required for the asyncio implementation."""
        return None

    def publish_daemon(
        self,
        publish_payload,
        presence_callback=None,
        remove_presence_callback=None,
    ):
        self.loop_adapter = get_io_loop()
        self.io_loop = self.loop_adapter
        self.presence_callback = presence_callback
        self.remove_presence_callback = remove_presence_callback

        async def start_server():
            await self._ensure_server(publish_payload)

        self.io_loop.create_task(start_server())
        try:
            self.io_loop.start()
        finally:
            self.close()

    async def publisher(
        self,
        publish_payload,
        presence_callback=None,
        remove_presence_callback=None,
        io_loop=None,
    ):
        self.presence_callback = presence_callback
        self.remove_presence_callback = remove_presence_callback
        self.loop_adapter = get_io_loop(io_loop)
        self.io_loop = self.loop_adapter
        await self._ensure_server(publish_payload)

    async def _ensure_server(self, publish_payload):
        if self._server is not None:
            return
        if self.pub_path:
            if os.path.exists(self.pub_path):
                os.unlink(self.pub_path)
            self._server = await asyncio.start_unix_server(
                lambda r, w: self._accept_client(r, w, publish_payload),
                path=self.pub_path,
            )
            os.chmod(self.pub_path, self.pub_path_perms)
            log.info("tcpv2 publish server listening on unix %s", self.pub_path)
        else:
            host = self.pub_host or "127.0.0.1"
            port = int(self.pub_port or self.opts.get("publish_port", 4506))
            self._server = await asyncio.start_server(
                lambda r, w: self._accept_client(r, w, publish_payload),
                host,
                port,
            )
            log.info("tcpv2 publish server listening on %s:%s", host, port)
        await self._ensure_pull_server(publish_payload)
        if self.started is not None:
            self.started.set()

    async def _ensure_pull_server(self, publish_payload):
        if self._pull_server is not None:
            return

        async def _handle(reader, writer):
            addr = writer.get_extra_info("peername")
            log.info("tcpv2 publish pull connection from %s", addr)
            unpacker = salt.utils.msgpack.Unpacker()
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    unpacker.feed(data)
                    for message in unpacker:
                        message = salt.transport.frame.decode_embedded_strs(message)
                        body = message.get("body")
                        header = message.get("head", {}) or {}
                        topic_list = header.get("topic_lst")
                        try:
                            if topic_list:
                                await publish_payload(body, topic_list)
                            else:
                                await publish_payload(body)
                        except Exception:  # pylint: disable=broad-except
                            log.exception(
                                "tcpv2 publish pull handler failed to publish payload"
                            )
                            raise
            finally:
                writer.close()
                with suppress(Exception):
                    await writer.wait_closed()
                log.info("tcpv2 publish pull disconnected from %s", addr)

        if self.pull_path:
            if os.path.exists(self.pull_path):
                os.unlink(self.pull_path)
            self._pull_server = await asyncio.start_unix_server(
                _handle, path=self.pull_path
            )
            os.chmod(self.pull_path, self.pull_path_perms)
            log.info("tcpv2 pull server listening on unix %s", self.pull_path)
        else:
            host = self.pull_host or "127.0.0.1"
            port = int(self.pull_port or self.opts.get("tcp_master_publish_pull", 4514))
            self._pull_server = await asyncio.start_server(_handle, host, port)
            log.info("tcpv2 pull server listening on %s:%s", host, port)

    async def _accept_client(self, reader, writer, publish_payload):
        addr = writer.get_extra_info("peername")
        subscriber = _AsyncSubscriber(reader, writer, addr)
        self.clients.add(subscriber)
        log.debug("tcpv2 publish client connected from %s", addr)
        task = asyncio.create_task(
            self._client_reader(subscriber, publish_payload),
            name=f"tcpv2_pub_{addr}",
        )
        self._reader_tasks.add(task)
        task.add_done_callback(self._reader_tasks.discard)

    async def _client_reader(self, subscriber, publish_payload):
        unpacker = salt.utils.msgpack.Unpacker()
        try:
            while True:
                data = await subscriber.reader.read(4096)
                if not data:
                    break
                unpacker.feed(data)
                for message in unpacker:
                    message = salt.transport.frame.decode_embedded_strs(message)
                    body = message.get("body", message)
                    if isinstance(body, dict):
                        subscriber.id_ = body.get("id", subscriber.id_)
                        if self.presence_callback is not None:
                            self.presence_callback(subscriber, body)
        except asyncio.CancelledError:  # pragma: no cover
            pass
        finally:
            self.clients.discard(subscriber)
            if self.remove_presence_callback is not None:
                self.remove_presence_callback(subscriber)
            with suppress(Exception):
                subscriber.writer.close()
                await subscriber.writer.wait_closed()
            log.debug("tcpv2 publish client disconnected from %s", subscriber.address)

    async def publish_payload(self, payload, topic_list=None):
        if not isinstance(payload, bytes):
            payload = salt.transport.frame.frame_msg(payload)
        dead = []
        targets = None
        if topic_list:
            targets = [client for client in self.clients if client.id_ in topic_list]
        for subscriber in targets or list(self.clients):
            try:
                subscriber.writer.write(payload)
                await subscriber.writer.drain()
            except Exception:  # pylint: disable=broad-except
                dead.append(subscriber)
        for subscriber in dead:
            self.clients.discard(subscriber)
            with suppress(Exception):
                subscriber.writer.close()

    async def publish(self, payload, **kwargs):
        log.info(
            "tcpv2 PublishServer.publish invoked with %d-byte payload", len(payload)
        )
        topic_list = kwargs.get("topic_list")
        header = None
        if topic_list:
            header = {"topic_lst": topic_list}
        framed = salt.transport.frame.frame_msg_ipc(
            payload, header=header, raw_body=True
        )

        if self.pull_path:
            _reader, writer = await asyncio.open_unix_connection(self.pull_path)
        else:
            host = self.pull_host or "127.0.0.1"
            port = int(self.pull_port or self.opts.get("tcp_master_publish_pull", 4514))
            _reader, writer = await asyncio.open_connection(host, port)
        writer.write(framed)
        await writer.drain()
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()

    def connect(self, timeout=None):
        if self.loop_adapter is None:
            self.loop_adapter = get_io_loop()
            self.io_loop = self.loop_adapter
        return True

    def close(self):
        async def _shutdown_server():
            if self._server is not None:
                self._server.close()
                await self._server.wait_closed()
            if self._pull_server is not None:
                self._pull_server.close()
                await self._pull_server.wait_closed()

        if self.io_loop is not None:
            self.io_loop.spawn_callback(_shutdown_server)
        for task in list(self._reader_tasks):
            task.cancel()
        for subscriber in list(self.clients):
            with suppress(Exception):
                subscriber.writer.close()
        self.clients.clear()
        if self.loop_adapter is not None:
            self.loop_adapter.stop()


class _AsyncSubscriber:
    def __init__(self, reader, writer, address):
        self.reader = reader
        self.writer = writer
        self.address = address
        self.id_ = None

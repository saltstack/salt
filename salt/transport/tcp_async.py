"""
Asyncio-based TCP transport implementation.

This transport is experimental and coexists with the existing Tornado-based TCP
transport.  It intentionally shares the same framing logic and message handler
interfaces so it can be plugged into Salt without changing higher level code.
"""

import asyncio
import logging
import urllib.parse
from contextlib import suppress

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

    ttype = "tcp_async"

    def __init__(self, opts, io_loop=None, **kwargs):
        super().__init__(opts, io_loop, **kwargs)
        self.opts = opts
        self.loop_adapter = get_io_loop(io_loop)
        parsed = urllib.parse.urlparse(self.opts["master_uri"])
        host, port = parsed.netloc.rsplit(":", 1)
        self.host = host
        self.port = int(port)
        self.reader = None
        self.writer = None
        self._unpacker = salt.utils.msgpack.Unpacker()
        self._lock = asyncio.Lock()

    def connect(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.loop_adapter.create_task(self._ensure_connection())

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

    def close(self):
        if self.writer is not None:
            self.writer.close()
            self.loop_adapter.create_task(self.writer.wait_closed())
        self.reader = None
        self.writer = None

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
            await self.connect_callback(True)

    async def _read_msg(self):
        while True:
            chunk = await self.reader.read(4096)
            if not chunk:
                raise SaltException("Connection closed while waiting for reply")
            self._unpacker.feed(chunk)
            for msg in self._unpacker:
                return salt.transport.frame.decode_embedded_strs(msg)


class RequestServer(salt.transport.base.DaemonizedRequestServer):
    """
    Asyncio TCP request server.
    """

    ttype = "tcp_async"

    def __init__(self, opts):
        self.opts = opts
        self.io_loop = None
        self._server = None
        self._closing = False
        self.message_handler = None

    def pre_fork(self, process_manager):  # pylint: disable=unused-argument
        """No special pre-fork setup required for the asyncio server."""
        return None

    def close(self):
        self._closing = True
        if self._server is not None:
            self._server.close()
            self.io_loop.create_task(self._server.wait_closed())
            self._server = None

    def post_fork(self, message_handler, io_loop):
        self.message_handler = message_handler
        self.io_loop = get_io_loop(io_loop)
        host = self.opts["interface"]
        port = int(self.opts["ret_port"])

        async def start_server():
            self._server = await asyncio.start_server(
                self._handle_client,
                host,
                port,
                reuse_port=self.opts.get("reuse_port", False),
            )

        self.io_loop.create_task(start_server())

    async def _handle_client(self, reader, writer):
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
                    reply = await self.message_handler(stream, body, header)
                    if reply is not None:
                        framed = salt.transport.frame.frame_msg(
                            reply,
                            header=header,
                        )
                        stream.write(framed)
        except Exception:  # pylint: disable=broad-except
            log.exception("Unhandled exception in tcp_async client handler")
        finally:
            with suppress(Exception):
                await stream.close()
            log.debug("TCP async client disconnected from %s", peername)


class PublishClient(salt.transport.base.PublishClient):
    ttype = "tcp_async"

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
                        self.disconnect_callback()
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
        if isinstance(message, dict):
            return message.get("body", message)
        body = salt.transport.frame.decode_embedded_strs(message)
        if isinstance(body, dict) and "body" in body:
            return body["body"]
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

    async def _async_close(self):
        self._closing = True
        if self.on_recv_task:
            self.on_recv_task.cancel()
            self.on_recv_task = None
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader = None
        self.writer = None

    def close(self):
        self.loop_adapter.spawn_callback(self._async_close)


class PublishServer(salt.transport.base.DaemonizedPublishServer):
    ttype = "tcp_async"

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
        self.pub_host = pub_host
        self.pub_port = pub_port
        self.pub_path = pub_path
        self.pull_host = pull_host
        self.pull_port = pull_port
        self.pull_path = pull_path
        self.pull_path_perms = pull_path_perms
        self.pub_path_perms = pub_path_perms
        self.started = started
        self.io_loop = None
        self.loop_adapter = None
        self._server = None
        self.clients = set()
        self._reader_tasks = set()
        self.presence_callback = None
        self.remove_presence_callback = None

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
            if self.pub_path:
                self._server = await asyncio.start_unix_server(
                    lambda r, w: self._accept_client(r, w, publish_payload),
                    path=self.pub_path,
                )
            else:
                host = self.pub_host or "127.0.0.1"
                port = int(self.pub_port or self.opts.get("publish_port", 4506))

                self._server = await asyncio.start_server(
                    lambda r, w: self._accept_client(r, w, publish_payload),
                    host,
                    port,
                )
            if self.started is not None:
                self.started.set()

        self.io_loop.create_task(start_server())
        try:
            self.io_loop.start()
        finally:
            self.close()

    async def _accept_client(self, reader, writer, publish_payload):
        addr = writer.get_extra_info("peername")
        subscriber = _AsyncSubscriber(reader, writer, addr)
        self.clients.add(subscriber)
        log.debug("tcp_async publish client connected from %s", addr)
        task = asyncio.create_task(
            self._client_reader(subscriber, publish_payload),
            name=f"tcp_async_pub_{addr}",
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
            log.debug(
                "tcp_async publish client disconnected from %s", subscriber.address
            )

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

    def publish(self, payload, **kwargs):
        topic_list = kwargs.get("topic_list")
        return self.loop_adapter.create_task(
            self.publish_payload(payload, topic_list=topic_list)
        )

    def close(self):
        async def _shutdown_server():
            if self._server is not None:
                self._server.close()
                await self._server.wait_closed()

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

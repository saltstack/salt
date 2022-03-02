import asyncio
import logging
import time

import salt.transport.frame
import salt.utils.msgpack

log = logging.getLogger(__name__)


class IPCServer:

    async_methods = ["start", "handle_stream"]
    close_methods = [
        "close",
    ]

    def __init__(self, socket_path, io_loop=None, payload_handler=None):
        self.socket_path = socket_path
        self.io_loop = io_loop or asyncio.get_event_loop()
        self.payload_handler = payload_handler
        self.server = None
        self.connection_info = None

    def close(self):
        if self.server:
            self.server.close()
        self.sever = None

    async def start(self):
        if isinstance(self.socket_path, int):
            host = "127.0.0.1"
            self.connection_info = "{}:{}".format(host, self.socket_path)
            log.debug("%r listen on %s", self, self.connection_info)
            self.server = await asyncio.start_server(
                self.handle_stream,
                host=host,
                port=self.socket_path,
                reuse_address=True,
            )
        else:
            log.debug("%r listen on %s", self, self.connection_info)
            self.connection_info = self.socket_path
            self.server = await asyncio.start_unix_server(
                self.handle_stream, path=self.socket_path
            )

    async def handle_stream(self, reader, writer):
        socket = writer.get_extra_info("socket")
        if socket is not None:
            log.debug("%r handle connection from %r", self, socket)
        else:
            log.debug("%r Socket is %r", self, socket)

        def write_callback(header):
            async def callback(msg, header=None):
                log.debug("IPC server write to stream: %r", msg)
                if header and header.get("mid"):
                    pack = salt.transport.frame.frame_msg_ipc(
                        msg,
                        header={"mid": header["mid"]},
                        raw_body=True,
                    )
                else:
                    pack = salt.transport.frame.frame_msg_ipc(
                        msg,
                        raw_body=True,
                    )
                writer.write(pack)
                await writer.drain()

            return callback

        # msgpack deprecated `encoding` starting with version 0.5.2
        if salt.utils.msgpack.version >= (0, 5, 2):
            # Under Py2 we still want raw to be set to True
            msgpack_kwargs = {"raw": False}
        else:
            msgpack_kwargs = {"encoding": "utf-8"}
        unpacker = salt.utils.msgpack.Unpacker(**msgpack_kwargs)
        while True:
            try:
                try:
                    wire_bytes = await reader.read(1024)
                    if not wire_bytes:
                        log.debug("%s nothing more to read", self.__class__.__name__)
                        break
                except asyncio.IncompleteReadError as e:
                    if len(e.partial) > 0:
                        wire_bytes = e.partial
                        log.debug(
                            "%s process message %r", self.__class__.__name__, wire_bytes
                        )
                        await self.process_message(unpacker, wire_bytes, write_callback)
                        break
                    else:
                        log.debug("%s reader reached EOF", self)
                        break
                await self.process_message(unpacker, wire_bytes, write_callback)
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Unhandled exception %s", exc, exc_info=True)
                break

    async def process_message(self, unpacker, wire_bytes, write_callback):
        unpacker.feed(wire_bytes)
        for framed_msg in unpacker:
            head = framed_msg.get("head", None)
            body = framed_msg["body"]
            if asyncio.iscoroutinefunction(self.payload_handler):
                await self.payload_handler(
                    body,
                    write_callback(head),
                )
            else:
                # XXX Spawn callback or enforce coroutine here?
                self.payload_handler(
                    body,
                    write_callback(head),
                )


class IPCClient:
    def __init__(self, socket_path, io_loop=None):
        self.socket_path = socket_path
        self.io_loop = io_loop or asyncio.get_event_loop()
        self.reader = None
        self.writer = None
        self.connection_info = None

    def connected(self):
        if self.reader and self.writer:
            return True

    async def _open_connection(self):
        if isinstance(self.socket_path, int):
            host = "127.0.0.1"
            self.connection_info = "{}:{}".format(host, self.socket_path)
            log.debug("%r connecting to %s", self, self.connection_info)
            self.reader, self.writer = await asyncio.open_connection(
                host="127.0.0.1", port=self.socket_path
            )
        else:
            self.connection_info = self.socket_path
            log.debug("%r connecting to %s", self, self.socket_path)
            self.reader, self.writer = await asyncio.open_unix_connection(
                path=self.socket_path
            )

    async def connect(self, callback=None, timeout=None):
        start = time.time()
        while True:
            try:
                await self._open_connection()
                break
            except (
                ConnectionRefusedError,
                FileNotFoundError,
            ):
                if timeout is None or time.time() - start > timeout:
                    raise
                await asyncio.sleep(1)
        if callback:
            callback(self)

    def close(self):
        # Only the writer has a close method
        if self.writer:
            self.writer.close()
            self.writer = None
            self.reader = None


class IPCMessageClient(IPCClient):
    async_methods = [
        "send",
        "connect",
    ]
    close_methods = [
        "close",
    ]

    # FIXME timeout unimplemented
    # FIXME tries unimplemented
    async def send(self, msg, timeout=None, tries=None):
        """
        Send a message to an IPC socket

        If the socket is not currently connected, a connection will be established.

        :param dict msg: The message to be sent
        :param int timeout: Timeout when sending message (Currently unimplemented)
        """
        if not self.connected():
            await self.connect()
        log.debug(
            "%s to %s send %r", self.__class__.__name__, self.connection_info, msg
        )
        pack = salt.transport.frame.frame_msg_ipc(msg, raw_body=True)
        self.writer.write(pack)
        await self.writer.drain()


class IPCMessageServer(IPCServer):
    """
    Salt IPC message server

    Creates a message server which can create and bind to a socket on a given
    path and then respond to messages asynchronously.

    See IPCMessageClient() for an example of sending messages to an IPCMessageServer instance
    """


class IPCMessagePublisher:
    def __init__(self, opts, socket_path, io_loop=None):
        self.socket_path = socket_path
        self.io_loop = io_loop or asyncio.get_event_loop()
        self.server = None
        self.streams = set()

    async def start(self):
        if isinstance(self.socket_path, int):
            host = "127.0.0.1"
            log.info(
                "%s listen on %s:%s", self.__class__.__name__, host, self.socket_path
            )
            self.server = await asyncio.start_server(
                self.handle_connection,
                host="127.0.0.1",
                port=self.socket_path,
                reuse_address=True,
            )
        else:
            log.info("%s listen on %s", self.__class__.__name__, self.socket_path)
            self.server = await asyncio.start_unix_server(
                self.handle_connection,
                path=self.socket_path,
            )

    async def handle_connection(self, reader, writer):
        socket = writer.get_extra_info("socket")
        if socket is not None:
            log.debug("%s handle connection from %r", self.__class__.__name__, socket)
        else:
            log.debug("%s Socket is %r", self.__class__.__name__, socket)
        self.streams.add((reader, writer))

    async def _write(self, writer, reader, pack):
        try:
            log.debug("%s write %r", self.__class__.__name__, pack)
            writer.write(pack)
            await writer.drain()
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Exception occurred while handling stream: %s", exc)
            self.streams.remove((reader, writer))

    def publish(self, msg):
        log.debug("%s publish %r", self.__class__.__name__, msg)
        pack = salt.transport.frame.frame_msg_ipc(msg, raw_body=True)
        for reader, writer in list(self.streams):
            self.io_loop.create_task(self._write(writer, reader, pack))

    def close(self):
        if self.server:
            self.server.close()


class IPCMessageSubscriber(IPCClient):
    async_methods = [
        "read",
        "connect",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, socket_path, io_loop=None):
        super().__init__(socket_path, io_loop=io_loop)
        self._saved_data = []
        self._read_lock = asyncio.Lock()
        if salt.utils.msgpack.version >= (0, 5, 2):
            # Under Py2 we still want raw to be set to True
            msgpack_kwargs = {"raw": False}
        else:
            msgpack_kwargs = {"encoding": "utf-8"}
        self.unpacker = salt.utils.msgpack.Unpacker(**msgpack_kwargs)

    async def _read(self, timeout, callback=None):
        try:
            await asyncio.wait_for(self._read_lock.acquire(), timeout=0.0000001)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Unhandled exception %r", exc)

        exc_to_raise = None
        ret = None
        try:
            while True:
                ret = None
                wire_bytes = None
                stop = False
                try:
                    # Backwards compat
                    if timeout == 0:
                        timeout = 0.3
                    if timeout is None:
                        wire_bytes = await self.reader.read(1024)
                    else:
                        wire_bytes = await asyncio.wait_for(
                            self.reader.read(1024), timeout=timeout
                        )
                    if not wire_bytes:
                        log.debug("%s Nothing more to read", self.__class__.__name__)
                        break
                except ConnectionResetError as e:
                    # XXX This only happens on windows?
                    log.error("Connection reset by peer")
                    break
                except asyncio.IncompleteReadError as e:
                    log.error("Incomplete read")
                    stop = True
                    if len(e.partial) > 0:
                        wire_bytes = e.partial
                if wire_bytes is not None:
                    self.unpacker.feed(wire_bytes)
                    first_sync_msg = True
                    for framed_msg in self.unpacker:
                        if callback:
                            # Try to run the callback as a normal function
                            # first, if it fails, run it as a coroutine.
                            try:
                                self.io_loop.call_soon(callback, framed_msg["body"])
                            except TypeError:
                                self.io_loop.create_task(callback(framed_msg["body"]))
                            stop = True
                        elif first_sync_msg:
                            ret = framed_msg["body"]
                            first_sync_msg = False
                        else:
                            self._saved_data.append(framed_msg["body"])
                    if not first_sync_msg or stop:
                        # We read at least one piece of data and we're on sync run
                        break
        except asyncio.TimeoutError:
            ret = None
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Exception occurred in Subscriber while handling stream: %s", exc)
            self._read_stream_future = None
            exc_to_raise = exc

        self._read_lock.release()

        if exc_to_raise is not None:
            raise exc_to_raise  # pylint: disable=E0702
        return ret

    async def read(self, timeout=30):
        """
        Asynchronously read messages and invoke a callback when they are ready.
        :param callback: A callback with the received data
        """
        if self._saved_data:
            res = self._saved_data.pop(0)
            return res
        if not self.connected():
            await self.connect()
        res = await self._read(timeout)
        return res

    async def read_async(self, callback):
        if self._saved_data:
            res = self._saved_data.pop(0)
            callback(res)
        if not self.connected():
            log.error("NOT YET CONNECTED")
            await self.connect()
        log.error("NOW %r", self.connected())
        await self._read(None, callback)

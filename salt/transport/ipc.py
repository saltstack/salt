"""
Define the types used by the Salt IPC system
"""

import asyncio
import logging
import socket
import threading

import tornado.gen
import tornado.ioloop
import tornado.iostream
import tornado.netutil

import salt.payload
import salt.transport.frame
import salt.utils.asynchronous
import salt.utils.msgpack
from salt.utils.versions import warn_until

log = logging.getLogger(__name__)


class IPCServer:
    """
    A base class for Salt IPC servers
    """

    def __init__(self, socket_path, io_loop=None, payload_handler=None):
        """
        Create a new Tornado IPC server

        :param str/int socket_path: Path on the filesystem for the
                                    socket to bind to. This socket does
                                    not need to exist prior to calling
                                    this method, but parent directories
                                    should.
                                    It may also be of type 'int', in
                                    which case it is used as the port
                                    for a tcp localhost connection.
        :param IOLoop io_loop: A Tornado ioloop to handle scheduling
        :param function payload_handler: A function to handle received payloads
        """
        self.socket_path = socket_path
        self.payload_handler = payload_handler
        self.io_loop = io_loop or salt.utils.asynchronous.get_ioloop()
        self.tasks = set()
        self._closing = False

    def start(self):
        """
        Perform the work necessary to start up a Tornado IPC server

        Blocks until socket is established
        """
        # Start up the ioloop
        if isinstance(self.socket_path, int):
            log.trace("IPCServer: binding to port: %s", self.socket_path)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setblocking(0)
            self.sock.bind(("127.0.0.1", self.socket_path))
            self.sock.listen(128)
        else:
            log.trace("IPCServer: binding to socket: %s", self.socket_path)
            self.sock = tornado.netutil.bind_unix_socket(self.socket_path)

        tornado.netutil.add_accept_handler(
            self.sock,
            self.handle_connection,
        )

    async def handle_stream(self, stream):
        """
        Override this to handle the streams as they arrive

        :param IOStream stream: An IOStream for processing

        See https://tornado.readthedocs.io/en/latest/iostream.html#tornado.iostream.IOStream
        for additional details.
        """
        unpacker = salt.utils.msgpack.Unpacker(raw=False)
        while not self._closing and not stream.closed():
            try:
                wire_bytes = await stream.read_bytes(4096, partial=True)
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    body = framed_msg["body"]
                    loop = salt.utils.asynchronous.aioloop(self.io_loop)
                    task = loop.create_task(
                        self.payload_handler(
                            body,
                            self.write_callback(stream, framed_msg["head"]),
                        )
                    )
                    self.tasks.add(task)
                    task.add_done_callback(self.tasks.discard)
            except (tornado.iostream.StreamClosedError, asyncio.CancelledError):
                break
            except Exception as exc:  # pylint: disable=broad-except
                log.error("IPCServer: Error while reading from stream: %s", exc)
                break
        stream.close()

    def write_callback(self, stream, header):
        if header.get("mid"):

            async def return_message(msg):
                pack = salt.transport.frame.frame_msg_ipc(
                    msg,
                    header={"mid": header["mid"]},
                    raw_body=True,
                )
                await stream.write(pack)

            return return_message
        else:

            async def _null(msg):
                return None

            return _null

    def handle_connection(self, connection, address):
        log.trace("IPCServer: Handling connection to address: %s", address)
        try:
            with salt.utils.asynchronous.current_ioloop(self.io_loop):
                stream = tornado.iostream.IOStream(
                    connection,
                )
            loop = salt.utils.asynchronous.aioloop(self.io_loop)
            task = loop.create_task(self.handle_stream(stream))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("IPC streaming error: %s", exc)

    def close(self):
        """
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitly, to prevent
        leaks.
        """
        if self._closing:
            return
        self._closing = True
        if hasattr(self, "sock") and hasattr(self.sock, "close"):
            self.sock.close()
        for task in list(self.tasks):
            if not task.done():
                task.cancel()
        self.tasks.clear()

    # pylint: disable=W1701
    def __del__(self):
        try:
            self.close()
        except Exception:  # pylint: disable=broad-except
            pass

    # pylint: enable=W1701

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class IPCMessageServer(IPCServer):
    """
    A Salt IPC server that can send and receive messagespack messages
    """

    def __init__(self, socket_path, io_loop=None, payload_handler=None):
        warn_until(
            3009,
            "salt.transport.ipc.IPCMessageServer is deprecated. Please use salt.transport.publish_server instead.",
        )
        super().__init__(socket_path, io_loop=io_loop, payload_handler=payload_handler)


class IPCClient:
    """
    A base class for Salt IPC clients
    """

    def __init__(self, socket_path, io_loop=None):
        """
        Create a new IPC client

        IPC clients cannot bind to ports, but must connect to
        existing IPC servers. Clients can then send messages
        to the server.

        """
        self.io_loop = io_loop or salt.utils.asynchronous.get_ioloop()
        self.socket_path = socket_path
        self._closing = False
        self._connecting_future = None
        self.stream = None

    def connected(self):
        return self.stream is not None and not self.stream.closed()

    async def connect(self, timeout=None):
        """
        Connect to a running IPCServer
        """
        if self.connected():
            return True
        if self._connecting_future and not self._connecting_future.done():
            return await self._connecting_future

        if isinstance(self.socket_path, int):
            sock_type = socket.AF_INET
            sock_addr = ("127.0.0.1", self.socket_path)
        else:
            sock_type = socket.AF_UNIX
            sock_addr = self.socket_path

        self._connecting_future = asyncio.Future()
        try:
            self.stream = tornado.iostream.IOStream(
                socket.socket(sock_type, socket.SOCK_STREAM)
            )
            await self.stream.connect(sock_addr)
            self._connecting_future.set_result(True)
        except Exception as exc:
            self._connecting_future.set_exception(exc)
            self.stream = None
            raise
        return await self._connecting_future

    def close(self):
        """
        Routines to handle any cleanup before the instance shuts down.
        Sockets and filehandles should be closed explicitly, to prevent
        leaks.
        """
        if self._closing:
            return
        self._closing = True
        if self.stream:
            self.stream.close()
            self.stream = None

    # pylint: disable=W1701
    def __del__(self):
        try:
            self.close()
        except Exception:  # pylint: disable=broad-except
            pass

    # pylint: enable=W1701

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class IPCMessagePublisher(IPCServer):
    """
    A Salt IPC server that can send and receive messagespack messages
    """

    def __init__(self, opts, socket_path, io_loop=None):
        warn_until(
            3009,
            "salt.transport.ipc.IPCMessagePublisher is deprecated. Please use salt.transport.publish_server instead.",
        )
        super().__init__(socket_path, io_loop=io_loop)
        self.opts = opts
        self.streams = set()
        self._write_semaphore = threading.Semaphore(value=100)

    def handle_connection(self, connection, address):
        log.trace("IPCMessagePublisher: Handling connection to address: %s", address)
        try:
            kwargs = {}
            write_buffer = self.opts.get("ipc_write_buffer", 0)
            if write_buffer <= 0:
                write_buffer = 100 * 1024 * 1024
            kwargs["max_write_buffer_size"] = write_buffer

            with salt.utils.asynchronous.current_ioloop(self.io_loop):
                stream = tornado.iostream.IOStream(connection, **kwargs)
            self.streams.add(stream)

            def discard_after_closed():
                self.streams.discard(stream)

            stream.set_close_callback(discard_after_closed)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("IPCMessagePublisher streaming error: %s", exc)

    def publish(self, msg):
        """
        Send message to all connected sockets
        """
        if not self.streams:
            return

        pack = salt.transport.frame.frame_msg_ipc(msg, raw_body=True)
        for stream in list(self.streams):
            if self._write_semaphore.acquire(blocking=False):
                try:
                    stream.write(pack, callback=self._write_semaphore.release)
                except tornado.iostream.StreamClosedError:
                    self._write_semaphore.release()
                    self.streams.discard(stream)
                except Exception as exc:  # pylint: disable=broad-except
                    log.error("Exception in IPCMessagePublisher.publish: %s", exc)
                    self._write_semaphore.release()
                    if not stream.closed():
                        stream.close()
                    self.streams.discard(stream)
            else:
                if stream.max_write_buffer_size - stream.get_write_buffer_size() > len(
                    pack
                ):
                    try:
                        stream.write(pack)
                    except tornado.iostream.StreamClosedError:
                        self.streams.discard(stream)
                    except Exception as exc:  # pylint: disable=broad-except
                        log.error("Exception in IPCMessagePublisher.publish: %s", exc)
                        if not stream.closed():
                            stream.close()
                        self.streams.discard(stream)
                else:
                    log.warning(
                        "IPCMessagePublisher: dropped event due to full buffer (%s/%s)",
                        stream.get_write_buffer_size(),
                        stream.max_write_buffer_size,
                    )


class IPCMessageSubscriber(IPCClient):
    """
    Salt IPC message subscriber
    """

    async_methods = ["connect", "read"]

    def __init__(self, socket_path, io_loop=None):
        warn_until(
            3009,
            "salt.transport.ipc.IPCMessageSubscriber is deprecated. Please use salt.transport.publish_client instead.",
        )
        super().__init__(socket_path, io_loop=io_loop)
        self.unpacker = salt.utils.msgpack.Unpacker(raw=False)
        self._read_stream_future = None
        self._saved_data = []
        self._read_in_progress = threading.Lock()
        self.tasks = set()

    async def _read(self, timeout, callback=None):
        try:
            if self._saved_data:
                ret = self._saved_data.pop(0)
                if callback:
                    callback(ret)
                return ret

            while not self._closing:
                wire_bytes = await self.stream.read_bytes(4096, partial=True)
                self.unpacker.feed(wire_bytes)
                first = True
                ret = None
                for framed_msg in self.unpacker:
                    if first:
                        ret = framed_msg["body"]
                        if callback:
                            callback(ret)
                        first = False
                    else:
                        self._saved_data.append(framed_msg["body"])
                if ret:
                    return ret
        except (tornado.iostream.StreamClosedError, asyncio.CancelledError):
            return None
        except Exception as exc:  # pylint: disable=broad-except
            log.error("IPCMessageSubscriber read error: %s", exc)
            return None

    async def read(self, timeout=None):
        return await self._read(timeout)

    def read_sync(self, timeout=None):
        loop = salt.utils.asynchronous.aioloop(self.io_loop)
        return loop.run_until_complete(self.read(timeout))

    def read_async(self, callback):
        loop = salt.utils.asynchronous.aioloop(self.io_loop)

        async def _read_async():
            while not self._closing:
                await self._read(None, callback)

        task = loop.create_task(_read_async())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def close(self):
        super().close()
        for task in list(self.tasks):
            if not task.done():
                task.cancel()
        self.tasks.clear()

"""
Legacy ZeroMQ helpers retained for backward compatibility.

The classes here rely on Tornado primitives and are slated for removal once the
asyncio migration is complete.
"""

import datetime
import logging

import tornado.concurrent
import tornado.gen
import tornado.ioloop
import tornado.queues

import salt.payload
from salt.exceptions import SaltReqTimeoutError
from salt.utils.zeromq import zmq

log = logging.getLogger(__name__)


def _set_tcp_keepalive(zmq_socket, opts):
    """Mirror the helper from the main zeromq transport."""
    if hasattr(zmq, "TCP_KEEPALIVE") and opts:
        if "tcp_keepalive" in opts:
            zmq_socket.setsockopt(zmq.TCP_KEEPALIVE, opts["tcp_keepalive"])
        if "tcp_keepalive_idle" in opts:
            zmq_socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, opts["tcp_keepalive_idle"])
        if "tcp_keepalive_cnt" in opts:
            zmq_socket.setsockopt(zmq.TCP_KEEPALIVE_CNT, opts["tcp_keepalive_cnt"])
        if "tcp_keepalive_intvl" in opts:
            zmq_socket.setsockopt(zmq.TCP_KEEPALIVE_INTVL, opts["tcp_keepalive_intvl"])


class AsyncReqMessageClient:
    """
    This class wraps the underlying zeromq REQ socket and gives a future-based
    interface to sending and receiving messages. This works around the primary
    limitation of serialized send/recv on the underlying socket by queueing the
    message sends in this class. In the future if we decide to attempt to
    multiplex we can manage a pool of REQ/REP sockets-- but for now we'll just
    do them in serial
    """

    def __init__(self, opts, addr, linger=0, io_loop=None):
        """
        Create an asynchronous message client

        :param dict opts: The salt opts dictionary
        :param str addr: The interface IP address to bind to
        :param int linger: The number of seconds to linger on a ZMQ socket. See
               http://api.zeromq.org/2-1:zmq-setsockopt [ZMQ_LINGER]
        :param IOLoop io_loop: A Tornado IOLoop event scheduler
        """
        salt.utils.versions.warn_until(
            3009,
            "AsyncReqMessageClient has been deprecated and will be removed.",
        )
        self.opts = opts
        self.addr = addr
        self.linger = linger
        if io_loop is None:
            self.io_loop = tornado.ioloop.IOLoop.current()
        else:
            self.io_loop = io_loop
        self.context = zmq.eventloop.future.Context()
        self._closing = False
        self._queue = tornado.queues.Queue()

    def connect(self):
        if hasattr(self, "socket") and self.socket:
            return
        # wire up sockets
        self._init_socket()

    def close(self):
        if self._closing:
            return
        self._closing = True
        if hasattr(self, "socket") and self.socket is not None:
            self.socket.close(0)
            self.socket = None
        if self.context.closed is False:
            self.context.destroy(0)
            self.context.term()
            self.context = None

    def _init_socket(self):
        self._closing = False
        if not self.context:
            self.context = zmq.eventloop.future.Context()
        self.socket = self.context.socket(zmq.REQ)

        # socket options
        if hasattr(zmq, "RECONNECT_IVL_MAX"):
            self.socket.setsockopt(zmq.RECONNECT_IVL_MAX, 5000)

        _set_tcp_keepalive(self.socket, self.opts)
        if self.addr.startswith("tcp://["):
            # Hint PF type if bracket enclosed IPv6 address
            if hasattr(zmq, "IPV6"):
                self.socket.setsockopt(zmq.IPV6, 1)
            elif hasattr(zmq, "IPV4ONLY"):
                self.socket.setsockopt(zmq.IPV4ONLY, 0)
        self.socket.setsockopt(zmq.LINGER, self.linger)
        self.socket.connect(self.addr)
        self.io_loop.spawn_callback(self._send_recv, self.socket)

    def send(self, message, timeout=None, callback=None):
        """
        Return a future which will be completed when the message has a response
        """
        future = tornado.concurrent.Future()

        message = salt.payload.dumps(message)

        self._queue.put_nowait((future, message))

        if callback is not None:

            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)

            future.add_done_callback(handle_future)

        if self.opts.get("detect_mode") is True:
            timeout = 1

        if timeout is not None:
            send_timeout = self.io_loop.call_later(
                timeout, self._timeout_message, future
            )

        recv = yield future

        raise tornado.gen.Return(recv)

    def _timeout_message(self, future):
        if not future.done():
            future.set_exception(SaltReqTimeoutError("Message timed out"))

    @tornado.gen.coroutine
    def _send_recv(self, socket, _TimeoutError=tornado.gen.TimeoutError):
        """
        Long running send/receive coroutine. This should be started once for
        each socket created. Once started, the coroutine will run until the
        socket is closed. A future and message are pulled from the queue. The
        message is sent and the reply socket is polled for a response while
        checking the future to see if it was timed out.
        """
        send_recv_running = True
        # Hold on to the socket so we'll still have a reference to it after the
        # close method is called. This allows us to fail gracefully once it's
        # been closed.
        while send_recv_running:
            try:
                future, message = yield self._queue.get(
                    timeout=datetime.timedelta(milliseconds=300)
                )
            except _TimeoutError:
                try:
                    # For some reason yielding here doesn't work because the
                    # future always has a result?
                    poll_future = socket.poll(0, zmq.POLLOUT)
                    poll_future.result()
                except _TimeoutError:
                    # This is what we expect if the socket is still alive
                    pass
                except zmq.eventloop.future.CancelledError:
                    log.trace("Loop closed while polling send socket.")
                    # The ioloop was closed before polling finished.
                    send_recv_running = False
                    break
                except zmq.ZMQError:
                    log.trace("Send socket closed while polling.")
                    send_recv_running = False
                    break
                continue

            try:
                yield socket.send(message)
            except zmq.eventloop.future.CancelledError as exc:
                log.trace("Loop closed while sending.")
                # The ioloop was closed before polling finished.
                send_recv_running = False
                future.set_exception(exc)
            except zmq.ZMQError as exc:
                if exc.errno in [
                    zmq.ENOTSOCK,
                    zmq.ETERM,
                    zmq.error.EINTR,
                ]:
                    log.trace("Send socket closed while sending.")
                    send_recv_running = False
                    future.set_exception(exc)
                elif exc.errno == zmq.EFSM:
                    log.error("Socket was found in invalid state.")
                    send_recv_running = False
                    future.set_exception(exc)
                else:
                    log.error("Unhandled Zeromq error during send/receive: %s", exc)
                    future.set_exception(exc)

            if future.done():
                if isinstance(future.exception, SaltReqTimeoutError):
                    log.trace(
                        "Request timed out while waiting for a response. reconnecting."
                    )
                else:
                    log.trace("The request ended with an error. reconnecting.")
                self.close()
                self.connect()
                send_recv_running = False
                continue

            received = False
            ready = False
            while True:
                try:
                    # Time is in milliseconds.
                    ready = yield socket.poll(300, zmq.POLLIN)
                except zmq.eventloop.future.CancelledError as exc:
                    log.trace("Loop closed while polling receive socket.")
                    send_recv_running = False
                    future.set_exception(exc)
                except zmq.ZMQError as exc:
                    log.trace("Receive socket closed while polling.")
                    send_recv_running = False
                    future.set_exception(exc)

                if ready:
                    try:
                        recv = yield socket.recv()
                        received = True
                    except zmq.eventloop.future.CancelledError as exc:
                        log.trace("Loop closed while receiving.")
                        send_recv_running = False
                        future.set_exception(exc)
                    except zmq.ZMQError as exc:
                        log.trace("Receive socket closed while receiving.")
                        send_recv_running = False
                        future.set_exception(exc)
                    break
                elif future.done():
                    break

            if future.done():
                if isinstance(future.exception, SaltReqTimeoutError):
                    log.trace(
                        "Request timed out while waiting for a response. reconnecting."
                    )
                else:
                    log.trace("The request ended with an error. reconnecting.")
                self.close()
                self.connect()
                send_recv_running = False
            elif received:
                data = salt.payload.loads(recv)
                future.set_result(data)
        log.trace("Send and receive coroutine ending %s", socket)

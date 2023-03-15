"""
Zeromq transport classes
"""
import errno
import hashlib
import logging
import os
import signal
import sys
import threading
from random import randint

import zmq.error
import zmq.eventloop.zmqstream

import salt.ext.tornado
import salt.ext.tornado.concurrent
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.payload
import salt.transport.base
import salt.utils.files
import salt.utils.process
import salt.utils.stringutils
import salt.utils.zeromq
from salt._compat import ipaddress
from salt.exceptions import SaltException, SaltReqTimeoutError
from salt.utils.zeromq import LIBZMQ_VERSION_INFO, ZMQ_VERSION_INFO, zmq

try:
    import zmq.utils.monitor

    HAS_ZMQ_MONITOR = True
except ImportError:
    HAS_ZMQ_MONITOR = False


log = logging.getLogger(__name__)


def _get_master_uri(master_ip, master_port, source_ip=None, source_port=None):
    """
    Return the ZeroMQ URI to connect the Minion to the Master.
    It supports different source IP / port, given the ZeroMQ syntax:
    // Connecting using a IP address and bind to an IP address
    rc = zmq_connect(socket, "tcp://192.168.1.17:5555;192.168.1.1:5555"); assert (rc == 0);
    Source: http://api.zeromq.org/4-1:zmq-tcp
    """
    from salt.utils.network import ip_bracket

    master_uri = "tcp://{master_ip}:{master_port}".format(
        master_ip=ip_bracket(master_ip), master_port=master_port
    )

    if source_ip or source_port:
        if LIBZMQ_VERSION_INFO >= (4, 1, 6) and ZMQ_VERSION_INFO >= (16, 0, 1):
            # The source:port syntax for ZeroMQ has been added in libzmq 4.1.6
            # which is included in the pyzmq wheels starting with 16.0.1.
            if source_ip and source_port:
                master_uri = (
                    "tcp://{source_ip}:{source_port};{master_ip}:{master_port}".format(
                        source_ip=ip_bracket(source_ip),
                        source_port=source_port,
                        master_ip=ip_bracket(master_ip),
                        master_port=master_port,
                    )
                )
            elif source_ip and not source_port:
                master_uri = "tcp://{source_ip}:0;{master_ip}:{master_port}".format(
                    source_ip=ip_bracket(source_ip),
                    master_ip=ip_bracket(master_ip),
                    master_port=master_port,
                )
            elif source_port and not source_ip:
                ip_any = (
                    "0.0.0.0"
                    if ipaddress.ip_address(master_ip).version == 4
                    else ip_bracket("::")
                )
                master_uri = (
                    "tcp://{ip_any}:{source_port};{master_ip}:{master_port}".format(
                        ip_any=ip_any,
                        source_port=source_port,
                        master_ip=ip_bracket(master_ip),
                        master_port=master_port,
                    )
                )
        else:
            log.warning(
                "Unable to connect to the Master using a specific source IP / port"
            )
            log.warning("Consider upgrading to pyzmq >= 16.0.1 and libzmq >= 4.1.6")
            log.warning(
                "Specific source IP / port for connecting to master returner port:"
                " configuraion ignored"
            )

    return master_uri


class PublishClient(salt.transport.base.PublishClient):
    """
    A transport channel backed by ZeroMQ for a Salt Publisher to use to
    publish commands to connected minions
    """

    ttype = "zeromq"

    def __init__(self, opts, io_loop, **kwargs):
        super().__init__(opts, io_loop, **kwargs)
        self.opts = opts
        self.io_loop = io_loop
        self.hexid = hashlib.sha1(
            salt.utils.stringutils.to_bytes(self.opts["id"])
        ).hexdigest()
        self._closing = False
        self.context = zmq.Context()
        self._socket = self.context.socket(zmq.SUB)
        if self.opts["zmq_filtering"]:
            # TODO: constants file for "broadcast"
            self._socket.setsockopt(zmq.SUBSCRIBE, b"broadcast")
            if self.opts.get("__role") == "syndic":
                self._socket.setsockopt(zmq.SUBSCRIBE, b"syndic")
            else:
                self._socket.setsockopt(
                    zmq.SUBSCRIBE, salt.utils.stringutils.to_bytes(self.hexid)
                )
        else:
            self._socket.setsockopt(zmq.SUBSCRIBE, b"")

        self._socket.setsockopt(
            zmq.IDENTITY, salt.utils.stringutils.to_bytes(self.opts["id"])
        )

        # TODO: cleanup all the socket opts stuff
        if hasattr(zmq, "TCP_KEEPALIVE"):
            self._socket.setsockopt(zmq.TCP_KEEPALIVE, self.opts["tcp_keepalive"])
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE_IDLE, self.opts["tcp_keepalive_idle"]
            )
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE_CNT, self.opts["tcp_keepalive_cnt"]
            )
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE_INTVL, self.opts["tcp_keepalive_intvl"]
            )

        recon_delay = self.opts["recon_default"]

        if self.opts["recon_randomize"]:
            recon_delay = randint(
                self.opts["recon_default"],
                self.opts["recon_default"] + self.opts["recon_max"],
            )

            log.debug(
                "Generated random reconnect delay between '%sms' and '%sms' (%s)",
                self.opts["recon_default"],
                self.opts["recon_default"] + self.opts["recon_max"],
                recon_delay,
            )

        log.debug("Setting zmq_reconnect_ivl to '%sms'", recon_delay)
        self._socket.setsockopt(zmq.RECONNECT_IVL, recon_delay)

        if hasattr(zmq, "RECONNECT_IVL_MAX"):
            log.debug(
                "Setting zmq_reconnect_ivl_max to '%sms'",
                self.opts["recon_default"] + self.opts["recon_max"],
            )

            self._socket.setsockopt(zmq.RECONNECT_IVL_MAX, self.opts["recon_max"])

        if (self.opts["ipv6"] is True or ":" in self.opts["master_ip"]) and hasattr(
            zmq, "IPV4ONLY"
        ):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self._socket.setsockopt(zmq.IPV4ONLY, 0)

        if HAS_ZMQ_MONITOR and self.opts["zmq_monitor"]:
            self._monitor = ZeroMQSocketMonitor(self._socket)
            self._monitor.start_io_loop(self.io_loop)

    def close(self):
        if self._closing is True:
            return
        self._closing = True
        if hasattr(self, "_monitor") and self._monitor is not None:
            self._monitor.stop()
            self._monitor = None
        if hasattr(self, "_stream"):
            self._stream.close(0)
        elif hasattr(self, "_socket"):
            self._socket.close(0)
        if hasattr(self, "context") and self.context.closed is False:
            self.context.term()

    # pylint: enable=W1701
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # TODO: this is the time to see if we are connected, maybe use the req channel to guess?
    @salt.ext.tornado.gen.coroutine
    def connect(self, publish_port, connect_callback=None, disconnect_callback=None):
        self.publish_port = publish_port
        log.debug(
            "Connecting the Minion to the Master publish port, using the URI: %s",
            self.master_pub,
        )
        log.debug("%r connecting to %s", self, self.master_pub)
        self._socket.connect(self.master_pub)
        connect_callback(True)

    @property
    def master_pub(self):
        """
        Return the master publish port
        """
        return _get_master_uri(
            self.opts["master_ip"],
            self.publish_port,
            source_ip=self.opts.get("source_ip"),
            source_port=self.opts.get("source_publish_port"),
        )

    @salt.ext.tornado.gen.coroutine
    def _decode_messages(self, messages):
        """
        Take the zmq messages, decrypt/decode them into a payload

        :param list messages: A list of messages to be decoded
        """
        messages_len = len(messages)
        # if it was one message, then its old style
        if messages_len == 1:
            payload = salt.payload.loads(messages[0])
        # 2 includes a header which says who should do it
        elif messages_len == 2:
            message_target = salt.utils.stringutils.to_str(messages[0])
            if (
                self.opts.get("__role") != "syndic"
                and message_target not in ("broadcast", self.hexid)
            ) or (
                self.opts.get("__role") == "syndic"
                and message_target not in ("broadcast", "syndic")
            ):
                log.debug("Publish received for not this minion: %s", message_target)
                raise salt.ext.tornado.gen.Return(None)
            payload = salt.payload.loads(messages[1])
        else:
            raise Exception(
                "Invalid number of messages ({}) in zeromq pubmessage from master".format(
                    len(messages_len)
                )
            )
        # Yield control back to the caller. When the payload has been decoded, assign
        # the decoded payload to 'ret' and resume operation
        raise salt.ext.tornado.gen.Return(payload)

    @property
    def stream(self):
        """
        Return the current zmqstream, creating one if necessary
        """
        if not hasattr(self, "_stream"):
            self._stream = zmq.eventloop.zmqstream.ZMQStream(
                self._socket, io_loop=self.io_loop
            )
        return self._stream

    def on_recv(self, callback):
        """
        Register a callback for received messages (that we didn't initiate)

        :param func callback: A function which should be called when data is received
        """
        return self.stream.on_recv(callback)

    @salt.ext.tornado.gen.coroutine
    def send(self, msg):
        self.stream.send(msg, noblock=True)


class RequestServer(salt.transport.base.DaemonizedRequestServer):
    def __init__(self, opts):  # pylint: disable=W0231
        self.opts = opts
        self._closing = False
        self._monitor = None
        self._w_monitor = None

    def zmq_device(self):
        """
        Multiprocessing target for the zmq queue device
        """
        self.__setup_signals()
        context = zmq.Context(self.opts["worker_threads"])
        # Prepare the zeromq sockets
        self.uri = "tcp://{interface}:{ret_port}".format(**self.opts)
        self.clients = context.socket(zmq.ROUTER)
        self.clients.setsockopt(zmq.LINGER, -1)
        if self.opts["ipv6"] is True and hasattr(zmq, "IPV4ONLY"):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.clients.setsockopt(zmq.IPV4ONLY, 0)
        self.clients.setsockopt(zmq.BACKLOG, self.opts.get("zmq_backlog", 1000))
        self._start_zmq_monitor()
        self.workers = context.socket(zmq.DEALER)
        self.workers.setsockopt(zmq.LINGER, -1)

        if self.opts["mworker_queue_niceness"] and not salt.utils.platform.is_windows():
            log.info(
                "setting mworker_queue niceness to %d",
                self.opts["mworker_queue_niceness"],
            )
            os.nice(self.opts["mworker_queue_niceness"])

        if self.opts.get("ipc_mode", "") == "tcp":
            self.w_uri = "tcp://127.0.0.1:{}".format(
                self.opts.get("tcp_master_workers", 4515)
            )
        else:
            self.w_uri = "ipc://{}".format(
                os.path.join(self.opts["sock_dir"], "workers.ipc")
            )

        log.info("Setting up the master communication server")
        log.info("ReqServer clients %s", self.uri)
        self.clients.bind(self.uri)
        log.info("ReqServer workers %s", self.w_uri)
        self.workers.bind(self.w_uri)

        while True:
            if self.clients.closed or self.workers.closed:
                break
            try:
                zmq.device(zmq.QUEUE, self.clients, self.workers)
            except zmq.ZMQError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise
            except (KeyboardInterrupt, SystemExit):
                break
        context.term()

    def close(self):
        """
        Cleanly shutdown the router socket
        """
        if self._closing:
            return
        log.info("MWorkerQueue under PID %s is closing", os.getpid())
        self._closing = True
        if getattr(self, "_monitor", None) is not None:
            self._monitor.stop()
            self._monitor = None
        if getattr(self, "_w_monitor", None) is not None:
            self._w_monitor.stop()
            self._w_monitor = None
        if hasattr(self, "clients") and self.clients.closed is False:
            self.clients.close()
        if hasattr(self, "workers") and self.workers.closed is False:
            self.workers.close()
        if hasattr(self, "stream"):
            self.stream.close()
        if hasattr(self, "_socket") and self._socket.closed is False:
            self._socket.close()
        if hasattr(self, "context") and self.context.closed is False:
            self.context.term()

    def pre_fork(self, process_manager):
        """
        Pre-fork we need to create the zmq router device

        :param func process_manager: An instance of salt.utils.process.ProcessManager
        """
        process_manager.add_process(self.zmq_device, name="MWorkerQueue")

    def _start_zmq_monitor(self):
        """
        Starts ZMQ monitor for debugging purposes.
        :return:
        """
        # Socket monitor shall be used the only for debug
        # purposes so using threading doesn't look too bad here

        if HAS_ZMQ_MONITOR and self.opts["zmq_monitor"]:
            log.debug("Starting ZMQ monitor")
            self._w_monitor = ZeroMQSocketMonitor(self._socket)
            threading.Thread(target=self._w_monitor.start_poll).start()
            log.debug("ZMQ monitor has been started started")

    def post_fork(self, message_handler, io_loop):
        """
        After forking we need to create all of the local sockets to listen to the
        router

        :param func message_handler: A function to called to handle incoming payloads as
                                     they are picked up off the wire
        :param IOLoop io_loop: An instance of a Tornado IOLoop, to handle event scheduling
        """
        context = zmq.Context(1)
        self._socket = context.socket(zmq.REP)
        # Linger -1 means we'll never discard messages.
        self._socket.setsockopt(zmq.LINGER, -1)
        self._start_zmq_monitor()

        if self.opts.get("ipc_mode", "") == "tcp":
            self.w_uri = "tcp://127.0.0.1:{}".format(
                self.opts.get("tcp_master_workers", 4515)
            )
        else:
            self.w_uri = "ipc://{}".format(
                os.path.join(self.opts["sock_dir"], "workers.ipc")
            )
        log.info("Worker binding to socket %s", self.w_uri)
        self._socket.connect(self.w_uri)
        self.stream = zmq.eventloop.zmqstream.ZMQStream(self._socket, io_loop=io_loop)
        self.message_handler = message_handler
        self.stream.on_recv_stream(self.handle_message)

    @salt.ext.tornado.gen.coroutine
    def handle_message(self, stream, payload):
        payload = self.decode_payload(payload)
        # XXX: Is header really needed?
        reply = yield self.message_handler(payload)
        self.stream.send(self.encode_payload(reply))

    def encode_payload(self, payload):
        return salt.payload.dumps(payload)

    def __setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_signals)
        signal.signal(signal.SIGTERM, self._handle_signals)

    def _handle_signals(self, signum, sigframe):
        msg = "{} received a ".format(self.__class__.__name__)
        if signum == signal.SIGINT:
            msg += "SIGINT"
        elif signum == signal.SIGTERM:
            msg += "SIGTERM"
        msg += ". Exiting"
        log.debug(msg)
        self.close()
        sys.exit(salt.defaults.exitcodes.EX_OK)

    def decode_payload(self, payload):
        payload = salt.payload.loads(payload[0])
        return payload


def _set_tcp_keepalive(zmq_socket, opts):
    """
    Ensure that TCP keepalives are set as specified in "opts".

    Warning: Failure to set TCP keepalives on the salt-master can result in
    not detecting the loss of a minion when the connection is lost or when
    its host has been terminated without first closing the socket.
    Salt's Presence System depends on this connection status to know if a minion
    is "present".

    Warning: Failure to set TCP keepalives on minions can result in frequent or
    unexpected disconnects!
    """
    if hasattr(zmq, "TCP_KEEPALIVE") and opts:
        if "tcp_keepalive" in opts:
            zmq_socket.setsockopt(zmq.TCP_KEEPALIVE, opts["tcp_keepalive"])
        if "tcp_keepalive_idle" in opts:
            zmq_socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, opts["tcp_keepalive_idle"])
        if "tcp_keepalive_cnt" in opts:
            zmq_socket.setsockopt(zmq.TCP_KEEPALIVE_CNT, opts["tcp_keepalive_cnt"])
        if "tcp_keepalive_intvl" in opts:
            zmq_socket.setsockopt(zmq.TCP_KEEPALIVE_INTVL, opts["tcp_keepalive_intvl"])


# TODO: unit tests!
class AsyncReqMessageClient:
    """
    This class wraps the underlying zeromq REQ socket and gives a future-based
    interface to sending and recieving messages. This works around the primary
    limitation of serialized send/recv on the underlying socket by queueing the
    message sends in this class. In the future if we decide to attempt to multiplex
    we can manage a pool of REQ/REP sockets-- but for now we'll just do them in serial
    """

    def __init__(self, opts, addr, linger=0, io_loop=None):
        """
        Create an asynchronous message client

        :param dict opts: The salt opts dictionary
        :param str addr: The interface IP address to bind to
        :param int linger: The number of seconds to linger on a ZMQ socket. See
                           http://api.zeromq.org/2-1:zmq-setsockopt [ZMQ_LINGER]
        :param IOLoop io_loop: A Tornado IOLoop event scheduler [tornado.ioloop.IOLoop]
        """
        self.opts = opts
        self.addr = addr
        self.linger = linger
        if io_loop is None:
            self.io_loop = salt.ext.tornado.ioloop.IOLoop.current()
        else:
            self.io_loop = io_loop

        self.context = zmq.Context()

        self.send_queue = []
        # mapping of message -> future
        self.send_future_map = {}

        self._closing = False

    def connect(self):
        # wire up sockets
        self._init_socket()

    # TODO: timeout all in-flight sessions, or error
    def close(self):
        try:
            if self._closing:
                return
        except AttributeError:
            # We must have been called from __del__
            # The python interpreter has nuked most attributes already
            return
        else:
            self._closing = True
            if hasattr(self, "stream") and self.stream is not None:
                if ZMQ_VERSION_INFO < (14, 3, 0):
                    # stream.close() doesn't work properly on pyzmq < 14.3.0
                    if self.stream.socket:
                        self.stream.socket.close()
                    self.stream.io_loop.remove_handler(self.stream.socket)
                    # set this to None, more hacks for messed up pyzmq
                    self.stream.socket = None
                    self.socket.close()
                else:
                    self.stream.close(1)
                    self.socket = None
                self.stream = None
            if self.context.closed is False:
                self.context.term()

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    def _init_socket(self):
        if hasattr(self, "stream"):
            self.stream.close()  # pylint: disable=E0203
            self.socket.close()  # pylint: disable=E0203
            del self.stream
            del self.socket

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
        self.socket.linger = self.linger
        self.socket.connect(self.addr)
        self.stream = zmq.eventloop.zmqstream.ZMQStream(
            self.socket, io_loop=self.io_loop
        )

    def timeout_message(self, message):
        """
        Handle a message timeout by removing it from the sending queue
        and informing the caller

        :raises: SaltReqTimeoutError
        """
        future = self.send_future_map.pop(message, None)
        # In a race condition the message might have been sent by the time
        # we're timing it out. Make sure the future is not None
        if future is not None:
            future.set_exception(SaltReqTimeoutError("Message timed out"))

    @salt.ext.tornado.gen.coroutine
    def send(self, message, timeout=None, callback=None):
        """
        Return a future which will be completed when the message has a response
        """
        future = salt.ext.tornado.concurrent.Future()

        message = salt.payload.dumps(message)

        if callback is not None:

            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)

            future.add_done_callback(handle_future)

        # Add this future to the mapping
        self.send_future_map[message] = future

        if self.opts.get("detect_mode") is True:
            timeout = 1

        if timeout is not None:
            send_timeout = self.io_loop.call_later(
                timeout, self.timeout_message, message
            )

        def mark_future(msg):
            if not future.done():
                data = salt.payload.loads(msg[0])
                future.set_result(data)
                self.send_future_map.pop(message)

        self.stream.on_recv(mark_future)
        yield self.stream.send(message)
        recv = yield future
        raise salt.ext.tornado.gen.Return(recv)


class ZeroMQSocketMonitor:
    __EVENT_MAP = None

    def __init__(self, socket):
        """
        Create ZMQ monitor sockets

        More information:
            http://api.zeromq.org/4-0:zmq-socket-monitor
        """
        self._socket = socket
        self._monitor_socket = self._socket.get_monitor_socket()
        self._monitor_stream = None

    def start_io_loop(self, io_loop):
        log.trace("Event monitor start!")
        self._monitor_stream = zmq.eventloop.zmqstream.ZMQStream(
            self._monitor_socket, io_loop=io_loop
        )
        self._monitor_stream.on_recv(self.monitor_callback)

    def start_poll(self):
        log.trace("Event monitor start!")
        try:
            while self._monitor_socket is not None and self._monitor_socket.poll():
                msg = self._monitor_socket.recv_multipart()
                self.monitor_callback(msg)
        except (AttributeError, zmq.error.ContextTerminated):
            # We cannot log here because we'll get an interrupted system call in trying
            # to flush the logging buffer as we terminate
            pass

    @property
    def event_map(self):
        if ZeroMQSocketMonitor.__EVENT_MAP is None:
            event_map = {}
            for name in dir(zmq):
                if name.startswith("EVENT_"):
                    value = getattr(zmq, name)
                    event_map[value] = name
            ZeroMQSocketMonitor.__EVENT_MAP = event_map
        return ZeroMQSocketMonitor.__EVENT_MAP

    def monitor_callback(self, msg):
        evt = zmq.utils.monitor.parse_monitor_message(msg)
        evt["description"] = self.event_map[evt["event"]]
        log.debug("ZeroMQ event: %s", evt)
        if evt["event"] == zmq.EVENT_MONITOR_STOPPED:
            self.stop()

    def stop(self):
        if self._socket is None:
            return
        self._socket.disable_monitor()
        self._socket = None
        self._monitor_socket = None
        if self._monitor_stream is not None:
            self._monitor_stream.close()
            self._monitor_stream = None
        log.trace("Event monitor done!")


class PublishServer(salt.transport.base.DaemonizedPublishServer):
    """
    Encapsulate synchronous operations for a publisher channel
    """

    _sock_data = threading.local()

    def __init__(self, opts):
        self.opts = opts

    def connect(self):
        return salt.ext.tornado.gen.sleep(5)

    def publish_daemon(
        self,
        publish_payload,
        presence_callback=None,
        remove_presence_callback=None,
    ):
        """
        This method represents the Publish Daemon process. It is intended to be
        run in a thread or process as it creates and runs an it's own ioloop.
        """
        ioloop = salt.ext.tornado.ioloop.IOLoop()
        ioloop.make_current()
        self.io_loop = ioloop
        context = zmq.Context(1)
        pub_sock = context.socket(zmq.PUB)
        monitor = ZeroMQSocketMonitor(pub_sock)
        monitor.start_io_loop(ioloop)
        _set_tcp_keepalive(pub_sock, self.opts)
        self.dpub_sock = pub_sock = zmq.eventloop.zmqstream.ZMQStream(pub_sock)
        # if 2.1 >= zmq < 3.0, we only have one HWM setting
        try:
            pub_sock.setsockopt(zmq.HWM, self.opts.get("pub_hwm", 1000))
        # in zmq >= 3.0, there are separate send and receive HWM settings
        except (AttributeError, zmq.error.ZMQError):
            # Set the High Water Marks. For more information on HWM, see:
            # http://api.zeromq.org/4-1:zmq-setsockopt
            pub_sock.setsockopt(zmq.SNDHWM, self.opts.get("pub_hwm", 1000))
            pub_sock.setsockopt(zmq.RCVHWM, self.opts.get("pub_hwm", 1000))
        if self.opts["ipv6"] is True and hasattr(zmq, "IPV4ONLY"):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            pub_sock.setsockopt(zmq.IPV4ONLY, 0)
        pub_sock.setsockopt(zmq.BACKLOG, self.opts.get("zmq_backlog", 1000))
        pub_sock.setsockopt(zmq.LINGER, -1)
        # Prepare minion pull socket
        pull_sock = context.socket(zmq.PULL)
        pull_sock = zmq.eventloop.zmqstream.ZMQStream(pull_sock)
        pull_sock.setsockopt(zmq.LINGER, -1)
        salt.utils.zeromq.check_ipc_path_max_len(self.pull_uri)
        # Start the minion command publisher
        log.info("Starting the Salt Publisher on %s", self.pub_uri)
        pub_sock.bind(self.pub_uri)
        # Securely create socket
        log.info("Starting the Salt Puller on %s", self.pull_uri)
        with salt.utils.files.set_umask(0o177):
            pull_sock.bind(self.pull_uri)

        @salt.ext.tornado.gen.coroutine
        def on_recv(packages):
            for package in packages:
                payload = salt.payload.loads(package)
                yield publish_payload(payload)

        pull_sock.on_recv(on_recv)
        try:
            ioloop.start()
        finally:
            pub_sock.close()
            pull_sock.close()

    @property
    def pull_uri(self):
        if self.opts.get("ipc_mode", "") == "tcp":
            pull_uri = "tcp://127.0.0.1:{}".format(
                self.opts.get("tcp_master_publish_pull", 4514)
            )
        else:
            pull_uri = "ipc://{}".format(
                os.path.join(self.opts["sock_dir"], "publish_pull.ipc")
            )
        return pull_uri

    @property
    def pub_uri(self):
        return "tcp://{interface}:{publish_port}".format(**self.opts)

    @salt.ext.tornado.gen.coroutine
    def publish_payload(self, payload, topic_list=None):
        payload = salt.payload.dumps(payload)
        if self.opts["zmq_filtering"]:
            if topic_list:
                for topic in topic_list:
                    log.trace("Sending filtered data over publisher %s", self.pub_uri)
                    # zmq filters are substring match, hash the topic
                    # to avoid collisions
                    htopic = salt.utils.stringutils.to_bytes(
                        hashlib.sha1(salt.utils.stringutils.to_bytes(topic)).hexdigest()
                    )
                    yield self.dpub_sock.send(htopic, flags=zmq.SNDMORE)
                    yield self.dpub_sock.send(payload)
                    log.trace("Filtered data has been sent")
                # Syndic broadcast
                if self.opts.get("order_masters"):
                    log.trace("Sending filtered data to syndic")
                    yield self.dpub_sock.send(b"syndic", flags=zmq.SNDMORE)
                    yield self.dpub_sock.send(payload)
                    log.trace("Filtered data has been sent to syndic")
            # otherwise its a broadcast
            else:
                # TODO: constants file for "broadcast"
                log.trace("Sending broadcasted data over publisher %s", self.pub_uri)
                yield self.dpub_sock.send(b"broadcast", flags=zmq.SNDMORE)
                yield self.dpub_sock.send(payload)
                log.trace("Broadcasted data has been sent")
        else:
            log.trace("Sending ZMQ-unfiltered data over publisher %s", self.pub_uri)
            yield self.dpub_sock.send(payload)
            log.trace("Unfiltered data has been sent")

    def pre_fork(self, process_manager):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing

        :param func process_manager: A ProcessManager, from salt.utils.process.ProcessManager
        """
        process_manager.add_process(
            self.publish_daemon,
            args=(self.publish_payload,),
        )

    @property
    def pub_sock(self):
        """
        This thread's zmq publisher socket. This socket is stored on the class
        so that multiple instantiations in the same thread will re-use a single
        zmq socket.
        """
        try:
            return self._sock_data.sock
        except AttributeError:
            pass

    def pub_connect(self):
        """
        Create and connect this thread's zmq socket. If a publisher socket
        already exists "pub_close" is called before creating and connecting a
        new socket.
        """
        if self.pub_sock:
            self.pub_close()
        ctx = zmq.Context()
        self._sock_data.sock = ctx.socket(zmq.PUSH)
        self.pub_sock.setsockopt(zmq.LINGER, -1)
        if self.opts.get("ipc_mode", "") == "tcp":
            pull_uri = "tcp://127.0.0.1:{}".format(
                self.opts.get("tcp_master_publish_pull", 4514)
            )
        else:
            pull_uri = "ipc://{}".format(
                os.path.join(self.opts["sock_dir"], "publish_pull.ipc")
            )
        log.debug("Connecting to pub server: %s", pull_uri)
        self.pub_sock.connect(pull_uri)
        return self._sock_data.sock

    def pub_close(self):
        """
        Disconnect an existing publisher socket and remove it from the local
        thread's cache.
        """
        if hasattr(self._sock_data, "sock"):
            self._sock_data.sock.close()
            delattr(self._sock_data, "sock")

    def publish(self, payload, **kwargs):
        """
        Publish "load" to minions. This send the load to the publisher daemon
        process with does the actual sending to minions.

        :param dict load: A load to be sent across the wire to minions
        """
        if not self.pub_sock:
            self.pub_connect()
        serialized = salt.payload.dumps(payload)
        self.pub_sock.send(serialized)
        log.debug("Sent payload to publish daemon.")

    @property
    def topic_support(self):
        return self.opts.get("zmq_filtering", False)

    def close(self):
        self.pub_close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class RequestClient(salt.transport.base.RequestClient):

    ttype = "zeromq"

    def __init__(self, opts, io_loop):  # pylint: disable=W0231
        self.opts = opts
        master_uri = self.get_master_uri(opts)
        self.message_client = AsyncReqMessageClient(
            self.opts,
            master_uri,
            io_loop=io_loop,
        )

    def connect(self):
        self.message_client.connect()

    @salt.ext.tornado.gen.coroutine
    def send(self, load, timeout=60):
        self.connect()
        ret = yield self.message_client.send(load, timeout=timeout)
        raise salt.ext.tornado.gen.Return(ret)

    def close(self):
        self.message_client.close()

    @staticmethod
    def get_master_uri(opts):
        if "master_uri" in opts:
            return opts["master_uri"]
        if "master_ip" in opts:
            return _get_master_uri(
                opts["master_ip"],
                opts["master_port"],
                source_ip=opts.get("source_ip"),
                source_port=opts.get("source_ret_port"),
            )
        # if we've reached here something is very abnormal
        raise SaltException("ReqChannel: missing master_uri/master_ip in self.opts")

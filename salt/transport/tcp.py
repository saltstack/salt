"""
TCP transport classes

Wire protocol: "len(payload) msgpack({'head': SOMEHEADER, 'body': SOMEBODY})"

"""
import errno
import logging
import os
import queue
import socket
import threading
import time
import traceback
import urllib.parse

import salt.crypt
import salt.exceptions
import salt.ext.tornado
import salt.ext.tornado.concurrent
import salt.ext.tornado.gen
import salt.ext.tornado.iostream
import salt.ext.tornado.netutil
import salt.ext.tornado.tcpclient
import salt.ext.tornado.tcpserver
import salt.payload
import salt.transport.client
import salt.transport.frame
import salt.transport.ipc
import salt.transport.mixins.auth
import salt.transport.server
import salt.utils.asynchronous
import salt.utils.event
import salt.utils.files
import salt.utils.msgpack
import salt.utils.platform
import salt.utils.process
import salt.utils.verify
import salt.utils.versions
from salt.exceptions import SaltClientError, SaltReqTimeoutError
from salt.transport import iter_transport_opts

try:
    from M2Crypto import RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.Cipher import PKCS1_OAEP
    except ImportError:
        from Crypto.Cipher import PKCS1_OAEP  # nosec

if salt.utils.platform.is_windows():
    USE_LOAD_BALANCER = True
else:
    USE_LOAD_BALANCER = False

if USE_LOAD_BALANCER:
    import threading
    import multiprocessing
    import salt.ext.tornado.util
    from salt.utils.process import SignalHandlingProcess

log = logging.getLogger(__name__)


def _set_tcp_keepalive(sock, opts):
    """
    Ensure that TCP keepalives are set for the socket.
    """
    if hasattr(socket, "SO_KEEPALIVE"):
        if opts.get("tcp_keepalive", False):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, "SOL_TCP"):
                if hasattr(socket, "TCP_KEEPIDLE"):
                    tcp_keepalive_idle = opts.get("tcp_keepalive_idle", -1)
                    if tcp_keepalive_idle > 0:
                        sock.setsockopt(
                            socket.SOL_TCP, socket.TCP_KEEPIDLE, int(tcp_keepalive_idle)
                        )
                if hasattr(socket, "TCP_KEEPCNT"):
                    tcp_keepalive_cnt = opts.get("tcp_keepalive_cnt", -1)
                    if tcp_keepalive_cnt > 0:
                        sock.setsockopt(
                            socket.SOL_TCP, socket.TCP_KEEPCNT, int(tcp_keepalive_cnt)
                        )
                if hasattr(socket, "TCP_KEEPINTVL"):
                    tcp_keepalive_intvl = opts.get("tcp_keepalive_intvl", -1)
                    if tcp_keepalive_intvl > 0:
                        sock.setsockopt(
                            socket.SOL_TCP,
                            socket.TCP_KEEPINTVL,
                            int(tcp_keepalive_intvl),
                        )
            if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                # Windows doesn't support TCP_KEEPIDLE, TCP_KEEPCNT, nor
                # TCP_KEEPINTVL. Instead, it has its own proprietary
                # SIO_KEEPALIVE_VALS.
                tcp_keepalive_idle = opts.get("tcp_keepalive_idle", -1)
                tcp_keepalive_intvl = opts.get("tcp_keepalive_intvl", -1)
                # Windows doesn't support changing something equivalent to
                # TCP_KEEPCNT.
                if tcp_keepalive_idle > 0 or tcp_keepalive_intvl > 0:
                    # Windows defaults may be found by using the link below.
                    # Search for 'KeepAliveTime' and 'KeepAliveInterval'.
                    # https://technet.microsoft.com/en-us/library/bb726981.aspx#EDAA
                    # If one value is set and the other isn't, we still need
                    # to send both values to SIO_KEEPALIVE_VALS and they both
                    # need to be valid. So in that case, use the Windows
                    # default.
                    if tcp_keepalive_idle <= 0:
                        tcp_keepalive_idle = 7200
                    if tcp_keepalive_intvl <= 0:
                        tcp_keepalive_intvl = 1
                    # The values expected are in milliseconds, so multiply by
                    # 1000.
                    sock.ioctl(
                        socket.SIO_KEEPALIVE_VALS,
                        (
                            1,
                            int(tcp_keepalive_idle * 1000),
                            int(tcp_keepalive_intvl * 1000),
                        ),
                    )
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 0)


if USE_LOAD_BALANCER:

    class LoadBalancerServer(SignalHandlingProcess):
        """
        Raw TCP server which runs in its own process and will listen
        for incoming connections. Each incoming connection will be
        sent via multiprocessing queue to the workers.
        Since the queue is shared amongst workers, only one worker will
        handle a given connection.
        """

        # TODO: opts!
        # Based on default used in salt.ext.tornado.netutil.bind_sockets()
        backlog = 128

        def __init__(self, opts, socket_queue, **kwargs):
            super().__init__(**kwargs)
            self.opts = opts
            self.socket_queue = socket_queue
            self._socket = None

        def close(self):
            if self._socket is not None:
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
                self._socket = None

        # pylint: disable=W1701
        def __del__(self):
            self.close()

        # pylint: enable=W1701

        def run(self):
            """
            Start the load balancer
            """
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _set_tcp_keepalive(self._socket, self.opts)
            self._socket.setblocking(1)
            self._socket.bind((self.opts["interface"], int(self.opts["ret_port"])))
            self._socket.listen(self.backlog)

            while True:
                try:
                    # Wait for a connection to occur since the socket is
                    # blocking.
                    connection, address = self._socket.accept()
                    # Wait for a free slot to be available to put
                    # the connection into.
                    # Sockets are picklable on Windows in Python 3.
                    self.socket_queue.put((connection, address), True, None)
                except OSError as e:
                    # ECONNABORTED indicates that there was a connection
                    # but it was closed while still in the accept queue.
                    # (observed on FreeBSD).
                    if (
                        salt.ext.tornado.util.errno_from_exception(e)
                        == errno.ECONNABORTED
                    ):
                        continue
                    raise


# TODO: move serial down into message library
class AsyncTCPReqChannel(salt.transport.client.ReqChannel):
    """
    Encapsulate sending routines to tcp.

    Note: this class returns a singleton
    """

    async_methods = [
        "crypted_transfer_decode_dictentry",
        "_crypted_transfer",
        "_uncrypted_transfer",
        "send",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, opts, **kwargs):
        self.opts = dict(opts)
        if "master_uri" in kwargs:
            self.opts["master_uri"] = kwargs["master_uri"]

        # crypt defaults to 'aes'
        self.crypt = kwargs.get("crypt", "aes")

        self.io_loop = kwargs.get("io_loop") or salt.ext.tornado.ioloop.IOLoop.current()

        if self.crypt != "clear":
            self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)

        resolver = kwargs.get("resolver")

        parse = urllib.parse.urlparse(self.opts["master_uri"])
        master_host, master_port = parse.netloc.rsplit(":", 1)
        self.master_addr = (master_host, int(master_port))
        self._closing = False
        self.message_client = SaltMessageClientPool(
            self.opts,
            args=(
                self.opts,
                master_host,
                int(master_port),
            ),
            kwargs={
                "io_loop": self.io_loop,
                "resolver": resolver,
                "source_ip": self.opts.get("source_ip"),
                "source_port": self.opts.get("source_ret_port"),
            },
        )

    def close(self):
        if self._closing:
            return
        log.debug("Closing %s instance", self.__class__.__name__)
        self._closing = True
        self.message_client.close()

    # pylint: disable=W1701
    def __del__(self):
        try:
            self.close()
        except OSError as exc:
            if exc.errno != errno.EBADF:
                # If its not a bad file descriptor error, raise
                raise

    # pylint: enable=W1701

    def _package_load(self, load):
        return {
            "enc": self.crypt,
            "load": load,
        }

    @salt.ext.tornado.gen.coroutine
    def crypted_transfer_decode_dictentry(
        self, load, dictkey=None, tries=3, timeout=60
    ):
        if not self.auth.authenticated:
            yield self.auth.authenticate()
        ret = yield self.message_client.send(
            self._package_load(self.auth.crypticle.dumps(load)),
            timeout=timeout,
            tries=tries,
        )
        key = self.auth.get_keys()
        if HAS_M2:
            aes = key.private_decrypt(ret["key"], RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(key)
            aes = cipher.decrypt(ret["key"])
        pcrypt = salt.crypt.Crypticle(self.opts, aes)
        data = pcrypt.loads(ret[dictkey])
        data = salt.transport.frame.decode_embedded_strs(data)
        raise salt.ext.tornado.gen.Return(data)

    @salt.ext.tornado.gen.coroutine
    def _crypted_transfer(self, load, tries=3, timeout=60):
        """
        In case of authentication errors, try to renegotiate authentication
        and retry the method.
        Indeed, we can fail too early in case of a master restart during a
        minion state execution call
        """

        @salt.ext.tornado.gen.coroutine
        def _do_transfer():
            data = yield self.message_client.send(
                self._package_load(self.auth.crypticle.dumps(load)),
                timeout=timeout,
                tries=tries,
            )
            # we may not have always data
            # as for example for saltcall ret submission, this is a blind
            # communication, we do not subscribe to return events, we just
            # upload the results to the master
            if data:
                data = self.auth.crypticle.loads(data)
                data = salt.transport.frame.decode_embedded_strs(data)
            raise salt.ext.tornado.gen.Return(data)

        if not self.auth.authenticated:
            yield self.auth.authenticate()
        try:
            ret = yield _do_transfer()
            raise salt.ext.tornado.gen.Return(ret)
        except salt.crypt.AuthenticationError:
            yield self.auth.authenticate()
            ret = yield _do_transfer()
            raise salt.ext.tornado.gen.Return(ret)

    @salt.ext.tornado.gen.coroutine
    def _uncrypted_transfer(self, load, tries=3, timeout=60):
        ret = yield self.message_client.send(
            self._package_load(load),
            timeout=timeout,
            tries=tries,
        )

        raise salt.ext.tornado.gen.Return(ret)

    @salt.ext.tornado.gen.coroutine
    def send(self, load, tries=3, timeout=60, raw=False):
        """
        Send a request, return a future which will complete when we send the message
        """
        try:
            if self.crypt == "clear":
                ret = yield self._uncrypted_transfer(load, tries=tries, timeout=timeout)
            else:
                ret = yield self._crypted_transfer(load, tries=tries, timeout=timeout)
        except salt.ext.tornado.iostream.StreamClosedError:
            # Convert to 'SaltClientError' so that clients can handle this
            # exception more appropriately.
            raise SaltClientError("Connection to master lost")
        raise salt.ext.tornado.gen.Return(ret)


class AsyncTCPPubChannel(
    salt.transport.mixins.auth.AESPubClientMixin, salt.transport.client.AsyncPubChannel
):
    async_methods = [
        "send_id",
        "connect_callback",
        "connect",
    ]
    close_methods = [
        "close",
    ]

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.crypt = kwargs.get("crypt", "aes")
        self.io_loop = kwargs.get("io_loop") or salt.ext.tornado.ioloop.IOLoop.current()
        self.connected = False
        self._closing = False
        self._reconnected = False
        self.message_client = None
        self.event = salt.utils.event.get_event("minion", opts=self.opts, listen=False)

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.message_client is not None:
            self.message_client.close()
            self.message_client = None
        if self.event is not None:
            self.event.destroy()
            self.event = None

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    def _package_load(self, load):
        return {
            "enc": self.crypt,
            "load": load,
        }

    @salt.ext.tornado.gen.coroutine
    def send_id(self, tok, force_auth):
        """
        Send the minion id to the master so that the master may better
        track the connection state of the minion.
        In case of authentication errors, try to renegotiate authentication
        and retry the method.
        """
        load = {"id": self.opts["id"], "tok": tok}

        @salt.ext.tornado.gen.coroutine
        def _do_transfer():
            msg = self._package_load(self.auth.crypticle.dumps(load))
            package = salt.transport.frame.frame_msg(msg, header=None)
            yield self.message_client.write_to_stream(package)
            raise salt.ext.tornado.gen.Return(True)

        if force_auth or not self.auth.authenticated:
            count = 0
            while (
                count <= self.opts["tcp_authentication_retries"]
                or self.opts["tcp_authentication_retries"] < 0
            ):
                try:
                    yield self.auth.authenticate()
                    break
                except SaltClientError as exc:
                    log.debug(exc)
                    count += 1
        try:
            ret = yield _do_transfer()
            raise salt.ext.tornado.gen.Return(ret)
        except salt.crypt.AuthenticationError:
            yield self.auth.authenticate()
            ret = yield _do_transfer()
            raise salt.ext.tornado.gen.Return(ret)

    @salt.ext.tornado.gen.coroutine
    def connect_callback(self, result):
        if self._closing:
            return
        # Force re-auth on reconnect since the master
        # may have been restarted
        yield self.send_id(self.tok, self._reconnected)
        self.connected = True
        self.event.fire_event({"master": self.opts["master"]}, "__master_connected")
        if self._reconnected:
            # On reconnects, fire a master event to notify that the minion is
            # available.
            if self.opts.get("__role") == "syndic":
                data = "Syndic {} started at {}".format(self.opts["id"], time.asctime())
                tag = salt.utils.event.tagify([self.opts["id"], "start"], "syndic")
            else:
                data = "Minion {} started at {}".format(self.opts["id"], time.asctime())
                tag = salt.utils.event.tagify([self.opts["id"], "start"], "minion")
            load = {
                "id": self.opts["id"],
                "cmd": "_minion_event",
                "pretag": None,
                "tok": self.tok,
                "data": data,
                "tag": tag,
            }
            req_channel = salt.utils.asynchronous.SyncWrapper(
                AsyncTCPReqChannel,
                (self.opts,),
                loop_kwarg="io_loop",
            )
            try:
                req_channel.send(load, timeout=60)
            except salt.exceptions.SaltReqTimeoutError:
                log.info(
                    "fire_master failed: master could not be contacted. Request timed"
                    " out."
                )
            except Exception:  # pylint: disable=broad-except
                log.info("fire_master failed: %s", traceback.format_exc())
            finally:
                # SyncWrapper will call either close() or destroy(), whichever is available
                del req_channel
        else:
            self._reconnected = True

    def disconnect_callback(self):
        if self._closing:
            return
        self.connected = False
        self.event.fire_event({"master": self.opts["master"]}, "__master_disconnected")

    @salt.ext.tornado.gen.coroutine
    def connect(self):
        try:
            self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)
            self.tok = self.auth.gen_token(b"salt")
            if not self.auth.authenticated:
                yield self.auth.authenticate()
            if self.auth.authenticated:
                # if this is changed from the default, we assume it was intentional
                if int(self.opts.get("publish_port", 4505)) != 4505:
                    self.publish_port = self.opts.get("publish_port")
                # else take the relayed publish_port master reports
                else:
                    self.publish_port = self.auth.creds["publish_port"]

                self.message_client = SaltMessageClientPool(
                    self.opts,
                    args=(self.opts, self.opts["master_ip"], int(self.publish_port)),
                    kwargs={
                        "io_loop": self.io_loop,
                        "connect_callback": self.connect_callback,
                        "disconnect_callback": self.disconnect_callback,
                        "source_ip": self.opts.get("source_ip"),
                        "source_port": self.opts.get("source_publish_port"),
                    },
                )
                yield self.message_client.connect()  # wait for the client to be connected
                self.connected = True
        # TODO: better exception handling...
        except KeyboardInterrupt:  # pylint: disable=try-except-raise
            raise
        except Exception as exc:  # pylint: disable=broad-except
            if "-|RETRY|-" not in str(exc):
                raise SaltClientError(
                    "Unable to sign_in to master: {}".format(exc)
                )  # TODO: better error message

    def on_recv(self, callback):
        """
        Register an on_recv callback
        """
        if callback is None:
            return self.message_client.on_recv(callback)

        @salt.ext.tornado.gen.coroutine
        def wrap_callback(body):
            if not isinstance(body, dict):
                # TODO: For some reason we need to decode here for things
                #       to work. Fix this.
                body = salt.utils.msgpack.loads(body)
                body = salt.transport.frame.decode_embedded_strs(body)
            ret = yield self._decode_payload(body)
            callback(ret)

        return self.message_client.on_recv(wrap_callback)


class TCPReqServerChannel(
    salt.transport.mixins.auth.AESReqServerMixin, salt.transport.server.ReqServerChannel
):
    # TODO: opts!
    backlog = 5

    def __init__(self, opts):
        salt.transport.server.ReqServerChannel.__init__(self, opts)
        self._socket = None
        self.req_server = None

    @property
    def socket(self):
        return self._socket

    def close(self):
        if self._socket is not None:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError as exc:
                if exc.errno == errno.ENOTCONN:
                    # We may try to shutdown a socket which is already disconnected.
                    # Ignore this condition and continue.
                    pass
                else:
                    raise
            if self.req_server is None:
                # We only close the socket if we don't have a req_server instance.
                # If we did, because the req_server is also handling this socket, when we call
                # req_server.stop(), tornado will give us an AssertionError because it's trying to
                # match the socket.fileno() (after close it's -1) to the fd it holds on it's _sockets cache
                # so it can remove the socket from the IOLoop handlers
                self._socket.close()
            self._socket = None
        if self.req_server is not None:
            try:
                self.req_server.close()
            except OSError as exc:
                if exc.errno != 9:
                    raise
                log.exception(
                    "TCPReqServerChannel close generated an exception: %s", str(exc)
                )
            self.req_server = None

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def pre_fork(self, process_manager):
        """
        Pre-fork we need to create the zmq router device
        """
        salt.transport.mixins.auth.AESReqServerMixin.pre_fork(self, process_manager)
        if USE_LOAD_BALANCER:
            self.socket_queue = multiprocessing.Queue()
            process_manager.add_process(
                LoadBalancerServer, args=(self.opts, self.socket_queue)
            )
        elif not salt.utils.platform.is_windows():
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _set_tcp_keepalive(self._socket, self.opts)
            self._socket.setblocking(0)
            self._socket.bind((self.opts["interface"], int(self.opts["ret_port"])))

    def post_fork(self, payload_handler, io_loop):
        """
        After forking we need to create all of the local sockets to listen to the
        router

        payload_handler: function to call with your payloads
        """
        if self.opts["pub_server_niceness"] and not salt.utils.platform.is_windows():
            log.info(
                "setting Publish daemon niceness to %i",
                self.opts["pub_server_niceness"],
            )
            os.nice(self.opts["pub_server_niceness"])

        self.payload_handler = payload_handler
        self.io_loop = io_loop
        with salt.utils.asynchronous.current_ioloop(self.io_loop):
            if USE_LOAD_BALANCER:
                self.req_server = LoadBalancerWorker(
                    self.socket_queue,
                    self.handle_message,
                    ssl_options=self.opts.get("ssl"),
                )
            else:
                if salt.utils.platform.is_windows():
                    self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    _set_tcp_keepalive(self._socket, self.opts)
                    self._socket.setblocking(0)
                    self._socket.bind(
                        (self.opts["interface"], int(self.opts["ret_port"]))
                    )
                self.req_server = SaltMessageServer(
                    self.handle_message,
                    ssl_options=self.opts.get("ssl"),
                    io_loop=self.io_loop,
                )
                self.req_server.add_socket(self._socket)
                self._socket.listen(self.backlog)
        salt.transport.mixins.auth.AESReqServerMixin.post_fork(
            self, payload_handler, io_loop
        )

    @salt.ext.tornado.gen.coroutine
    def handle_message(self, stream, header, payload):
        """
        Handle incoming messages from underlying tcp streams
        """
        try:
            try:
                payload = self._decode_payload(payload)
            except Exception:  # pylint: disable=broad-except
                stream.write(salt.transport.frame.frame_msg("bad load", header=header))
                raise salt.ext.tornado.gen.Return()

            # TODO helper functions to normalize payload?
            if not isinstance(payload, dict) or not isinstance(
                payload.get("load"), dict
            ):
                yield stream.write(
                    salt.transport.frame.frame_msg(
                        "payload and load must be a dict", header=header
                    )
                )
                raise salt.ext.tornado.gen.Return()

            try:
                id_ = payload["load"].get("id", "")
                if "\0" in id_:
                    log.error("Payload contains an id with a null byte: %s", payload)
                    stream.send(salt.payload.dumps("bad load: id contains a null byte"))
                    raise salt.ext.tornado.gen.Return()
            except TypeError:
                log.error("Payload contains non-string id: %s", payload)
                stream.send(
                    salt.payload.dumps("bad load: id {} is not a string".format(id_))
                )
                raise salt.ext.tornado.gen.Return()

            # intercept the "_auth" commands, since the main daemon shouldn't know
            # anything about our key auth
            if (
                payload["enc"] == "clear"
                and payload.get("load", {}).get("cmd") == "_auth"
            ):
                yield stream.write(
                    salt.transport.frame.frame_msg(
                        self._auth(payload["load"]), header=header
                    )
                )
                raise salt.ext.tornado.gen.Return()

            # TODO: test
            try:
                ret, req_opts = yield self.payload_handler(payload)
            except Exception as e:  # pylint: disable=broad-except
                # always attempt to return an error to the minion
                stream.write("Some exception handling minion payload")
                log.error(
                    "Some exception handling a payload from minion", exc_info=True
                )
                stream.close()
                raise salt.ext.tornado.gen.Return()

            req_fun = req_opts.get("fun", "send")
            if req_fun == "send_clear":
                stream.write(salt.transport.frame.frame_msg(ret, header=header))
            elif req_fun == "send":
                stream.write(
                    salt.transport.frame.frame_msg(
                        self.crypticle.dumps(ret), header=header
                    )
                )
            elif req_fun == "send_private":
                stream.write(
                    salt.transport.frame.frame_msg(
                        self._encrypt_private(
                            ret,
                            req_opts["key"],
                            req_opts["tgt"],
                        ),
                        header=header,
                    )
                )
            else:
                log.error("Unknown req_fun %s", req_fun)
                # always attempt to return an error to the minion
                stream.write("Server-side exception handling payload")
                stream.close()
        except salt.ext.tornado.gen.Return:
            raise
        except salt.ext.tornado.iostream.StreamClosedError:
            # Stream was closed. This could happen if the remote side
            # closed the connection on its end (eg in a timeout or shutdown
            # situation).
            log.error("Connection was unexpectedly closed", exc_info=True)
        except Exception as exc:  # pylint: disable=broad-except
            # Absorb any other exceptions
            log.error("Unexpected exception occurred: %s", exc, exc_info=True)

        raise salt.ext.tornado.gen.Return()


class SaltMessageServer(salt.ext.tornado.tcpserver.TCPServer):
    """
    Raw TCP server which will receive all of the TCP streams and re-assemble
    messages that are sent through to us
    """

    def __init__(self, message_handler, *args, **kwargs):
        io_loop = (
            kwargs.pop("io_loop", None) or salt.ext.tornado.ioloop.IOLoop.current()
        )
        self._closing = False
        super().__init__(*args, **kwargs)
        self.io_loop = io_loop
        self.clients = []
        self.message_handler = message_handler

    @salt.ext.tornado.gen.coroutine
    def handle_stream(self, stream, address):
        """
        Handle incoming streams and add messages to the incoming queue
        """
        log.trace("Req client %s connected", address)
        self.clients.append((stream, address))
        unpacker = salt.utils.msgpack.Unpacker()
        try:
            while True:
                wire_bytes = yield stream.read_bytes(4096, partial=True)
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    header = framed_msg["head"]
                    self.io_loop.spawn_callback(
                        self.message_handler, stream, header, framed_msg["body"]
                    )
        except salt.ext.tornado.iostream.StreamClosedError:
            log.trace("req client disconnected %s", address)
            self.remove_client((stream, address))
        except Exception as e:  # pylint: disable=broad-except
            log.trace("other master-side exception: %s", e)
            self.remove_client((stream, address))
            stream.close()

    def remove_client(self, client):
        try:
            self.clients.remove(client)
        except ValueError:
            log.trace("Message server client was not in list to remove")

    def shutdown(self):
        """
        Shutdown the whole server
        """
        salt.utils.versions.warn_until(
            "Phosphorus",
            "Please stop calling {0}.{1}.shutdown() and instead call {0}.{1}.close()".format(
                __name__, self.__class__.__name__
            ),
        )
        self.close()

    def close(self):
        """
        Close the server
        """
        if self._closing:
            return
        self._closing = True
        for item in self.clients:
            client, address = item
            client.close()
            self.remove_client(item)
        try:
            self.stop()
        except OSError as exc:
            if exc.errno != 9:
                raise


if USE_LOAD_BALANCER:

    class LoadBalancerWorker(SaltMessageServer):
        """
        This will receive TCP connections from 'LoadBalancerServer' via
        a multiprocessing queue.
        Since the queue is shared amongst workers, only one worker will handle
        a given connection.
        """

        def __init__(self, socket_queue, message_handler, *args, **kwargs):
            super().__init__(message_handler, *args, **kwargs)
            self.socket_queue = socket_queue
            self._stop = threading.Event()
            self.thread = threading.Thread(target=self.socket_queue_thread)
            self.thread.start()

        def stop(self):
            salt.utils.versions.warn_until(
                "Phosphorus",
                "Please stop calling {0}.{1}.stop() and instead call {0}.{1}.close()".format(
                    __name__, self.__class__.__name__
                ),
            )
            self.close()

        def close(self):
            self._stop.set()
            self.thread.join()
            super().close()

        def socket_queue_thread(self):
            try:
                while True:
                    try:
                        client_socket, address = self.socket_queue.get(True, 1)
                    except queue.Empty:
                        if self._stop.is_set():
                            break
                        continue
                    # 'self.io_loop' initialized in super class
                    # 'salt.ext.tornado.tcpserver.TCPServer'.
                    # 'self._handle_connection' defined in same super class.
                    self.io_loop.spawn_callback(
                        self._handle_connection, client_socket, address
                    )
            except (KeyboardInterrupt, SystemExit):
                pass


class TCPClientKeepAlive(salt.ext.tornado.tcpclient.TCPClient):
    """
    Override _create_stream() in TCPClient to enable keep alive support.
    """

    def __init__(self, opts, resolver=None):
        self.opts = opts
        super().__init__(resolver=resolver)

    def _create_stream(
        self, max_buffer_size, af, addr, **kwargs
    ):  # pylint: disable=unused-argument,arguments-differ
        """
        Override _create_stream() in TCPClient.

        Tornado 4.5 added the kwargs 'source_ip' and 'source_port'.
        Due to this, use **kwargs to swallow these and any future
        kwargs to maintain compatibility.
        """
        # Always connect in plaintext; we'll convert to ssl if necessary
        # after one connection has completed.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _set_tcp_keepalive(sock, self.opts)
        stream = salt.ext.tornado.iostream.IOStream(
            sock, max_buffer_size=max_buffer_size
        )
        if salt.ext.tornado.version_info < (5,):
            return stream.connect(addr)
        return stream, stream.connect(addr)


class SaltMessageClientPool(salt.transport.MessageClientPool):
    """
    Wrapper class of SaltMessageClient to avoid blocking waiting while writing data to socket.
    """

    def __init__(self, opts, args=None, kwargs=None):
        super().__init__(SaltMessageClient, opts, args=args, kwargs=kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    def close(self):
        for message_client in self.message_clients:
            message_client.close()
        self.message_clients = []

    @salt.ext.tornado.gen.coroutine
    def connect(self):
        futures = []
        for message_client in self.message_clients:
            futures.append(message_client.connect())
        yield futures
        raise salt.ext.tornado.gen.Return(None)

    def on_recv(self, *args, **kwargs):
        for message_client in self.message_clients:
            message_client.on_recv(*args, **kwargs)

    def send(self, *args, **kwargs):
        message_clients = sorted(self.message_clients, key=lambda x: len(x.send_queue))
        return message_clients[0].send(*args, **kwargs)

    def write_to_stream(self, *args, **kwargs):
        message_clients = sorted(self.message_clients, key=lambda x: len(x.send_queue))
        return message_clients[0]._stream.write(*args, **kwargs)


# TODO consolidate with IPCClient
# TODO: limit in-flight messages.
# TODO: singleton? Something to not re-create the tcp connection so much
class SaltMessageClient:
    """
    Low-level message sending client
    """

    def __init__(
        self,
        opts,
        host,
        port,
        io_loop=None,
        resolver=None,
        connect_callback=None,
        disconnect_callback=None,
        source_ip=None,
        source_port=None,
    ):
        self.opts = opts
        self.host = host
        self.port = port
        self.source_ip = source_ip
        self.source_port = source_port
        self.connect_callback = connect_callback
        self.disconnect_callback = disconnect_callback

        self.io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop.current()

        with salt.utils.asynchronous.current_ioloop(self.io_loop):
            self._tcp_client = TCPClientKeepAlive(opts, resolver=resolver)

        self._mid = 1
        self._max_messages = int((1 << 31) - 2)  # number of IDs before we wrap

        # TODO: max queue size
        self.send_queue = []  # queue of messages to be sent
        self.send_future_map = {}  # mapping of request_id -> Future
        self.send_timeout_map = {}  # request_id -> timeout_callback

        self._read_until_future = None
        self._on_recv = None
        self._closing = False
        self._connecting_future = self.connect()
        self._stream_return_future = salt.ext.tornado.concurrent.Future()
        self.io_loop.spawn_callback(self._stream_return)

        self.backoff = opts.get("tcp_reconnect_backoff", 1)

    def _stop_io_loop(self):
        if self.io_loop is not None:
            self.io_loop.stop()

    # TODO: timeout inflight sessions
    def close(self):
        if self._closing:
            return
        self._closing = True
        if hasattr(self, "_stream") and not self._stream.closed():
            # If _stream_return() hasn't completed, it means the IO
            # Loop is stopped (such as when using
            # 'salt.utils.asynchronous.SyncWrapper'). Ensure that
            # _stream_return() completes by restarting the IO Loop.
            # This will prevent potential errors on shutdown.
            try:
                orig_loop = salt.ext.tornado.ioloop.IOLoop.current()
                self.io_loop.make_current()
                self._stream.close()
                if self._read_until_future is not None:
                    # This will prevent this message from showing up:
                    # '[ERROR   ] Future exception was never retrieved:
                    # StreamClosedError'
                    # This happens because the logic is always waiting to read
                    # the next message and the associated read future is marked
                    # 'StreamClosedError' when the stream is closed.
                    if self._read_until_future.done():
                        self._read_until_future.exception()
                    if (
                        self.io_loop
                        != salt.ext.tornado.ioloop.IOLoop.current(instance=False)
                        or not self._stream_return_future.done()
                    ):
                        self.io_loop.add_future(
                            self._stream_return_future,
                            lambda future: self._stop_io_loop(),
                        )
                        self.io_loop.start()
            except Exception as e:  # pylint: disable=broad-except
                log.info("Exception caught in SaltMessageClient.close: %s", str(e))
            finally:
                orig_loop.make_current()
        self._tcp_client.close()
        self.io_loop = None
        self._read_until_future = None
        # Clear callback references to allow the object that they belong to
        # to be deleted.
        self.connect_callback = None
        self.disconnect_callback = None

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    def connect(self):
        """
        Ask for this client to reconnect to the origin
        """
        if hasattr(self, "_connecting_future") and not self._connecting_future.done():
            future = self._connecting_future
        else:
            future = salt.ext.tornado.concurrent.Future()
            self._connecting_future = future
            self.io_loop.add_callback(self._connect)

            # Add the callback only when a new future is created
            if self.connect_callback is not None:

                def handle_future(future):
                    response = future.result()
                    self.io_loop.add_callback(self.connect_callback, response)

                future.add_done_callback(handle_future)

        return future

    @salt.ext.tornado.gen.coroutine
    def _connect(self):
        """
        Try to connect for the rest of time!
        """
        while True:
            if self._closing:
                break
            try:
                kwargs = {}
                if self.source_ip or self.source_port:
                    if salt.ext.tornado.version_info >= (4, 5):
                        ### source_ip and source_port are supported only in Tornado >= 4.5
                        # See http://www.tornadoweb.org/en/stable/releases/v4.5.0.html
                        # Otherwise will just ignore these args
                        kwargs = {
                            "source_ip": self.source_ip,
                            "source_port": self.source_port,
                        }
                    else:
                        log.warning(
                            "If you need a certain source IP/port, consider upgrading"
                            " Tornado >= 4.5"
                        )
                with salt.utils.asynchronous.current_ioloop(self.io_loop):
                    self._stream = yield self._tcp_client.connect(
                        self.host, self.port, ssl_options=self.opts.get("ssl"), **kwargs
                    )
                self._connecting_future.set_result(True)
                break
            except Exception as exc:  # pylint: disable=broad-except
                log.warning(
                    "TCP Message Client encountered an exception while connecting to"
                    " %s:%s: %r, will reconnect in %d seconds",
                    self.host,
                    self.port,
                    exc,
                    self.backoff,
                )
                yield salt.ext.tornado.gen.sleep(self.backoff)
                # self._connecting_future.set_exception(exc)

    @salt.ext.tornado.gen.coroutine
    def _stream_return(self):
        try:
            while not self._closing and (
                not self._connecting_future.done()
                or self._connecting_future.result() is not True
            ):
                yield self._connecting_future
            unpacker = salt.utils.msgpack.Unpacker()
            while not self._closing:
                try:
                    self._read_until_future = self._stream.read_bytes(
                        4096, partial=True
                    )
                    wire_bytes = yield self._read_until_future
                    unpacker.feed(wire_bytes)
                    for framed_msg in unpacker:
                        framed_msg = salt.transport.frame.decode_embedded_strs(
                            framed_msg
                        )
                        header = framed_msg["head"]
                        body = framed_msg["body"]
                        message_id = header.get("mid")

                        if message_id in self.send_future_map:
                            self.send_future_map.pop(message_id).set_result(body)
                            self.remove_message_timeout(message_id)
                        else:
                            if self._on_recv is not None:
                                self.io_loop.spawn_callback(self._on_recv, header, body)
                            else:
                                log.error(
                                    "Got response for message_id %s that we are not"
                                    " tracking",
                                    message_id,
                                )
                except salt.ext.tornado.iostream.StreamClosedError as e:
                    log.debug(
                        "tcp stream to %s:%s closed, unable to recv",
                        self.host,
                        self.port,
                    )
                    for future in self.send_future_map.values():
                        future.set_exception(e)
                    self.send_future_map = {}
                    if self._closing:
                        return
                    if self.disconnect_callback:
                        self.disconnect_callback()
                    # if the last connect finished, then we need to make a new one
                    if self._connecting_future.done():
                        self._connecting_future = self.connect()
                    yield self._connecting_future
                except TypeError:
                    # This is an invalid transport
                    if "detect_mode" in self.opts:
                        log.info(
                            "There was an error trying to use TCP transport; "
                            "attempting to fallback to another transport"
                        )
                    else:
                        raise SaltClientError
                except Exception as e:  # pylint: disable=broad-except
                    log.error("Exception parsing response", exc_info=True)
                    for future in self.send_future_map.values():
                        future.set_exception(e)
                    self.send_future_map = {}
                    if self._closing:
                        return
                    if self.disconnect_callback:
                        self.disconnect_callback()
                    # if the last connect finished, then we need to make a new one
                    if self._connecting_future.done():
                        self._connecting_future = self.connect()
                    yield self._connecting_future
        finally:
            self._stream_return_future.set_result(True)

    @salt.ext.tornado.gen.coroutine
    def _stream_send(self):
        while (
            not self._connecting_future.done()
            or self._connecting_future.result() is not True
        ):
            yield self._connecting_future
        while len(self.send_queue) > 0:
            message_id, item = self.send_queue[0]
            try:
                yield self._stream.write(item)
                del self.send_queue[0]
            # if the connection is dead, lets fail this send, and make sure we
            # attempt to reconnect
            except salt.ext.tornado.iostream.StreamClosedError as e:
                if message_id in self.send_future_map:
                    self.send_future_map.pop(message_id).set_exception(e)
                self.remove_message_timeout(message_id)
                del self.send_queue[0]
                if self._closing:
                    return
                if self.disconnect_callback:
                    self.disconnect_callback()
                # if the last connect finished, then we need to make a new one
                if self._connecting_future.done():
                    self._connecting_future = self.connect()
                yield self._connecting_future

    def _message_id(self):
        wrap = False
        while self._mid in self.send_future_map:
            if self._mid >= self._max_messages:
                if wrap:
                    # this shouldn't ever happen, but just in case
                    raise Exception("Unable to find available messageid")
                self._mid = 1
                wrap = True
            else:
                self._mid += 1

        return self._mid

    # TODO: return a message object which takes care of multiplexing?
    def on_recv(self, callback):
        """
        Register a callback for received messages (that we didn't initiate)
        """
        if callback is None:
            self._on_recv = callback
        else:

            def wrap_recv(header, body):
                callback(body)

            self._on_recv = wrap_recv

    def remove_message_timeout(self, message_id):
        if message_id not in self.send_timeout_map:
            return
        timeout = self.send_timeout_map.pop(message_id)
        self.io_loop.remove_timeout(timeout)

    def timeout_message(self, message_id, msg):
        if message_id in self.send_timeout_map:
            del self.send_timeout_map[message_id]
        if message_id in self.send_future_map:
            future = self.send_future_map.pop(message_id)
            # In a race condition the message might have been sent by the time
            # we're timing it out. Make sure the future is not None
            if future is not None:
                if future.attempts < future.tries:
                    future.attempts += 1

                    log.debug(
                        "SaltReqTimeoutError, retrying. (%s/%s)",
                        future.attempts,
                        future.tries,
                    )
                    self.send(
                        msg,
                        timeout=future.timeout,
                        tries=future.tries,
                        future=future,
                    )

                else:
                    future.set_exception(SaltReqTimeoutError("Message timed out"))

    def send(self, msg, timeout=None, callback=None, raw=False, future=None, tries=3):
        """
        Send given message, and return a future
        """
        message_id = self._message_id()
        header = {"mid": message_id}

        if future is None:
            future = salt.ext.tornado.concurrent.Future()
            future.tries = tries
            future.attempts = 0
            future.timeout = timeout

        if callback is not None:

            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)

            future.add_done_callback(handle_future)
        # Add this future to the mapping
        self.send_future_map[message_id] = future

        if self.opts.get("detect_mode") is True:
            timeout = 1

        if timeout is not None:
            send_timeout = self.io_loop.call_later(
                timeout, self.timeout_message, message_id, msg
            )
            self.send_timeout_map[message_id] = send_timeout

        # if we don't have a send queue, we need to spawn the callback to do the sending
        if len(self.send_queue) == 0:
            self.io_loop.spawn_callback(self._stream_send)
        self.send_queue.append(
            (message_id, salt.transport.frame.frame_msg(msg, header=header))
        )
        return future


class Subscriber:
    """
    Client object for use with the TCP publisher server
    """

    def __init__(self, stream, address):
        self.stream = stream
        self.address = address
        self._closing = False
        self._read_until_future = None
        self.id_ = None

    def close(self):
        if self._closing:
            return
        self._closing = True
        if not self.stream.closed():
            self.stream.close()
            if self._read_until_future is not None and self._read_until_future.done():
                # This will prevent this message from showing up:
                # '[ERROR   ] Future exception was never retrieved:
                # StreamClosedError'
                # This happens because the logic is always waiting to read
                # the next message and the associated read future is marked
                # 'StreamClosedError' when the stream is closed.
                self._read_until_future.exception()

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701


class PubServer(salt.ext.tornado.tcpserver.TCPServer):
    """
    TCP publisher
    """

    def __init__(self, opts, io_loop=None):
        super().__init__(ssl_options=opts.get("ssl"))
        self.io_loop = io_loop
        self.opts = opts
        self._closing = False
        self.clients = set()
        self.aes_funcs = salt.master.AESFuncs(self.opts)
        self.present = {}
        self.event = None
        self.presence_events = False
        if self.opts.get("presence_events", False):
            tcp_only = True
            for transport, _ in iter_transport_opts(self.opts):
                if transport != "tcp":
                    tcp_only = False
            if tcp_only:
                # Only when the transport is TCP only, the presence events will
                # be handled here. Otherwise, it will be handled in the
                # 'Maintenance' process.
                self.presence_events = True

        if self.presence_events:
            self.event = salt.utils.event.get_event(
                "master", opts=self.opts, listen=False
            )
        else:
            self.event = None

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.event is not None:
            self.event.destroy()
            self.event = None
        if self.aes_funcs is not None:
            self.aes_funcs.destroy()
            self.aes_funcs = None

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    def _add_client_present(self, client):
        id_ = client.id_
        if id_ in self.present:
            clients = self.present[id_]
            clients.add(client)
        else:
            self.present[id_] = {client}
            if self.presence_events:
                data = {"new": [id_], "lost": []}
                self.event.fire_event(
                    data, salt.utils.event.tagify("change", "presence")
                )
                data = {"present": list(self.present.keys())}
                self.event.fire_event(
                    data, salt.utils.event.tagify("present", "presence")
                )

    def _remove_client_present(self, client):
        id_ = client.id_
        if id_ is None or id_ not in self.present:
            # This is possible if _remove_client_present() is invoked
            # before the minion's id is validated.
            return

        clients = self.present[id_]
        if client not in clients:
            # Since _remove_client_present() is potentially called from
            # _stream_read() and/or publish_payload(), it is possible for
            # it to be called twice, in which case we will get here.
            # This is not an abnormal case, so no logging is required.
            return

        clients.remove(client)
        if len(clients) == 0:
            del self.present[id_]
            if self.presence_events:
                data = {"new": [], "lost": [id_]}
                self.event.fire_event(
                    data, salt.utils.event.tagify("change", "presence")
                )
                data = {"present": list(self.present.keys())}
                self.event.fire_event(
                    data, salt.utils.event.tagify("present", "presence")
                )

    @salt.ext.tornado.gen.coroutine
    def _stream_read(self, client):
        unpacker = salt.utils.msgpack.Unpacker()
        while not self._closing:
            try:
                client._read_until_future = client.stream.read_bytes(4096, partial=True)
                wire_bytes = yield client._read_until_future
                unpacker.feed(wire_bytes)
                for framed_msg in unpacker:
                    framed_msg = salt.transport.frame.decode_embedded_strs(framed_msg)
                    body = framed_msg["body"]
                    if body["enc"] != "aes":
                        # We only accept 'aes' encoded messages for 'id'
                        continue
                    crypticle = salt.crypt.Crypticle(
                        self.opts, salt.master.SMaster.secrets["aes"]["secret"].value
                    )
                    load = crypticle.loads(body["load"])
                    load = salt.transport.frame.decode_embedded_strs(load)
                    if not self.aes_funcs.verify_minion(load["id"], load["tok"]):
                        continue
                    client.id_ = load["id"]
                    self._add_client_present(client)
            except salt.ext.tornado.iostream.StreamClosedError as e:
                log.debug("tcp stream to %s closed, unable to recv", client.address)
                client.close()
                self._remove_client_present(client)
                self.clients.discard(client)
                break
            except Exception as e:  # pylint: disable=broad-except
                log.error(
                    "Exception parsing response from %s", client.address, exc_info=True
                )
                continue

    def handle_stream(self, stream, address):
        log.trace("Subscriber at %s connected", address)
        client = Subscriber(stream, address)
        self.clients.add(client)
        self.io_loop.spawn_callback(self._stream_read, client)

    # TODO: ACK the publish through IPC
    @salt.ext.tornado.gen.coroutine
    def publish_payload(self, package, _):
        log.debug("TCP PubServer sending payload: %s", package)
        payload = salt.transport.frame.frame_msg(package["payload"])

        to_remove = []
        if "topic_lst" in package:
            topic_lst = package["topic_lst"]
            for topic in topic_lst:
                if topic in self.present:
                    # This will rarely be a list of more than 1 item. It will
                    # be more than 1 item if the minion disconnects from the
                    # master in an unclean manner (eg cable yank), then
                    # restarts and the master is yet to detect the disconnect
                    # via TCP keep-alive.
                    for client in self.present[topic]:
                        try:
                            # Write the packed str
                            f = client.stream.write(payload)
                            self.io_loop.add_future(f, lambda f: True)
                        except salt.ext.tornado.iostream.StreamClosedError:
                            to_remove.append(client)
                else:
                    log.debug("Publish target %s not connected", topic)
        else:
            for client in self.clients:
                try:
                    # Write the packed str
                    f = client.stream.write(payload)
                    self.io_loop.add_future(f, lambda f: True)
                except salt.ext.tornado.iostream.StreamClosedError:
                    to_remove.append(client)
        for client in to_remove:
            log.debug(
                "Subscriber at %s has disconnected from publisher", client.address
            )
            client.close()
            self._remove_client_present(client)
            self.clients.discard(client)
        log.trace("TCP PubServer finished publishing payload")


class TCPPubServerChannel(salt.transport.server.PubServerChannel):
    # TODO: opts!
    # Based on default used in salt.ext.tornado.netutil.bind_sockets()
    backlog = 128

    def __init__(self, opts):
        self.opts = opts
        self.ckminions = salt.utils.minions.CkMinions(opts)
        self.io_loop = None

    def __setstate__(self, state):
        salt.master.SMaster.secrets = state["secrets"]
        self.__init__(state["opts"])

    def __getstate__(self):
        return {"opts": self.opts, "secrets": salt.master.SMaster.secrets}

    def _publish_daemon(self, **kwargs):
        """
        Bind to the interface specified in the configuration file
        """
        salt.utils.process.appendproctitle(self.__class__.__name__)

        log_queue = kwargs.get("log_queue")
        if log_queue is not None:
            salt.log.setup.set_multiprocessing_logging_queue(log_queue)
        log_queue_level = kwargs.get("log_queue_level")
        if log_queue_level is not None:
            salt.log.setup.set_multiprocessing_logging_level(log_queue_level)
        salt.log.setup.setup_multiprocessing_logging(log_queue)

        # Check if io_loop was set outside
        if self.io_loop is None:
            self.io_loop = salt.ext.tornado.ioloop.IOLoop.current()

        # Spin up the publisher
        pub_server = PubServer(self.opts, io_loop=self.io_loop)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _set_tcp_keepalive(sock, self.opts)
        sock.setblocking(0)
        sock.bind((self.opts["interface"], int(self.opts["publish_port"])))
        sock.listen(self.backlog)
        # pub_server will take ownership of the socket
        pub_server.add_socket(sock)

        # Set up Salt IPC server
        if self.opts.get("ipc_mode", "") == "tcp":
            pull_uri = int(self.opts.get("tcp_master_publish_pull", 4514))
        else:
            pull_uri = os.path.join(self.opts["sock_dir"], "publish_pull.ipc")

        pull_sock = salt.transport.ipc.IPCMessageServer(
            pull_uri,
            io_loop=self.io_loop,
            payload_handler=pub_server.publish_payload,
        )

        # Securely create socket
        log.info("Starting the Salt Puller on %s", pull_uri)
        with salt.utils.files.set_umask(0o177):
            pull_sock.start()

        # run forever
        try:
            self.io_loop.start()
        except (KeyboardInterrupt, SystemExit):
            salt.log.setup.shutdown_multiprocessing_logging()
        finally:
            pull_sock.close()

    def pre_fork(self, process_manager, kwargs=None):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing
        """
        process_manager.add_process(self._publish_daemon, kwargs=kwargs)

    def publish(self, load):
        """
        Publish "load" to minions
        """
        payload = {"enc": "aes"}

        crypticle = salt.crypt.Crypticle(
            self.opts, salt.master.SMaster.secrets["aes"]["secret"].value
        )
        payload["load"] = crypticle.dumps(load)
        if self.opts["sign_pub_messages"]:
            master_pem_path = os.path.join(self.opts["pki_dir"], "master.pem")
            log.debug("Signing data packet")
            payload["sig"] = salt.crypt.sign_message(master_pem_path, payload["load"])
        # Use the Salt IPC server
        if self.opts.get("ipc_mode", "") == "tcp":
            pull_uri = int(self.opts.get("tcp_master_publish_pull", 4514))
        else:
            pull_uri = os.path.join(self.opts["sock_dir"], "publish_pull.ipc")
        # TODO: switch to the actual asynchronous interface
        # pub_sock = salt.transport.ipc.IPCMessageClient(self.opts, io_loop=self.io_loop)
        pub_sock = salt.utils.asynchronous.SyncWrapper(
            salt.transport.ipc.IPCMessageClient,
            (pull_uri,),
            loop_kwarg="io_loop",
        )
        pub_sock.connect()

        int_payload = {"payload": salt.payload.dumps(payload)}

        # add some targeting stuff for lists only (for now)
        if load["tgt_type"] == "list" and not self.opts.get("order_masters", False):
            if isinstance(load["tgt"], str):
                # Fetch a list of minions that match
                _res = self.ckminions.check_minions(
                    load["tgt"], tgt_type=load["tgt_type"]
                )
                match_ids = _res["minions"]

                log.debug("Publish Side Match: %s", match_ids)
                # Send list of miions thru so zmq can target them
                int_payload["topic_lst"] = match_ids
            else:
                int_payload["topic_lst"] = load["tgt"]
        # Send it over IPC!
        pub_sock.send(int_payload)

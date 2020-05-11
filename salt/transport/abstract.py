# -*- coding: utf-8 -*-
"""Abstract transport classes"""

## Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import json
import base64
import errno
import logging
import os
import socket
import sys
import threading
import time
import traceback
import weakref
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from tornado.ioloop import IOLoop
from tornado.queues import Queue
import tempfile

# Import Salt Libs
import salt.crypt
import salt.exceptions

# Import Tornado Libs
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
from salt.exceptions import SaltClientError, SaltReqTimeoutError
from salt.ext import six
from salt.ext.six.moves import queue  # pylint: disable=import-error
from salt.transport import iter_transport_opts

# pylint: disable=import-error,no-name-in-module
if six.PY2:
    import urlparse
else:
    import urllib.parse as urlparse
# pylint: enable=import-error,no-name-in-module

# Import third party libs
try:
    from M2Crypto import RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.Cipher import PKCS1_OAEP
    except ImportError:
        from Crypto.Cipher import PKCS1_OAEP

log = logging.getLogger(__name__)


# TODO: move serial down into message library
class AbstractAsyncReqChannel(salt.transport.client.ReqChannel):
    """
    Encapsulate sending routines to channel.
    Note: this class returns a singleton
    """

    # This class is only a singleton per minion/master pair
    # mapping of io_loop -> {key -> channel}
    instance_map = weakref.WeakKeyDictionary()

    def __new__(cls, opts, **kwargs):
        """
        Only create one instance of channel per __key()
        """
        # do we have any mapping for this io_loop
        io_loop = kwargs.get("io_loop") or salt.ext.tornado.ioloop.IOLoop.current()
        if io_loop not in cls.instance_map:
            cls.instance_map[io_loop] = weakref.WeakValueDictionary()
        loop_instance_map = cls.instance_map[io_loop]

        key = cls.__key(opts, **kwargs)
        obj = loop_instance_map.get(key)
        if obj is None:
            log.debug("Initializing new AbstractAsyncReqChannel for %s", key)
            # we need to make a local variable for this, as we are going to store
            # it in a WeakValueDictionary-- which will remove the item if no one
            # references it-- this forces a reference while we return to the caller
            obj = object.__new__(cls)
            obj.__singleton_init__(opts, **kwargs)
            obj._instance_key = key
            loop_instance_map[key] = obj
            obj._refcount = 1
            obj._refcount_lock = threading.RLock()
        else:
            with obj._refcount_lock:
                obj._refcount += 1
            log.debug("Re-using AbstractAsyncReqChannel for %s", key)
        return obj

    @classmethod
    def __key(cls, opts, **kwargs):
        if "master_uri" in kwargs:
            opts["master_uri"] = kwargs["master_uri"]
        return (
            opts["pki_dir"],  # where the keys are stored
            opts["id"],  # minion ID
            opts["master_uri"],
            kwargs.get("crypt", "aes"),  # TODO: use the same channel for crypt
        )

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts, **kwargs):
        pass

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, **kwargs):
        self.opts = dict(opts)

        self.serial = salt.payload.Serial(self.opts)

        # crypt defaults to 'aes'
        self.crypt = kwargs.get("crypt", "aes")

        self.io_loop = kwargs.get("io_loop") or salt.ext.tornado.ioloop.IOLoop.current()
        kwargs["io_loop"] = self.io_loop

        if self.crypt != "clear":
            self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)

        self.start_channel(**kwargs)

        self._closing = False

    def close(self):
        if self._closing:
            return

        if self._refcount > 1:
            # Decrease refcount
            with self._refcount_lock:
                self._refcount -= 1
            log.debug(
                "This is not the last %s instance. Not closing yet.",
                self.__class__.__name__,
            )
            return

        log.debug("Closing %s instance", self.__class__.__name__)
        self._closing = True

        # Remove the entry from the instance map so that a closed entry may not
        # be reused.
        # This forces this operation even if the reference count of the entry
        # has not yet gone to zero.
        if self.io_loop in self.__class__.instance_map:
            loop_instance_map = self.__class__.instance_map[self.io_loop]
            if self._instance_key in loop_instance_map:
                del loop_instance_map[self._instance_key]
            if not loop_instance_map:
                del self.__class__.instance_map[self.io_loop]

    # pylint: disable=W1701
    def __del__(self):
        with self._refcount_lock:
            # Make sure we actually close no matter if something
            # went wrong with our ref counting
            self._refcount = 1
        self.close()

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
        ret = yield self.publish_dict(
            self._package_load(self.auth.crypticle.dumps(load)), timeout=timeout
        )
        key = self.auth.get_keys()
        if HAS_M2:
            aes = key.private_decrypt(ret["key"], RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(key)
            aes = cipher.decrypt(ret["key"])
        pcrypt = salt.crypt.Crypticle(self.opts, aes)
        data = pcrypt.loads(ret[dictkey])
        if six.PY3:
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
            data = yield self.publish_dict(
                self._package_load(self.auth.crypticle.dumps(load)), timeout=timeout,
            )
            # we may not have always data
            # as for example for saltcall ret submission, this is a blind
            # communication, we do not subscribe to return events, we just
            # upload the results to the master
            if data:
                data = self.auth.crypticle.loads(data)
                if six.PY3:
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
        ret = yield self.publish_dict(
            self._package_load(load), timeout=timeout
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

    def publish_dict(self, dicty, tries=3, timeout=60):
        int_payload = self.serial.dumps(dicty)
        return self.publish_bytes(int_payload)

    def publish_bytes(self, bpayload):
        """Transfer bytes to the minions.

        The default implementation base64 encodes the payload, and calls
        publish_string, for clients which cannot or will not transfer
        binary.
        """
        b64payload = base64.b64encode(bpayload)
        payload_string = b64payload.decode("ascii")
        return self.publish_string(payload_string)

    def publish_string(self, spayload):
        """Transfer a string to the minions."""
        raise NotImplemented()


class AbstractReqServerChannel(
    salt.transport.mixins.auth.AESReqServerMixin, salt.transport.server.ReqServerChannel
):
    def __init__(self, opts):
        salt.transport.server.ReqServerChannel.__init__(self, opts)

    def close(self):
        pass

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    def pre_fork(self, process_manager):
        """
        Pre-fork we need to create the zmq router device
        """
        salt.transport.mixins.auth.AESReqServerMixin.pre_fork(self, process_manager)

    def post_fork(self, payload_handler, io_loop):
        """
        After forking we need to create all of the local sockets to listen to the
        router

        payload_handler: function to call with your payloads
        """
        self.payload_handler = payload_handler
        self.io_loop = io_loop
        self.serial = salt.payload.Serial(self.opts)
        self.start_channel(io_loop)
        salt.transport.mixins.auth.AESReqServerMixin.post_fork(
            self, payload_handler, io_loop
        )

    @salt.ext.tornado.gen.coroutine
    def process_message(self, header, payload, **kwargs):
        """
        Handle incoming messages from underylying channel streams
        """
        try:
            try:
                payload = self._decode_payload(payload)
            except Exception:  # pylint: disable=broad-except
                self.write_bytes(
                    salt.transport.frame.frame_msg("bad load", header=header),
                    **kwargs
                )
                raise salt.ext.tornado.gen.Return()

            # TODO helper functions to normalize payload?
            if not isinstance(payload, dict) or not isinstance(
                payload.get("load"), dict
            ):
                yield self.write_bytes(
                    salt.transport.frame.frame_msg(
                        "payload and load must be a dict", header=header
                    ),
                    **kwargs
                )
                raise salt.ext.tornado.gen.Return()

            try:
                id_ = payload["load"].get("id", "")
                if str("\0") in id_:
                    log.error("Payload contains an id with a null byte: %s", payload)
                    self.write_bytes(
                        self.serial.dumps("bad load: id contains a null byte"),
                        **kwargs
                    )
                    raise salt.ext.tornado.gen.Return()
            except TypeError:
                log.error("Payload contains non-string id: %s", payload)
                self.write_bytes(
                    self.serial.dumps("bad load: id {0} is not a string".format(id_)),
                    **kwargs
                )
                raise salt.ext.tornado.gen.Return()

            # intercept the "_auth" commands, since the main daemon shouldn't know
            # anything about our key auth
            if (
                payload["enc"] == "clear"
                and payload.get("load", {}).get("cmd") == "_auth"
            ):
                yield self.write_bytes(
                    salt.transport.frame.frame_msg(
                        self._auth(payload["load"]), header=header
                    ),
                    **kwargs
                )
                raise salt.ext.tornado.gen.Return()

            # TODO: test
            try:
                ret, req_opts = yield self.payload_handler(payload)
            except Exception as e:  # pylint: disable=broad-except
                # always attempt to return an error to the minion
                self.write_bytes(
                    "Some exception handling minion payload",
                    **kwargs
                )
                log.error(
                    "Some exception handling a payload from minion", exc_info=True
                )
                self.shutdown_processor(**kwargs)
                raise salt.ext.tornado.gen.Return()

            req_fun = req_opts.get("fun", "send")
            if req_fun == "send_clear":
                self.write_bytes(
                    salt.transport.frame.frame_msg(ret, header=header),
                    **kwargs
                )
            elif req_fun == "send":
                self.write_bytes(
                    salt.transport.frame.frame_msg(
                        self.crypticle.dumps(ret), header=header
                    ),
                    **kwargs
                )
            elif req_fun == "send_private":
                self.write_bytes(
                    salt.transport.frame.frame_msg(
                        self._encrypt_private(ret, req_opts["key"], req_opts["tgt"],),
                        header=header,
                    ),
                    **kwargs
                )
            else:
                log.error("Unknown req_fun %s", req_fun)
                # always attempt to return an error to the minion
                self.write_bytes(
                    "Server-side exception handling payload", **kwargs
                )
                self.shutdown_processor(**kwargs)
        except salt.ext.tornado.gen.Return:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            # Absorb any other exceptions
            log.error("Unexpected exception occurred: %s", exc, exc_info=True)

        raise salt.ext.tornado.gen.Return()

    def start_channel(self, io_loop):
        """Start channel for minions to connect to.

        Whenever a message is received process_message should be called with
        the decoded message.
        """
        raise NotImplemented()

    def write_bytes(self, bpayload, **kwargs):
        """Send bytes back to minion as response.

        The kwargs provided to this function are the same start_channel passes
        to process_message to process receieved messages.

        The default implementation base64 encodes the payload, and calls
        publish_string, for clients which cannot or will not transfer
        binary.
        """
        b64payload = base64.b64encode(bpayload)
        payload_string = b64payload.decode("ascii")
        return self.write_string(payload_string, **kwargs)

    def write_string(self, spayload, **kwargs):
        """Send bytes back to minion as response.

        The kwargs provided to this function are the same start_channel passes
        to process_message to process receieved messages.

        This must implemented assuming the write_bytes method is not.
        """
        raise NotImplemented()

    def shutdown_processor(self, **kwargs):
        """Shutdown the specific minion response channel.

        The kwargs provided to this function are the same start_channel passes
        to process_message to process receieved messages.
        """
        pass


class AbstractAsyncPubChannel(
    salt.transport.mixins.auth.AESPubClientMixin, salt.transport.client.AsyncPubChannel
):
    def __init__(self, opts, **kwargs):
        self.opts = opts

        self.serial = salt.payload.Serial(self.opts)

        self.crypt = kwargs.get("crypt", "aes")
        self.io_loop = kwargs.get("io_loop") or salt.ext.tornado.ioloop.IOLoop.current()
        self.connected = False
        self._closing = False
        self._reconnected = False
        self.event = salt.utils.event.get_event("minion", opts=self.opts, listen=False)

    def close(self):
        if self._closing:
            return
        self._closing = True

    # pylint: disable=W1701
    def __del__(self):
        self.close()

    # pylint: enable=W1701

    @salt.ext.tornado.gen.coroutine
    def connect(self):
        try:
            self.auth = salt.crypt.AsyncAuth(self.opts, io_loop=self.io_loop)
            self.tok = self.auth.gen_token(b"salt")
            if not self.auth.authenticated:
                yield self.auth.authenticate()
            if self.auth.authenticated:
                yield self.open_connection()
                self.connected = True
        # TODO: better exception handling...
        except KeyboardInterrupt:  # pylint: disable=try-except-raise
            raise
        except Exception as exc:  # pylint: disable=broad-except
            if "-|RETRY|-" not in six.text_type(exc):
                raise SaltClientError(
                    "Unable to sign_in to master: {0}".format(exc)
                )  # TODO: better error message

    def on_recv(self, callback):
        """
        Register an on_recv callback
        """
        if callback is None:
            return self.set_callback(None)

        @salt.ext.tornado.gen.coroutine
        def wrap_callback(body):
            if not isinstance(body, dict):
                # TODO: For some reason we need to decode here for things
                #       to work. Fix this.
                body = salt.utils.msgpack.loads(body)
                if six.PY3:
                    body = salt.transport.frame.decode_embedded_strs(body)
            ret = yield self._decode_payload(body)
            callback(ret)

        return self.set_callback(wrap_callback)

    @salt.ext.tornado.gen.coroutine
    def open_connection(self):
        raise NotImplemented()

    def set_callback(self, callback):
        raise NotImplemented()


class AbstractPubServerChannel(salt.transport.server.PubServerChannel):
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)  # TODO: in init?
        self.ckminions = salt.utils.minions.CkMinions(opts)
        self.io_loop = None

    def __setstate__(self, state):
        salt.master.SMaster.secrets = state["secrets"]
        self.__init__(state["opts"])

    def __getstate__(self):
        return {"opts": self.opts, "secrets": salt.master.SMaster.secrets}

    def _publish_ipc(self, **kwargs):
        """
        Bind to the interface specified in the configuration file
        """
        salt.utils.process.appendproctitle(self.__class__.__name__ + "ipc")

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

        # Set up Salt IPC server
        if self.opts.get("ipc_mode", "") == "tcp":
            pull_uri = int(self.opts.get("tcp_master_publish_pull", 4514))
        else:
            pull_uri = os.path.join(self.opts["sock_dir"], "publish_pull.ipc")

        pull_sock = salt.transport.ipc.IPCMessageServer(
            pull_uri, io_loop=self.io_loop, payload_handler=self.publish_payload,
        )

        # Securely create socket
        log.info("Starting the Salt Puller on %s", pull_uri)
        with salt.utils.files.set_umask(0o177):
            pull_sock.start()

        self.start_channel(self.io_loop)

        try:
            self.io_loop.start()
        except (KeyboardInterrupt, SystemExit):
            salt.log.setup.shutdown_multiprocessing_logging()

    def pre_fork(self, process_manager, kwargs=None):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing
        """
        process_manager.add_process(self._publish_ipc, kwargs=kwargs)

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
            salt.transport.ipc.IPCMessageClient, (pull_uri,)
        )
        pub_sock.connect()

        int_payload = {"payload": self.serial.dumps(payload)}

        # add some targeting stuff for lists only (for now)
        if load["tgt_type"] == "list" and not self.opts.get("order_masters", False):
            if isinstance(load["tgt"], six.string_types):
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

    def publish_payload(self, package, arg):
        """Transfer package to minions.

        The default implementation fetches the payload from the frame, and
        calls publish_bytes with it, for clients which cannot or will not
        transfer the frame themselves.
        """
        bpayload = salt.transport.frame.frame_msg(package["payload"])
        return self.publish_bytes(bpayload)

    def publish_bytes(self, bpayload):
        """Transfer bytes to the minions.

        The default implementation base64 encodes the payload, and calls
        publish_string, for clients which cannot or will not transfer
        binary.
        """
        b64payload = base64.b64encode(bpayload)
        payload_string = b64payload.decode("ascii")
        return self.publish_string(payload_string)

    def publish_string(self, spayload):
        """Transfer a string to the minions.

        This must implemented assuming none of the other publish_* methods are.
        """
        raise NotImplemented()

    def start_channel(self, io_loop):
        """Start channel for minions to connect to.

        Whenever publish_* is called, the payload should be send to minions,
        whom are connected.
        """
        raise NotImplemented()

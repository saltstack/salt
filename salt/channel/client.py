"""
Encapsulate the different transports available to Salt.

This includes client side transport, for the ReqServer and the Publisher
"""

import logging
import os
import time

import salt.crypt
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.payload
import salt.transport.frame
import salt.utils.event
import salt.utils.files
import salt.utils.minions
import salt.utils.stringutils
import salt.utils.verify
from salt.exceptions import SaltClientError, SaltException
from salt.utils.asynchronous import SyncWrapper

try:
    from M2Crypto import RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.Cipher import PKCS1_OAEP
    except ImportError:
        try:
            from Crypto.Cipher import PKCS1_OAEP  # nosec
        except ImportError:
            pass

log = logging.getLogger(__name__)


class ReqChannel:
    """
    Factory class to create a sychronous communication channels to the master's
    ReqServer. ReqChannels connect to the ReqServer on the ret_port (default:
    4506)
    """

    @staticmethod
    def factory(opts, **kwargs):
        # All Sync interfaces are just wrappers around the Async ones
        return SyncWrapper(
            AsyncReqChannel.factory,
            (opts,),
            kwargs,
            loop_kwarg="io_loop",
        )

    def close(self):
        """
        Close the channel
        """
        raise NotImplementedError()

    def send(self, load, tries=3, timeout=60, raw=False):
        """
        Send "load" to the master.
        """
        raise NotImplementedError()

    def crypted_transfer_decode_dictentry(
        self, load, dictkey=None, tries=3, timeout=60
    ):
        """
        Send "load" to the master in a way that the load is only readable by
        the minion and the master (not other minions etc.)
        """
        raise NotImplementedError()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class PushChannel:
    """
    Factory class to create Sync channel for push side of push/pull IPC
    """

    @staticmethod
    def factory(opts, **kwargs):
        return SyncWrapper(
            AsyncPushChannel.factory,
            (opts,),
            kwargs,
            loop_kwarg="io_loop",
        )

    def send(self, load, tries=3, timeout=60):
        """
        Send load across IPC push
        """
        raise NotImplementedError()


class PullChannel:
    """
    Factory class to create Sync channel for pull side of push/pull IPC
    """

    @staticmethod
    def factory(opts, **kwargs):
        return SyncWrapper(
            AsyncPullChannel.factory,
            (opts,),
            kwargs,
            loop_kwarg="io_loop",
        )


class AsyncReqChannel:
    """
    Factory class to create a asynchronous communication channels to the
    master's ReqServer. ReqChannels connect to the master's ReqServerChannel on
    the minion's master_port (default: 4506) option.
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

    @classmethod
    def factory(cls, opts, **kwargs):
        import salt.ext.tornado.ioloop
        import salt.crypt

        # Default to ZeroMQ for now
        ttype = "zeromq"
        # determine the ttype
        if "transport" in opts:
            ttype = opts["transport"]
        elif "transport" in opts.get("pillar", {}).get("master", {}):
            ttype = opts["pillar"]["master"]["transport"]

        io_loop = kwargs.get("io_loop")
        if io_loop is None:
            io_loop = salt.ext.tornado.ioloop.IOLoop.current()

        crypt = kwargs.get("crypt", "aes")
        if crypt != "clear":
            # we don't need to worry about auth as a kwarg, since its a singleton
            auth = salt.crypt.AsyncAuth(opts, io_loop=io_loop)
        else:
            auth = None

        if "master_uri" in kwargs:
            opts["master_uri"] = kwargs["master_uri"]
        master_uri = cls.get_master_uri(opts)

        # log.error("AsyncReqChannel connects to %s", master_uri)
        # switch on available ttypes
        if ttype == "zeromq":
            import salt.transport.zeromq

            transport = salt.transport.zeromq.ZeroMQReqChannel(
                opts, master_uri, io_loop
            )
        elif ttype == "tcp":
            import salt.transport.tcp

            transport = salt.transport.tcp.TCPReqChannel(opts, master_uri, io_loop)
        else:
            raise Exception("Channels are only defined for tcp, zeromq")
        return cls(opts, transport, auth)

    def __init__(self, opts, transport, auth, **kwargs):
        self.opts = dict(opts)
        self.transport = transport
        self.auth = auth
        self._closing = False

    @property
    def crypt(self):
        if self.auth:
            return "aes"
        return "clear"

    @property
    def ttype(self):
        return self.transport.ttype

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
        ret = yield self.transport.send(
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
    def _crypted_transfer(self, load, tries=3, timeout=60, raw=False):
        """
        Send a load across the wire, with encryption

        In case of authentication errors, try to renegotiate authentication
        and retry the method.

        Indeed, we can fail too early in case of a master restart during a
        minion state execution call

        :param dict load: A load to send across the wire
        :param int tries: The number of times to make before failure
        :param int timeout: The number of seconds on a response before failing
        """

        @salt.ext.tornado.gen.coroutine
        def _do_transfer():
            # Yield control to the caller. When send() completes, resume by populating data with the Future.result
            data = yield self.transport.send(
                self._package_load(self.auth.crypticle.dumps(load)),
                timeout=timeout,
                tries=tries,
            )
            # we may not have always data
            # as for example for saltcall ret submission, this is a blind
            # communication, we do not subscribe to return events, we just
            # upload the results to the master
            if data:
                data = self.auth.crypticle.loads(data, raw)
            if not raw:
                data = salt.transport.frame.decode_embedded_strs(data)
            raise salt.ext.tornado.gen.Return(data)

        if not self.auth.authenticated:
            # Return control back to the caller, resume when authentication succeeds
            yield self.auth.authenticate()
        try:
            # We did not get data back the first time. Retry.
            ret = yield _do_transfer()
        except salt.crypt.AuthenticationError:
            # If auth error, return control back to the caller, continue when authentication succeeds
            yield self.auth.authenticate()
            ret = yield _do_transfer()
        raise salt.ext.tornado.gen.Return(ret)

    @salt.ext.tornado.gen.coroutine
    def _uncrypted_transfer(self, load, tries=3, timeout=60):
        """
        Send a load across the wire in cleartext

        :param dict load: A load to send across the wire
        :param int tries: The number of times to make before failure
        :param int timeout: The number of seconds on a response before failing
        """
        ret = yield self.transport.send(
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
        if self.crypt == "clear":
            ret = yield self._uncrypted_transfer(load, tries=tries, timeout=timeout)
        else:
            ret = yield self._crypted_transfer(
                load, tries=tries, timeout=timeout, raw=raw
            )
        raise salt.ext.tornado.gen.Return(ret)

    @classmethod
    def get_master_uri(cls, opts):
        if "master_uri" in opts:
            return opts["master_uri"]

        # TODO: Make sure we don't need this anymore
        # if by chance master_uri is not there..
        # if "master_ip" in opts:
        #    return _get_master_uri(
        #        opts["master_ip"],
        #        opts["master_port"],
        #        source_ip=opts.get("source_ip"),
        #        source_port=opts.get("source_ret_port"),
        #    )

        # if we've reached here something is very abnormal
        raise SaltException("ReqChannel: missing master_uri/master_ip in self.opts")

    @property
    def master_uri(self):
        return self.get_master_uri(self.opts)

    def close(self):
        """
        Since the message_client creates sockets and assigns them to the IOLoop we have to
        specifically destroy them, since we aren't the only ones with references to the FDs
        """
        if self._closing:
            return
        log.debug("Closing %s instance", self.__class__.__name__)
        self._closing = True
        if hasattr(self.transport, "message_client"):
            self.transport.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncPubChannel:
    """
    Factory class to create subscription channels to the master's Publisher
    """

    async_methods = [
        "connect",
        "_decode_messages",
    ]
    close_methods = [
        "close",
    ]

    @classmethod
    def factory(cls, opts, **kwargs):
        import salt.ext.tornado.ioloop
        import salt.crypt

        # Default to ZeroMQ for now
        ttype = "zeromq"

        # determine the ttype
        if "transport" in opts:
            ttype = opts["transport"]
        elif "transport" in opts.get("pillar", {}).get("master", {}):
            ttype = opts["pillar"]["master"]["transport"]

        if "master_uri" in kwargs:
            opts["master_uri"] = kwargs["master_uri"]
        # master_uri = cls.get_master_uri(opts)

        # switch on available ttypes
        if ttype == "detect":
            opts["detect_mode"] = True
            log.info("Transport is set to detect; using %s", ttype)

        io_loop = kwargs.get("io_loop")
        if io_loop is None:
            io_loop = salt.ext.tornado.ioloop.IOLoop.current()

        auth = salt.crypt.AsyncAuth(opts, io_loop=io_loop)
        #    if int(opts.get("publish_port", 4506)) != 4506:
        #        publish_port = opts.get("publish_port")
        #    # else take the relayed publish_port master reports
        #    else:
        #        publish_port = auth.creds["publish_port"]

        if ttype == "zeromq":
            import salt.transport.zeromq

            transport = salt.transport.zeromq.AsyncZeroMQPubChannel(opts, io_loop)
        elif ttype == "tcp":
            import salt.transport.tcp

            transport = salt.transport.tcp.AsyncTCPPubChannel(
                opts, io_loop
            )  # , **kwargs)
        elif ttype == "local":  # TODO:
            raise Exception("There's no AsyncLocalPubChannel implementation yet")
            # import salt.transport.local
            # return salt.transport.local.AsyncLocalPubChannel(opts, **kwargs)
        else:
            raise Exception("Channels are only defined for tcp, zeromq, and local")
            # return NewKindOfChannel(opts, **kwargs)
        return cls(opts, transport, auth, io_loop)

    def __init__(self, opts, transport, auth, io_loop=None):
        self.opts = opts
        self.io_loop = io_loop
        self.serial = salt.payload.Serial(self.opts)
        self.auth = auth
        self.tok = self.auth.gen_token(b"salt")
        self.transport = transport
        self._closing = False
        self._reconnected = False
        self.event = salt.utils.event.get_event("minion", opts=self.opts, listen=False)

    @property
    def crypt(self):
        if self.auth:
            return "aes"
        return "clear"

    @salt.ext.tornado.gen.coroutine
    def connect(self):
        """
        Return a future which completes when connected to the remote publisher
        """
        try:
            import traceback

            if not self.auth.authenticated:
                yield self.auth.authenticate()
            # if this is changed from the default, we assume it was intentional
            if int(self.opts.get("publish_port", 4506)) != 4506:
                publish_port = self.opts.get("publish_port")
            # else take the relayed publish_port master reports
            else:
                publish_port = self.auth.creds["publish_port"]
            # TODO: The zeromq transport does not use connect_callback and
            # disconnect_callback.
            yield self.transport.connect(
                publish_port, self.connect_callback, self.disconnect_callback
            )
        # TODO: better exception handling...
        except KeyboardInterrupt:  # pylint: disable=try-except-raise
            raise
        except Exception as exc:  # pylint: disable=broad-except
            if "-|RETRY|-" not in str(exc):
                raise SaltClientError(
                    "Unable to sign_in to master: {}".format(exc)
                )  # TODO: better error message

    def close(self):
        """
        Close the channel
        """
        self.transport.close()
        if self.event is not None:
            self.event.destroy()
            self.event = None

    def on_recv(self, callback=None):
        """
        When jobs are received pass them (decoded) to callback
        """
        if callback is None:
            return self.transport.on_recv(None)

        @salt.ext.tornado.gen.coroutine
        def wrap_callback(messages):
            payload = yield self.transport._decode_messages(messages)
            decoded = yield self._decode_payload(payload)
            if decoded is not None:
                callback(decoded)

        return self.transport.on_recv(wrap_callback)

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
            # yield self.message_client.write_to_stream(package)
            yield self.transport.send(package)

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
        try:
            # Force re-auth on reconnect since the master
            # may have been restarted
            yield self.send_id(self.tok, self._reconnected)
            self.connected = True
            self.event.fire_event({"master": self.opts["master"]}, "__master_connected")
            if self._reconnected:
                # On reconnects, fire a master event to notify that the minion is
                # available.
                if self.opts.get("__role") == "syndic":
                    data = "Syndic {} started at {}".format(
                        self.opts["id"], time.asctime()
                    )
                    tag = salt.utils.event.tagify([self.opts["id"], "start"], "syndic")
                else:
                    data = "Minion {} started at {}".format(
                        self.opts["id"], time.asctime()
                    )
                    tag = salt.utils.event.tagify([self.opts["id"], "start"], "minion")
                load = {
                    "id": self.opts["id"],
                    "cmd": "_minion_event",
                    "pretag": None,
                    "tok": self.tok,
                    "data": data,
                    "tag": tag,
                }
                req_channel = ReqChannel(self.opts)
                try:
                    req_channel.send(load, timeout=60)
                except salt.exceptions.SaltReqTimeoutError:
                    log.info(
                        "fire_master failed: master could not be contacted. Request timed"
                        " out."
                    )
                except Exception:  # pylint: disable=broad-except
                    log.info("fire_master failed", exc_info=True)
                finally:
                    # SyncWrapper will call either close() or destroy(), whichever is available
                    del req_channel
            else:
                self._reconnected = True
        except Exception as exc:  # pylint: disable=broad-except
            log.error(
                "Caught exception in PubChannel connect callback %r", exc, exc_info=True
            )

    def disconnect_callback(self):
        if self._closing:
            return
        self.connected = False
        self.event.fire_event({"master": self.opts["master"]}, "__master_disconnected")

    def _verify_master_signature(self, payload):
        if self.opts.get("sign_pub_messages"):
            if not payload.get("sig", False):
                raise salt.crypt.AuthenticationError(
                    "Message signing is enabled but the payload has no signature."
                )

            # Verify that the signature is valid
            master_pubkey_path = os.path.join(self.opts["pki_dir"], "minion_master.pub")
            if not salt.crypt.verify_signature(
                master_pubkey_path, payload["load"], payload.get("sig")
            ):
                raise salt.crypt.AuthenticationError(
                    "Message signature failed to validate."
                )

    @salt.ext.tornado.gen.coroutine
    def _decode_payload(self, payload):
        # we need to decrypt it
        log.trace("Decoding payload: %s", payload)
        if payload["enc"] == "aes":
            self._verify_master_signature(payload)
            try:
                payload["load"] = self.auth.crypticle.loads(payload["load"])
            except salt.crypt.AuthenticationError:
                yield self.auth.authenticate()
                payload["load"] = self.auth.crypticle.loads(payload["load"])

        raise salt.ext.tornado.gen.Return(payload)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncPushChannel:
    """
    Factory class to create IPC Push channels
    """

    @staticmethod
    def factory(opts, **kwargs):
        """
        If we have additional IPC transports other than UxD and TCP, add them here
        """
        # FIXME for now, just UXD
        # Obviously, this makes the factory approach pointless, but we'll extend later
        import salt.transport.ipc

        return salt.transport.ipc.IPCMessageClient(opts, **kwargs)


class AsyncPullChannel:
    """
    Factory class to create IPC pull channels
    """

    @staticmethod
    def factory(opts, **kwargs):
        """
        If we have additional IPC transports other than UXD and TCP, add them here
        """
        import salt.transport.ipc

        return salt.transport.ipc.IPCMessageServer(opts, **kwargs)

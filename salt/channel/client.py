"""
Encapsulate the different transports available to Salt.

This includes client side transport, for the ReqServer and the Publisher
"""


import asyncio
import logging
import os
import time

import salt.crypt
import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.payload
import salt.transport.frame
import salt.utils.event
import salt.utils.files
import salt.utils.minions
import salt.utils.stringutils
import salt.utils.verify
from salt.utils.asynchronous import AIOSyncWrapper

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
    ReqServer. ReqChannels use transports to connect to the ReqServer.
    """

    @staticmethod
    def factory(opts, **kwargs):
        return AIOSyncWrapper(
            AsyncReqChannel.factory,
            (opts,),
            kwargs,
            loop_kwarg="io_loop",
        )


class PushChannel:
    """
    Factory class to create Sync channel for push side of push/pull IPC
    """

    @staticmethod
    def factory(opts, **kwargs):
        return AIOSyncWrapper(
            AsyncPushChannel.factory,
            (opts,),
            kwargs,
            loop_kwarg="io_loop",
        )


class PullChannel:
    """
    Factory class to create Sync channel for pull side of push/pull IPC
    """

    @staticmethod
    def factory(opts, **kwargs):
        return AIOSyncWrapper(
            AsyncPullChannel.factory,
            (opts,),
            kwargs,
            loop_kwarg="io_loop",
        )


class AsyncReqChannel:
    """
    Factory class to create a asynchronous communication channels to the
    master's ReqServer. ReqChannels connect to the master's ReqServerChannel.
    """

    async_methods = [
        "crypted_transfer_decode_dictentry",
        "_crypted_transfer",
        "_uncrypted_transfer",
        "send",
        "connect",
    ]
    close_methods = [
        "close",
    ]

    @classmethod
    def factory(cls, opts, **kwargs):
        # Default to ZeroMQ for now
        ttype = "zeromq"
        # determine the ttype
        if "transport" in opts:
            ttype = opts["transport"]
        elif "transport" in opts.get("pillar", {}).get("master", {}):
            ttype = opts["pillar"]["master"]["transport"]

        if "master_uri" not in opts and "master_uri" in kwargs:
            opts["master_uri"] = kwargs["master_uri"]
        io_loop = kwargs.get("io_loop")
        if io_loop is None:
            io_loop = asyncio.get_event_loop()
        crypt = kwargs.get("crypt", "aes")
        if crypt != "clear":
            # we don't need to worry about auth as a kwarg, since its a singleton
            auth = salt.crypt.AsyncAuth(opts, io_loop=io_loop)
        else:
            auth = None

        transport = salt.transport.request_client(opts, io_loop)
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

    async def crypted_transfer_decode_dictentry(
        self, load, dictkey=None, timeout=60
    ):
        if not self.auth.authenticated:
            await self.auth.authenticate()
        ret = await self.transport.send(
            self._package_load(self.auth.crypticle.dumps(load)),
            timeout=timeout,
        )
        key = self.auth.get_keys()
        if "key" not in ret:
            # Reauth in the case our key is deleted on the master side.
            await self.auth.authenticate()
            ret = await self.transport.send(
                self._package_load(self.auth.crypticle.dumps(load)),
                timeout=timeout,
            )
        if HAS_M2:
            aes = key.private_decrypt(ret["key"], RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(key)
            aes = cipher.decrypt(ret["key"])
        pcrypt = salt.crypt.Crypticle(self.opts, aes)
        data = pcrypt.loads(ret[dictkey])
        data = salt.transport.frame.decode_embedded_strs(data)
        return data

    async def _crypted_transfer(self, load, timeout=60, raw=False):
        """
        Send a load across the wire, with encryption

        In case of authentication errors, try to renegotiate authentication
        and retry the method.

        Indeed, we can fail too early in case of a master restart during a
        minion state execution call

        :param dict load: A load to send across the wire
        :param int timeout: The number of seconds on a response before failing
        """

        async def _do_transfer():
            # Yield control to the caller. When send() completes, resume by populating data with the Future.result
            data = await self.transport.send(
                self._package_load(self.auth.crypticle.dumps(load)),
                timeout=timeout,
            )
            # we may not have always data
            # as for example for saltcall ret submission, this is a blind
            # communication, we do not subscribe to return events, we just
            # upload the results to the master
            if data:
                data = self.auth.crypticle.loads(data, raw)
            if not raw or self.ttype == "tcp":  # XXX Why is this needed for tcp
                data = salt.transport.frame.decode_embedded_strs(data)
            return data

        if not self.auth.authenticated:
            # Return control back to the caller, resume when authentication succeeds
            await self.auth.authenticate()
        try:
            # We did not get data back the first time. Retry.
            ret = await _do_transfer()
        except salt.crypt.AuthenticationError:
            # If auth error, return control back to the caller, continue when authentication succeeds
            await self.auth.authenticate()
            ret = await _do_transfer()
        return ret

    async def _uncrypted_transfer(self, load, timeout=60):
        """
        Send a load across the wire in cleartext

        :param dict load: A load to send across the wire
        :param int timeout: The number of seconds on a response before failing
        """
        ret = await self.transport.send(
            self._package_load(load),
            timeout=timeout,
        )

        return ret

    @salt.ext.tornado.gen.coroutine
    def connect(self):
        yield self.transport.connect()

    async def send(self, load, tries=3, timeout=60, raw=False):
        """
        Send a request, return a future which will complete when we send the message

        :param dict load: A load to send across the wire
        :param int tries: The number of times to make before failure
        :param int timeout: The number of seconds on a response before failing
        """
        _try = 1
        while True:
            try:
                if self.crypt == "clear":
                    log.trace("ReqChannel send clear load=%r", load)
                    ret = await self._uncrypted_transfer(load, timeout=timeout)
                else:
                    log.trace("ReqChannel send crypt load=%r", load)
                    ret = await self._crypted_transfer(load, timeout=timeout, raw=raw)
                break
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Failed to send msg %r", dir(exc))
                if _try >= tries:
                    raise
                else:
                    _try += 1
                    continue
        return ret

    def close(self):
        """
        Since the message_client creates sockets and assigns them to the IOLoop we have to
        specifically destroy them, since we aren't the only ones with references to the FDs
        """
        if self._closing:
            return
        log.debug("Closing %s instance", self.__class__.__name__)
        self._closing = True
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
        # Default to ZeroMQ for now
        ttype = "zeromq"

        # determine the ttype
        if "transport" in opts:
            ttype = opts["transport"]
        elif "transport" in opts.get("pillar", {}).get("master", {}):
            ttype = opts["pillar"]["master"]["transport"]

        if "master_uri" not in opts and "master_uri" in kwargs:
            opts["master_uri"] = kwargs["master_uri"]

        # switch on available ttypes
        if ttype == "detect":
            opts["detect_mode"] = True
            log.info("Transport is set to detect; using %s", ttype)

        io_loop = kwargs.get("io_loop")
        if io_loop is None:
            io_loop = asyncio.get_event_loop()

        auth = salt.crypt.AsyncAuth(opts, io_loop=io_loop)
        transport = salt.transport.publish_client(opts, io_loop)
        return cls(opts, transport, auth, io_loop)

    def __init__(self, opts, transport, auth, io_loop=None):
        self.opts = opts
        self.io_loop = io_loop
        self.auth = auth
        self.token = self.auth.gen_token(b"salt")
        self.transport = transport
        self._closing = False
        self._reconnected = False
        self.event = salt.utils.event.get_event("minion", opts=self.opts, listen=False)

    @property
    def crypt(self):
        return "aes" if self.auth else "clear"

    async def connect(self):
        """
        Return a future which completes when connected to the remote publisher
        """
        try:
            if not self.auth.authenticated:
                await self.auth.authenticate()
            # if this is changed from the default, we assume it was intentional
            if int(self.opts.get("publish_port", 4506)) != 4506:
                publish_port = self.opts.get("publish_port")
            # else take the relayed publish_port master reports
            else:
                publish_port = self.auth.creds["publish_port"]
            # TODO: The zeromq transport does not use connect_callback and
            # disconnect_callback.
            await self.transport.connect(
                publish_port, self.connect_callback, self.disconnect_callback
            )
        # TODO: better exception handling...
        except KeyboardInterrupt:  # pylint: disable=try-except-raise
            raise
        except Exception as exc:  # pylint: disable=broad-except
            if "-|RETRY|-" not in str(exc):
                raise salt.exceptions.SaltClientError(
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

        async def wrap_callback(messages):
            payload = await self.transport._decode_messages(messages)
            decoded = await self._decode_payload(payload)
            log.trace("PubChannel received: %r", decoded)
            if decoded is not None:
                callback(decoded)

        return self.transport.on_recv(wrap_callback)

    def _package_load(self, load):
        return {
            "enc": self.crypt,
            "load": load,
        }

    async def send_id(self, tok, force_auth):
        """
        Send the minion id to the master so that the master may better
        track the connection state of the minion.
        In case of authentication errors, try to renegotiate authentication
        and retry the method.
        """
        load = {"id": self.opts["id"], "tok": tok}

        async def _do_transfer():
            msg = self._package_load(self.auth.crypticle.dumps(load))
            package = salt.transport.frame.frame_msg(msg, header=None)
            await self.transport.send(package)
            return True

        if force_auth or not self.auth.authenticated:
            count = 0
            while (
                count <= self.opts["tcp_authentication_retries"]
                or self.opts["tcp_authentication_retries"] < 0
            ):
                try:
                    await self.auth.authenticate()
                    break
                except salt.exceptions.SaltClientError as exc:
                    log.debug(exc)
                    count += 1
        try:
            ret = await _do_transfer()
            return ret
        except salt.crypt.AuthenticationError:
            await self.auth.authenticate()
            ret = await _do_transfer()
            return ret

    async def connect_callback(self, result):
        if self._closing:
            return
        try:
            # Force re-auth on reconnect since the master
            # may have been restarted
            await self.send_id(self.token, self._reconnected)
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
                    "tok": self.token,
                    "data": data,
                    "tag": tag,
                }
                req_channel = AsyncReqChannel.factory(self.opts)
                try:
                    await req_channel.send(load, timeout=60)
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

    async def _decode_payload(self, payload):
        # we need to decrypt it
        log.trace("Decoding payload: %s", payload)
        if payload["enc"] == "aes":
            self._verify_master_signature(payload)
            try:
                payload["load"] = self.auth.crypticle.loads(payload["load"])
            except salt.crypt.AuthenticationError:
                await self.auth.authenticate()
                payload["load"] = self.auth.crypticle.loads(payload["load"])
        return payload

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

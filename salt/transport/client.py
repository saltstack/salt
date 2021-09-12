"""
Encapsulate the different transports available to Salt.

This includes client side transport, for the ReqServer and the Publisher
"""


import logging

import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
from salt.utils.asynchronous import SyncWrapper
from salt.exceptions import SaltException

try:
    from M2Crypto import RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.Cipher import PKCS1_OAEP
    except ImportError:
        from Crypto.Cipher import PKCS1_OAEP  # nosec

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

            channel = salt.transport.zeromq.ZeroMQReqChannel(opts, master_uri, io_loop)
        elif ttype == "tcp":
            import salt.transport.tcp

            channel = salt.transport.tcp.TCPReqChannel(opts, master_uri, io_loop)
        else:
            raise Exception("Channels are only defined for tcp, zeromq")
        return cls(opts, channel, auth)

    def __init__(self, opts, channel, auth, **kwargs):
        self.opts = dict(opts)
        self.channel = channel
        self.auth = auth
        self._closing = False

    @property
    def crypt(self):
        if self.auth:
            return "aes"
        return "clear"

    @property
    def ttype(self):
        return self.channel.ttype

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
        ret = yield self.channel.message_client.send(
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
            data = yield self.channel.message_client.send(
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
        ret = yield self.channel.message_client.send(
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
        #if "master_ip" in opts:
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
        if hasattr(self.channel, "message_client"):
            self.channel.message_client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncPubChannel(AsyncChannel):
    """
    Factory class to create subscription channels to the master's Publisher
    """

    @classmethod
    def factory(cls, opts, **kwargs):
        # Default to ZeroMQ for now
        ttype = "zeromq"

        # determine the ttype
        if "transport" in opts:
            ttype = opts["transport"]
        elif "transport" in opts.get("pillar", {}).get("master", {}):
            ttype = opts["pillar"]["master"]["transport"]

        # switch on available ttypes
        if ttype == "detect":
            opts["detect_mode"] = True
            log.info("Transport is set to detect; using %s", ttype)
        if ttype == "zeromq":
            import salt.transport.zeromq

            return salt.transport.zeromq.AsyncZeroMQPubChannel(opts, **kwargs)
        elif ttype == "tcp":
            if not cls._resolver_configured:
                # TODO: add opt to specify number of resolver threads
                AsyncChannel._config_resolver()
            import salt.transport.tcp

            return salt.transport.tcp.AsyncTCPPubChannel(opts, **kwargs)
        elif ttype == "local":  # TODO:
            raise Exception("There's no AsyncLocalPubChannel implementation yet")
            # import salt.transport.local
            # return salt.transport.local.AsyncLocalPubChannel(opts, **kwargs)
        else:
            raise Exception("Channels are only defined for tcp, zeromq, and local")
            # return NewKindOfChannel(opts, **kwargs)

    def connect(self):
        """
        Return a future which completes when connected to the remote publisher
        """
        raise NotImplementedError()

    def close(self):
        """
        Close the channel
        """
        raise NotImplementedError()

    def on_recv(self, callback):
        """
        When jobs are received pass them (decoded) to callback
        """
        raise NotImplementedError()

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

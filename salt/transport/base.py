import hashlib
import logging
import os
import ssl
import traceback
import warnings

import salt.utils.stringutils

log = logging.getLogger(__name__)

TRANSPORTS = (
    "zeromq",
    "tcp",
    "ws",
)


def request_server(opts, **kwargs):
    # Default to ZeroMQ for now
    ttype = "zeromq"

    # determine the ttype
    if "transport" in opts:
        ttype = opts["transport"]
    elif "transport" in opts.get("pillar", {}).get("master", {}):
        ttype = opts["pillar"]["master"]["transport"]

    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.RequestServer(opts)
    elif ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.RequestServer(opts)
    elif ttype == "ws":
        import salt.transport.ws

        return salt.transport.ws.RequestServer(opts)
    elif ttype == "local":
        import salt.transport.local

        transport = salt.transport.local.LocalServerChannel(opts)
    else:
        raise Exception("Channels are only defined for ZeroMQ and TCP")


def request_client(opts, io_loop):
    ttype = "zeromq"
    if "transport" in opts:
        ttype = opts["transport"]
    elif "transport" in opts.get("pillar", {}).get("master", {}):
        ttype = opts["pillar"]["master"]["transport"]

    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.RequestClient(opts, io_loop=io_loop)
    elif ttype == "tcp":
        import salt.transport.tcp

        resolver = salt.transport.tcp.Resolver()
        return salt.transport.tcp.RequestClient(
            opts, resolver=resolver, io_loop=io_loop
        )
    elif ttype == "ws":
        import salt.transport.ws

        return salt.transport.ws.RequestClient(opts, io_loop=io_loop)
    else:
        raise Exception("Channels are only defined for tcp, zeromq")


def publish_server(opts, **kwargs):
    # Default to ZeroMQ for now
    ttype = "zeromq"
    # determine the ttype
    if "transport" in kwargs:
        ttype = kwargs.pop("transport")
    elif "transport" in opts:
        ttype = opts["transport"]
    elif "transport" in opts.get("pillar", {}).get("master", {}):
        ttype = opts["pillar"]["master"]["transport"]

    if "pub_host" not in kwargs and "pub_path" not in kwargs:
        kwargs["pub_host"] = opts["interface"]
    if "pub_port" not in kwargs and "pub_path" not in kwargs:
        kwargs["pub_port"] = opts.get("publish_port", 4506)

    if "pull_host" not in kwargs and "pull_path" not in kwargs:
        if opts.get("ipc_mode", "") == "tcp":
            kwargs["pull_host"] = "127.0.0.1"
            kwargs["pull_port"] = opts.get("tcp_master_publish_pull", 4514)
        else:
            kwargs["pull_path"] = os.path.join(opts["sock_dir"], "publish_pull.ipc")

    if "ssl" not in kwargs and opts.get("ssl", None) is not None:
        kwargs["ssl"] = opts["ssl"]

    # switch on available ttypes
    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.PublishServer(opts, **kwargs)
    elif ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.PublishServer(opts, **kwargs)
    elif ttype == "ws":
        import salt.transport.ws

        return salt.transport.ws.PublishServer(opts, **kwargs)
    elif ttype == "local":  # TODO:
        import salt.transport.local

        return salt.transport.local.LocalPubServerChannel(opts, **kwargs)
    raise Exception(f"Transport type not found: {ttype}")


def publish_client(
    opts, io_loop, host=None, port=None, path=None, transport=None, **kwargs
):
    # Default to ZeroMQ for now
    ttype = "zeromq"
    # determine the ttype
    if transport is not None:
        ttype = transport
    elif "transport" in opts:
        ttype = opts["transport"]
    elif "transport" in opts.get("pillar", {}).get("master", {}):
        ttype = opts["pillar"]["master"]["transport"]

    ssl_opts = None
    if "ssl" in kwargs:
        ssl_opts = kwargs["ssl"]
    elif opts.get("ssl", None) is not None:
        ssl_opts = opts["ssl"]

    # switch on available ttypes
    if ttype == "zeromq":
        import salt.transport.zeromq

        if ssl_opts:
            log.warning("TLS not supported with zeromq transport")
        return salt.transport.zeromq.PublishClient(
            opts, io_loop, host=host, port=port, path=path
        )
    elif ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.PublishClient(
            opts,
            io_loop,
            host=host,
            port=port,
            path=path,
            ssl=ssl_opts,
        )
    elif ttype == "ws":
        import salt.transport.ws

        return salt.transport.ws.PublishClient(
            opts,
            io_loop,
            host=host,
            port=port,
            path=path,
            ssl=ssl_opts,
        )

    raise Exception(f"Transport type not found: {ttype}")


def _minion_hash(hash_type, minion_id):
    """
    Generate a hash string for the minion id
    """
    hasher = getattr(hashlib, hash_type)
    return hasher(salt.utils.stringutils.to_bytes(minion_id)).hexdigest()[:10]


def ipc_publish_client(node, opts, io_loop):
    # Default to TCP for now
    kwargs = {"transport": "tcp", "ssl": None}
    if opts["ipc_mode"] == "tcp":
        if node == "master":
            kwargs.update(
                host="127.0.0.1",
                port=int(opts["tcp_master_pub_port"]),
            )
        else:
            kwargs.update(
                host="127.0.0.1",
                port=int(opts["tcp_pub_port"]),
            )
    else:
        if node == "master":
            kwargs.update(
                path=os.path.join(opts["sock_dir"], "master_event_pub.ipc"),
            )
        else:
            id_hash = _minion_hash(
                hash_type=opts["hash_type"],
                minion_id=opts.get("hash_id", opts["id"]),
            )
            kwargs.update(
                path=os.path.join(opts["sock_dir"], f"minion_event_{id_hash}_pub.ipc")
            )
    return publish_client(opts, io_loop, **kwargs)


def ipc_publish_server(node, opts):
    # Default to TCP for now
    kwargs = {"transport": "tcp", "ssl": None}
    if opts["ipc_mode"] == "tcp":
        if node == "master":
            kwargs.update(
                pub_host="127.0.0.1",
                pub_port=int(opts["tcp_master_pub_port"]),
                pull_host="127.0.0.1",
                pull_port=int(opts["tcp_master_pull_port"]),
            )
        else:
            kwargs.update(
                pub_host="127.0.0.1",
                pub_port=int(opts["tcp_pub_port"]),
                pull_host="127.0.0.1",
                pull_port=int(opts["tcp_pull_port"]),
            )
    else:
        if node == "master":
            kwargs.update(
                pub_path=os.path.join(opts["sock_dir"], "master_event_pub.ipc"),
                pull_path=os.path.join(opts["sock_dir"], "master_event_pull.ipc"),
            )
        else:
            id_hash = _minion_hash(
                hash_type=opts["hash_type"],
                minion_id=opts.get("hash_id", opts["id"]),
            )
            pub_path = os.path.join(opts["sock_dir"], f"minion_event_{id_hash}_pub.ipc")
            kwargs.update(
                pub_path=pub_path,
                pull_path=os.path.join(
                    opts["sock_dir"], f"minion_event_{id_hash}_pull.ipc"
                ),
            )
    return publish_server(opts, **kwargs)


class TransportWarning(Warning):
    """
    Transport warning.
    """


class Transport:
    def __init__(self, *args, **kwargs):
        self._trace = "\n".join(traceback.format_stack()[:-1])
        if not hasattr(self, "_closing"):
            self._closing = False
        if not hasattr(self, "_connect_called"):
            self._connect_called = False

    def connect(self, *args, **kwargs):
        self._connect_called = True

    # pylint: disable=W1701
    def __del__(self):
        """
        Warn the user if the transport's close method was never called.

        If the _closing attribute is missing we won't raise a warning. This
        prevents issues when class's dunder init method is called with improper
        arguments, and is later getting garbage collected. Users of this class
        should take care to call super() and validate the functionality with a
        test.
        """
        if getattr(self, "_connect_called") and not getattr(self, "_closing", True):
            warnings.warn(
                f"Unclosed transport! {self!r} \n{self._trace}",
                TransportWarning,
                source=self,
            )

    # pylint: enable=W1701


class RequestClient(Transport):
    """
    The RequestClient transport is used to make requests and get corresponding
    replies from the RequestServer.
    """

    def __init__(self, opts, io_loop, **kwargs):
        super().__init__()

    async def send(self, load, timeout=60):
        """
        Send a request message and return the reply from the server.
        """
        raise NotImplementedError

    def close(self):
        """
        Close the connection.
        """
        raise NotImplementedError

    def connect(self):  # pylint: disable=W0221
        """
        Connect to the server / broker.
        """
        raise NotImplementedError


class RequestServer:
    """
    The RequestServer transport is responsible for handling requests from
    RequestClients and sending replies to those requests.
    """

    def __init__(self, opts):
        pass

    def close(self):
        """
        Close the underlying network connection.
        """
        raise NotImplementedError


class DaemonizedRequestServer(RequestServer):
    def pre_fork(self, process_manager):
        raise NotImplementedError

    def post_fork(self, message_handler, io_loop):
        """
        The message handler is a coroutine that will be called called when a
        new request comes into the server. The return from the message handler
        will be send back to the RequestClient
        """
        raise NotImplementedError


class PublishServer:
    """
    The PublishServer publishes messages to PublishClients or to a borker
    service.
    """

    def publish(self, payload, **kwargs):
        """
        Publish "load" to minions. This send the load to the publisher daemon
        process with does the actual sending to minions.

        :param dict load: A load to be sent across the wire to minions
        """
        raise NotImplementedError


class DaemonizedPublishServer(PublishServer):
    """
    PublishServer that has a daemon associated with it.
    """

    def pre_fork(self, process_manager):
        raise NotImplementedError

    def publish_daemon(
        self,
        publish_payload,
        presence_callback=None,
        remove_presence_callback=None,
    ):
        """
        If a daemon is needed to act as a broker implement it here.

        :param func publish_payload: A method used to publish the payload
        :param func presence_callback: If the transport support presence
                                       callbacks call this method to notify the
                                       channel of a client's presence
        :param func remove_presence_callback: If the transport support presence
                                              callbacks call this method to
                                              notify the channel a client is no
                                              longer present
        """
        raise NotImplementedError


class PublishClient(Transport):
    """
    The PublishClient receives messages from the PublishServer and runs a callback.
    """

    def __init__(self, opts, io_loop, **kwargs):
        super().__init__()

    def on_recv(self, callback):
        """
        Add a message handler when we receive a message from the PublishServer
        """
        raise NotImplementedError

    async def connect(  # pylint: disable=arguments-differ,invalid-overridden-method
        self, port=None, connect_callback=None, disconnect_callback=None, timeout=None
    ):
        """
        Create a network connection to the PublishServer or broker.
        """
        raise NotImplementedError

    async def recv(self, timeout=None):
        """
        Receive a single message from the publish server.

        The default timeout=None will wait indefinitly for a message. When
        timeout is 0 return immediately if no message is ready. A positive
        value sepcifies a period of time to wait for a message before raising a
        TimeoutError.
        """
        raise NotImplementedError

    def close(self):
        """
        Close the underlying network connection
        """
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def ssl_context(ssl_options, server_side=False):
    """
    Create an ssl context from the provided ssl_options. This method preserves
    backwards compatability older ssl config settings but adds verify_locations
    and verify_flags options.
    """
    default_version = ssl.PROTOCOL_TLS
    if server_side:
        default_version = ssl.PROTOCOL_TLS_SERVER
        purpose = ssl.Purpose.CLIENT_AUTH
    elif server_side is not None:
        default_version = ssl.PROTOCOL_TLS_CLIENT
        purpose = ssl.Purpose.SERVER_AUTH
    # Use create_default_context to start with what Python considers resonably
    # secure settings.
    context = ssl.create_default_context(purpose)
    context.protocol = ssl_options.get("ssl_version", default_version)
    if "certfile" in ssl_options:
        context.load_cert_chain(
            ssl_options["certfile"], ssl_options.get("keyfile", None)
        )
    if "cert_reqs" in ssl_options:
        if ssl_options["cert_reqs"].upper() == "CERT_NONE":
            # This may have been set automatically by PROTOCOL_TLS_CLIENT but is
            # incompatible with CERT_NONE so we must manually clear it.
            context.check_hostname = False
        context.verify_mode = getattr(ssl.VerifyMode, ssl_options["cert_reqs"])
    if "ca_certs" in ssl_options:
        context.load_verify_locations(ssl_options["ca_certs"])
    if "verify_locations" in ssl_options:
        for _ in ssl_options["verify_locations"]:
            if isinstance(_, dict):
                for key in _:
                    if key.lower() == "cafile":
                        context.load_verify_locations(cafile=_[key])
                    elif key.lower() == "capath":
                        context.load_verify_locations(capath=_[key])
                    elif key.lower() == "cadata":
                        context.load_verify_locations(cadata=_[key])
                    else:
                        log.warning("Unkown verify location type: %s", key)
            else:
                cafile = _
                context.load_verify_locations(cafile=_)
    if "verify_flags" in ssl_options:
        for flag in ssl_options["verify_flags"]:
            context.verify_flags |= getattr(ssl.VerifyFlags, flag.upper())
    if "ciphers" in ssl_options:
        context.set_ciphers(ssl_options["ciphers"])
    return context


def common_name(cert):
    try:
        name = dict([_[0] for _ in cert["subject"]])["commonName"]
    except (ValueError, KeyError):
        return None
    return name

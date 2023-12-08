import hashlib
import os
import traceback
import warnings

import salt.utils.stringutils

TRANSPORTS = (
    "zeromq",
    "tcp",
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

        return salt.transport.tcp.TCPReqServer(opts)
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
        return salt.transport.tcp.TCPReqClient(opts, resolver=resolver, io_loop=io_loop)
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

    # switch on available ttypes
    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.PublishServer(opts, **kwargs)
    elif ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.TCPPublishServer(opts, **kwargs)
    elif ttype == "local":  # TODO:
        import salt.transport.local

        return salt.transport.local.LocalPubServerChannel(opts, **kwargs)
    raise Exception(f"Transport type not found: {ttype}")


def publish_client(opts, io_loop, host=None, port=None, path=None, transport=None):
    # Default to ZeroMQ for now
    ttype = "zeromq"
    # determine the ttype
    if transport is not None:
        ttype = transport
    elif "transport" in opts:
        ttype = opts["transport"]
    elif "transport" in opts.get("pillar", {}).get("master", {}):
        ttype = opts["pillar"]["master"]["transport"]

    # switch on available ttypes
    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.PublishClient(
            opts, io_loop, host=host, port=port, path=path
        )
    elif ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.TCPPubClient(
            opts, io_loop, host=host, port=port, path=path
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
    kwargs = {"transport": "tcp"}
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
    kwargs = {"transport": "tcp"}
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

    async def connect(  # pylint: disable=arguments-differ
        self, port=None, connect_callback=None, disconnect_callback=None, timeout=None
    ):
        """
        Create a network connection to the the PublishServer or broker.
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

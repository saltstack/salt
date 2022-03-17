import salt.ext.tornado.gen

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

        return salt.transport.tcp.TCPReqClient(opts, io_loop=io_loop)
    else:
        raise Exception("Channels are only defined for tcp, zeromq")


def publish_server(opts, **kwargs):
    # Default to ZeroMQ for now
    ttype = "zeromq"
    # determine the ttype
    if "transport" in opts:
        ttype = opts["transport"]
    elif "transport" in opts.get("pillar", {}).get("master", {}):
        ttype = opts["pillar"]["master"]["transport"]
    # switch on available ttypes
    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.PublishServer(opts, **kwargs)
    elif ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.TCPPublishServer(opts)
    elif ttype == "local":  # TODO:
        import salt.transport.local

        return salt.transport.local.LocalPubServerChannel(opts, **kwargs)
    raise Exception("Transport type not found: {}".format(ttype))


def publish_client(opts, io_loop):
    # Default to ZeroMQ for now
    ttype = "zeromq"
    # determine the ttype
    if "transport" in opts:
        ttype = opts["transport"]
    elif "transport" in opts.get("pillar", {}).get("master", {}):
        ttype = opts["pillar"]["master"]["transport"]
    # switch on available ttypes
    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.PublishClient(opts, io_loop)
    elif ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.TCPPubClient(opts, io_loop)
    raise Exception("Transport type not found: {}".format(ttype))


class RequestClient:
    """
    The RequestClient transport is used to make requests and get corresponding
    replies from the RequestServer.
    """

    def __init__(self, opts, io_loop, **kwargs):
        pass

    @salt.ext.tornado.gen.coroutine
    def send(self, load, timeout=60):
        """
        Send a request message and return the reply from the server.
        """
        raise NotImplementedError

    def close(self):
        """
        Close the connection.
        """
        raise NotImplementedError

    def connect(self):
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


class PublishClient:
    """
    The PublishClient receives messages from the PublishServer and runs a callback.
    """

    def __init__(self, opts, io_loop, **kwargs):
        pass

    def on_recv(self, callback):
        """
        Add a message handler when we receive a message from the PublishServer
        """
        raise NotImplementedError

    @salt.ext.tornado.gen.coroutine
    def connect(self, publish_port, connect_callback=None, disconnect_callback=None):
        """
        Create a network connection to the the PublishServer or broker.
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

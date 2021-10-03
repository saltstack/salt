import salt.ext.tornado.gen


def request_server(opts, **kwargs):
    # Default to ZeroMQ for now
    ttype = "zeromq"

    # determine the ttype
    if "transport" in opts:
        ttype = opts["transport"]
    elif "transport" in opts.get("pillar", {}).get("master", {}):
        ttype = opts["pillar"]["master"]["transport"]

    # import salt.transport.zeromq
    # opts["master_uri"] = salt.transport.zeromq.RequestClient.get_master_uri(opts)
    # switch on available ttypes
    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.RequestServer(opts)
    elif ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.TCPReqServer(opts)
    elif ttype == "rabbitmq":
        import salt.transport.tcp

        return salt.transport.rabbitmq.RabbitMQReqServer(opts)
    elif ttype == "local":
        import salt.transport.local

        transport = salt.transport.local.LocalServerChannel(opts)
    else:
        raise Exception("Channels are only defined for ZeroMQ and TCP")
        # return NewKindOfChannel(opts, **kwargs)


def request_client(opts, io_loop):
    # log.error("AsyncReqChannel connects to %s", master_uri)
    # switch on available ttypes
    # XXX
    # opts["master_uri"] = salt.transport.zeromq.RequestClient.get_master_uri(opts)
    ttype = "zeromq"
    # determine the ttype
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
    elif ttype == "rabbitmq":
        import salt.transport.rabbitmq

        return salt.transportrabbitmq.RabbitMQRequestClient(opts, io_loop=io_loop)
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
    elif ttype == "rabbitmq":
        import salt.transport.tcp

        return salt.transport.rabbitmq.RabbitMQPubServer(opts, **kwargs)
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
    elif ttype == "rabbitmq":
        import salt.transport.tcp

        return salt.transport.rabbitmq.RabbitMQPubClient(opts, io_loop)
    raise Exception("Transport type not found: {}".format(ttype))


class RequestClient:
    """
    The RequestClient transport is used to make requests and get corresponding
    replies from the RequestServer.
    """

    @salt.ext.tornado.gen.coroutine
    def send(self, load, tries=3, timeout=60, raw=False):
        """
        Send a request message and return the reply from the server.
        """

    def close(self):
        """
        Close the connection.
        """

    # XXX:  Should have a connect too?
    # def connect(self):
    #    """
    #    Connect to the server / broker.
    #    """


class RequestServer:
    """
    The RequestServer transport is responsible for handling requests from
    RequestClients and sending replies to those requests.
    """

    def close(self):
        pass

    def pre_fork(self, process_manager):
        """ """

    def post_fork(self, message_handler, io_loop):
        """
        The message handler is a coroutine that will be called called when a
        new request comes into the server. The return from the message handler
        will be send back to the RequestClient
        """


class PublishServer:
    """
    The PublishServer publishes messages to PubilshClients
    """

    def pre_fork(self, process_manager, kwargs=None):
        """ """

    def post_fork(self, message_handler, io_loop):
        """ """

    def publish_daemon(
        self,
        publish_payload,
        presence_callback=None,
        remove_presence_callback=None,
        **kwargs
    ):
        """
        If a deamon is needed to act as a broker impliment it here.
        """

    def publish(self, payload, **kwargs):
        """
        Publish "load" to minions. This send the load to the publisher daemon
        process with does the actual sending to minions.

        :param dict load: A load to be sent across the wire to minions
        """


class PublishClient:
    def on_recv(self, callback):
        """
        Add a message handler when we recieve a message from the PublishServer
        """

    @salt.ext.tornado.gen.coroutine
    def connect(self, publish_port, connect_callback=None, disconnect_callback=None):
        """ """

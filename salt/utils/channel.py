import copy

import salt.master


def iter_transport_opts(opts):
    """
    Yield transport, opts for all master configured transports
    """
    transports = set()

    for transport, opts_overrides in opts.get("transport_opts", {}).items():
        t_opts = copy.deepcopy(opts)
        t_opts.update(opts_overrides)
        t_opts["transport"] = transport
        # Ensure secrets are available
        t_opts["secrets"] = salt.master.SMaster.secrets
        transports.add(transport)
        yield transport, t_opts

    transport = opts.get("transport", "zeromq")
    if transport not in transports:
        t_opts = copy.deepcopy(opts)
        t_opts["secrets"] = salt.master.SMaster.secrets
        yield transport, t_opts


def create_server_transport(opts):
    """
    Create a server transport based on opts
    """
    ttype = opts.get("transport", "zeromq")
    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.RequestServer(opts)
    if ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.RequestServer(opts)
    if ttype == "ws":
        import salt.transport.ws

        return salt.transport.ws.RequestServer(opts)
    raise ValueError(f"Unsupported transport type: {ttype}")


def create_client_transport(opts, io_loop):
    """
    Create a client transport based on opts.
    For request routing, this should return a RequestClient, not PublishClient.
    """
    ttype = opts.get("transport", "zeromq")
    if ttype == "zeromq":
        import salt.transport.zeromq

        # For worker pool routing we need RequestClient, not PublishClient
        if opts.get("workers_ipc_name") or opts.get("pool_name"):
            return salt.transport.zeromq.RequestClient(opts, io_loop=io_loop)
        return salt.transport.zeromq.PublishClient(opts, io_loop)
    if ttype == "tcp":
        import salt.transport.tcp

        if opts.get("workers_ipc_name") or opts.get("pool_name"):
            return salt.transport.tcp.RequestClient(opts, io_loop=io_loop)
        return salt.transport.tcp.PublishClient(opts, io_loop)
    if ttype == "ws":
        import salt.transport.ws

        if opts.get("workers_ipc_name") or opts.get("pool_name"):
            return salt.transport.ws.RequestClient(opts, io_loop=io_loop)
        return salt.transport.ws.PublishClient(opts, io_loop)
    raise ValueError(f"Unsupported transport type: {ttype}")


def create_request_client(opts, io_loop=None):
    """
    Create a RequestClient for pool routing.
    This ensures we always get a RequestClient regardless of transport.
    """
    ttype = opts.get("transport", "zeromq")
    if io_loop is None:
        import tornado.ioloop

        io_loop = tornado.ioloop.IOLoop.current()

    if ttype == "zeromq":
        import salt.transport.zeromq

        return salt.transport.zeromq.RequestClient(opts, io_loop=io_loop)
    if ttype == "tcp":
        import salt.transport.tcp

        return salt.transport.tcp.RequestClient(opts, io_loop=io_loop)
    if ttype == "ws":
        import salt.transport.ws

        return salt.transport.ws.RequestClient(opts, io_loop=io_loop)
    raise ValueError(f"Unsupported transport type: {ttype}")

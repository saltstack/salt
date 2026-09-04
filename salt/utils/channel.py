import copy

import salt.master


def iter_transport_opts(opts):
    """
    Yield transport, opts for all master configured transports
    """
    transports = set()
    # Never deepcopy secrets: SMaster.secrets holds SynchronizedString objects
    # (multiprocessing sharedctypes) that Python 3.14 refuses to deepcopy outside
    # a spawning context — assert_spawning() raises even when the start method is
    # "fork".  Exclude the key before copying and re-attach a live reference after,
    # so callers that pass opts already enriched by a previous iter_transport_opts
    # call (e.g. PubServerChannel.factory called from ClearFuncs.connect) are safe.
    opts_nosecrets = {k: v for k, v in opts.items() if k != "secrets"}

    for transport, opts_overrides in opts_nosecrets.get("transport_opts", {}).items():
        t_opts = copy.deepcopy(opts_nosecrets)
        t_opts.update(opts_overrides)
        t_opts["transport"] = transport
        # Ensure secrets are available
        t_opts["secrets"] = salt.master.SMaster.secrets
        transports.add(transport)
        yield transport, t_opts

    transport = opts_nosecrets.get("transport", "zeromq")
    if transport not in transports:
        t_opts = copy.deepcopy(opts_nosecrets)
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

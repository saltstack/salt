import asyncio
import copy

import salt.master
import salt.transport
from salt.utils.asynchronous import aioloop


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


def _validate_transport(opts):
    """Retain the pool routing API's error for unsupported transports."""
    ttype = opts.get("transport", "zeromq")
    if ttype not in salt.transport.TRANSPORTS:
        raise ValueError(f"Unsupported transport type: {ttype}")


def create_server_transport(opts):
    """Create a request server for pool routing."""
    _validate_transport(opts)
    return salt.transport.request_server(opts)


def create_client_transport(opts, io_loop):
    """Create a request client for pool routing, otherwise a publish client."""
    _validate_transport(opts)
    io_loop = aioloop(io_loop)
    if opts.get("workers_ipc_name") or opts.get("pool_name"):
        return salt.transport.request_client(opts, io_loop=io_loop)
    return salt.transport.publish_client(opts, io_loop)


def create_request_client(opts, io_loop=None):
    """Create a request client on the caller's event loop for pool routing."""
    _validate_transport(opts)
    io_loop = asyncio.get_event_loop() if io_loop is None else aioloop(io_loop)
    return salt.transport.request_client(opts, io_loop=io_loop)

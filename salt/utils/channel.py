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

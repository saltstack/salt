import copy


def iter_transport_opts(opts):
    """
    Yield transport, opts for all master configured transports
    """
    transports = set()

    for transport, opts_overrides in opts.get("transport_opts", {}).items():
        t_opts = copy.deepcopy(opts)
        t_opts.update(opts_overrides)
        t_opts["transport"] = transport
        transports.add(transport)
        yield transport, t_opts

    if opts["transport"] not in transports:
        yield opts["transport"], opts

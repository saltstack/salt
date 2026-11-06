"""
Salt multi-master cluster support (hash ring, coordination, consensus).
"""


def node_id(opts):
    """
    Return this master's cluster-wide identity.

    ``_master`` suffix is added by ``apply_master_config`` when ``id`` is not
    configured explicitly, and it is stripped there. It is used as ``peer_id``
    on the wire.
    """
    return opts["id"].removesuffix("_master")

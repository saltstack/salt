"""
This is the default ipcidr matcher.
"""

import logging

import salt.utils.network
from salt._compat import ipaddress

log = logging.getLogger(__name__)


def match(tgt, opts=None, minion_id=None):
    """
    Matches based on IP address or CIDR notation
    """
    if not opts:
        opts = __opts__

    try:
        # Target is an address?
        tgt = ipaddress.ip_address(tgt)
    except:  # pylint: disable=bare-except
        try:
            # Target is a network?
            tgt = ipaddress.ip_network(tgt)
        except:  # pylint: disable=bare-except
            log.error("Invalid IP/CIDR target: %s", tgt)
            return []
    proto = "ipv{}".format(tgt.version)

    grains = opts["grains"]

    if proto not in grains:
        match = False
    elif isinstance(tgt, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        match = str(tgt) in grains[proto]
    else:
        match = salt.utils.network.in_subnet(tgt, grains[proto])

    return match

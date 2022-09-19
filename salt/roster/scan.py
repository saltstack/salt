"""
Scan a netmask or ipaddr for open ssh ports
"""

import copy
import logging
import socket

import salt.utils.network
from salt._compat import ipaddress

log = logging.getLogger(__name__)


def targets(tgt, tgt_type="glob", **kwargs):
    """
    Return the targets from the flat yaml file, checks opts for location but
    defaults to /etc/salt/roster
    """
    rmatcher = RosterMatcher(tgt, tgt_type)
    return rmatcher.targets()


class RosterMatcher:
    """
    Matcher for the roster data structure
    """

    def __init__(self, tgt, tgt_type):
        self.tgt = tgt
        self.tgt_type = tgt_type

    def targets(self):
        """
        Return ip addrs based on netmask, sitting in the "glob" spot because
        it is the default
        """
        addrs = []
        ret = {}
        ports = __opts__["ssh_scan_ports"]
        if not isinstance(ports, list):
            # Comma-separate list of integers
            ports = list(map(int, str(ports).split(",")))
        if self.tgt_type == "list":
            tgts = self.tgt
        else:
            tgts = [self.tgt]
        for tgt in tgts:
            try:
                addrs.append(ipaddress.ip_address(tgt))
            except ValueError:
                try:
                    addrs.extend(ipaddress.ip_network(tgt).hosts())
                except ValueError:
                    pass
        for addr in addrs:
            addr = str(addr)
            ret[addr] = copy.deepcopy(__opts__.get("roster_defaults", {}))
            log.trace("Scanning host: %s", addr)
            for port in ports:
                log.trace("Scanning port: %s", port)
                try:
                    sock = salt.utils.network.get_socket(addr, socket.SOCK_STREAM)
                    sock.settimeout(float(__opts__["ssh_scan_timeout"]))
                    sock.connect((addr, port))
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                    ret[addr].update({"host": addr, "port": port})
                except OSError:
                    pass
        return ret

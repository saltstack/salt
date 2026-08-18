"""
This roster resolves hostname in a pdsh/clustershell style.

:depends: clustershell, https://github.com/cea-hpc/clustershell

When you want to use host globs for target matching, use ``--roster clustershell``. For example:

.. code-block:: bash

    salt-ssh --roster clustershell 'server_[1-10,21-30],test_server[5,7,9]' test.ping

"""

import copy
import socket

REQ_ERROR = None
try:
    from ClusterShell.NodeSet import NodeSet
except (ImportError, OSError) as e:
    REQ_ERROR = "ClusterShell import error, perhaps missing python ClusterShell package"


def __virtual__():
    return (REQ_ERROR is None, REQ_ERROR)


def targets(tgt, tgt_type="glob", **kwargs):
    """
    Return the targets
    """
    ret = {}
    ports = __opts__["ssh_scan_ports"]
    if not isinstance(ports, list):
        # Comma-separate list of integers
        ports = list(map(int, str(ports).split(",")))

    hosts = list(NodeSet(tgt))
    host_addrs = {h: socket.gethostbyname(h) for h in hosts}

    for host, addr in host_addrs.items():
        addr = str(addr)
        ret[host] = copy.deepcopy(__opts__.get("roster_defaults", {}))
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(float(__opts__["ssh_scan_timeout"]))
                sock.connect((addr, port))
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                ret[host].update({"host": addr, "port": port})
            except OSError:
                pass
    return ret

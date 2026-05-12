"""
The daemons package is used to store implementations of the Salt Master and
Minion enabling different transports.
"""

import logging
import sys
from collections.abc import Iterable, Mapping, Sequence

log = logging.getLogger(__name__)


def is_non_string_iterable(obj):
    """
    Returns True if obj is non-string iterable, False otherwise

    Future proof way that is compatible with both Python3 and Python2 to check
    for non string iterables.
    Assumes in Python3 that, basestring = (str, bytes)
    """
    return not isinstance(obj, str) and isinstance(obj, Iterable)


def is_non_string_sequence(obj):
    """
    Returns True if obj is non-string sequence, False otherwise

    Future proof way that is compatible with both Python3 and Python2 to check
    for non string sequences.
    Assumes in Python3 that, basestring = (str, bytes)
    """
    return not isinstance(obj, str) and isinstance(obj, Sequence)


def extract_masters(opts, masters="master", port=None, raise_if_empty=True):
    """
    Parses opts and generates a list of master (host,port) addresses.
    By default looks for list of masters in opts['master'] and uses
    opts['master_port'] as the default port when otherwise not provided.

    Use the opts key given by masters for the masters list, default is 'master'
    If parameter port is not None then uses the default port given by port


    Returns a list of host address dicts of the form

    [
        {
            'external': (host,port),
            'internal': (host, port)
        },
        ...

    ]

    When only one address is provided it is assigned to the external address field
    When not provided the internal address field is set to None.

    For a given master the syntax options are as follows:

    hostname [port]

    external: hostname [port]
    [internal: hostaddress [port]]

    Where the hostname string could be either an FQDN or host address
    in dotted number notation.
        master.example.com
        10.0.2.110

    And the hostadress is in dotted number notation

    The space delimited port is optional and if not provided a default is used.
    The internal address is optional and if not provided is set to None

    Examples showing the YAML in /etc/salt/master  conf file:

    1) Single host name string (fqdn or dotted address)
        a)
            master: me.example.com
        b)
            master: localhost
        c)
            master: 10.0.2.205

    2) Single host name string with port
        a)
            master: me.example.com 4506
        b)
            master: 10.0.2.205 4510

    3) Single master with external and optional internal host addresses for nat
       in a dict

        master:
            external: me.example.com 4506
            internal: 10.0.2.100 4506


    3) One or host host names with optional ports in a list

        master:
            - me.example.com 4506
            - you.example.com 4510
            - 8.8.8.8
            - they.example.com 4506
            - 8.8.4.4  4506

    4) One or more host name with external and optional internal host addresses
       for Nat  in a list of dicts

        master:
            -
                external: me.example.com 4506
                internal: 10.0.2.100 4506

            -
                external: you.example.com 4506
                internal: 10.0.2.101 4506

            -
                external: we.example.com

            - they.example.com
    """
    if port is not None:
        master_port = opts.get(port)
    else:
        master_port = opts.get("master_port")
    try:
        master_port = int(master_port)
    except ValueError:
        master_port = None

    if not master_port:
        emsg = "Invalid or missing opts['master_port']."
        log.error(emsg)
        raise ValueError(emsg)

    entries = opts.get(masters, [])

    if not entries:
        emsg = f"Invalid or missing opts['{masters}']."
        log.error(emsg)
        if raise_if_empty:
            raise ValueError(emsg)

    hostages = []
    # extract candidate hostage (hostname dict) from entries
    if is_non_string_sequence(entries):  # multiple master addresses provided
        for entry in entries:
            if isinstance(entry, Mapping):  # mapping
                external = entry.get("external", "")
                internal = entry.get("internal", "")
                hostages.append(dict(external=external, internal=internal))

            elif isinstance(entry, str):  # string
                external = entry
                internal = ""
                hostages.append(dict(external=external, internal=internal))

    elif isinstance(entries, Mapping):  # mapping
        external = entries.get("external", "")
        internal = entries.get("internal", "")
        hostages.append(dict(external=external, internal=internal))

    elif isinstance(entries, str):  # string
        external = entries
        internal = ""
        hostages.append(dict(external=external, internal=internal))

    # now parse each hostname string for host and optional port
    masters = []
    for hostage in hostages:
        external = hostage["external"]
        internal = hostage["internal"]
        if external:
            external = parse_hostname(external, master_port)
            if not external:
                continue  # must have a valid external host address
            internal = parse_hostname(internal, master_port)
            masters.append(dict(external=external, internal=internal))

    return masters


def parse_hostname(hostname, default_port):
    """
    Parse hostname string and return a tuple of (host, port)
    If port missing in hostname string then use default_port
    If anything is not a valid then return None

    hostname should contain a host and an option space delimited port
    host port

    As an attempt to prevent foolish mistakes the parser also tries to identify
    the port when it is colon delimited not space delimited. As in host:port.
    This is problematic since IPV6 addresses may have colons in them.
    Consequently the use of colon delimited ports is strongly discouraged.
    An ipv6 address must have at least 2 colons.
    """
    try:
        host, sep, port = hostname.strip().rpartition(" ")
        if not port:  # invalid nothing there
            return None

        if not host:  # no space separated port, only host as port use default port
            host = port
            port = default_port
            # ipv6 must have two or more colons
            if host.count(":") == 1:  # only one so may be using colon delimited port
                host, sep, port = host.rpartition(":")
                if not host:  # colon but not host so invalid
                    return None
                if not port:  # colon but no port so use default
                    port = default_port

        host = host.strip()
        try:
            port = int(port)
        except ValueError:
            return None

    except AttributeError:
        return None

    return (host, port)

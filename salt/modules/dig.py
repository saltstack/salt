# -*- coding: utf-8 -*-
"""
Compendium of generic DNS utilities.
The 'dig' command line tool must be installed in order to use this module.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import re

# Import salt libs
import salt.utils.network
import salt.utils.path
from salt.ext import six

log = logging.getLogger(__name__)

__virtualname__ = "dig"


def __virtual__():
    """
    Only load module if dig binary is present
    """
    if salt.utils.path.which("dig"):
        return __virtualname__
    return (
        False,
        "The dig execution module cannot be loaded: "
        "the dig binary is not in the path.",
    )


def check_ip(addr):
    """
    Check if address is a valid IP. returns True if valid, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.check_ip 127.0.0.1
        salt ns1 dig.check_ip 1111:2222:3333:4444:5555:6666:7777:8888
    """

    try:
        addr = addr.rsplit("/", 1)
    except AttributeError:
        # Non-string passed
        return False

    if salt.utils.network.is_ipv4(addr[0]):
        try:
            if 1 <= int(addr[1]) <= 32:
                return True
        except ValueError:
            # Non-int subnet notation
            return False
        except IndexError:
            # No subnet notation used (i.e. just an IPv4 address)
            return True

    if salt.utils.network.is_ipv6(addr[0]):
        try:
            if 8 <= int(addr[1]) <= 128:
                return True
        except ValueError:
            # Non-int subnet notation
            return False
        except IndexError:
            # No subnet notation used (i.e. just an IPv4 address)
            return True

    return False


def A(host, nameserver=None):
    """
    Return the A record for ``host``.

    Always returns a list.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.A www.google.com
    """
    dig = ["dig", "+short", six.text_type(host), "A"]

    if nameserver is not None:
        dig.append("@{0}".format(nameserver))

    cmd = __salt__["cmd.run_all"](dig, python_shell=False)
    # In this case, 0 is not the same as False
    if cmd["retcode"] != 0:
        log.warning(
            "dig returned exit code '{0}'. Returning empty list as "
            "fallback.".format(cmd["retcode"])
        )
        return []

    # make sure all entries are IPs
    return [x for x in cmd["stdout"].split("\n") if check_ip(x)]


def AAAA(host, nameserver=None):
    """
    Return the AAAA record for ``host``.

    Always returns a list.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.AAAA www.google.com
    """
    dig = ["dig", "+short", six.text_type(host), "AAAA"]

    if nameserver is not None:
        dig.append("@{0}".format(nameserver))

    cmd = __salt__["cmd.run_all"](dig, python_shell=False)
    # In this case, 0 is not the same as False
    if cmd["retcode"] != 0:
        log.warning(
            "dig returned exit code '{0}'. Returning empty list as "
            "fallback.".format(cmd["retcode"])
        )
        return []

    # make sure all entries are IPs
    return [x for x in cmd["stdout"].split("\n") if check_ip(x)]


def NS(domain, resolve=True, nameserver=None):
    """
    Return a list of IPs of the nameservers for ``domain``

    If ``resolve`` is False, don't resolve names.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.NS google.com
    """
    dig = ["dig", "+short", six.text_type(domain), "NS"]

    if nameserver is not None:
        dig.append("@{0}".format(nameserver))

    cmd = __salt__["cmd.run_all"](dig, python_shell=False)
    # In this case, 0 is not the same as False
    if cmd["retcode"] != 0:
        log.warning(
            "dig returned exit code '{0}'. Returning empty list as "
            "fallback.".format(cmd["retcode"])
        )
        return []

    if resolve:
        ret = []
        for ns_host in cmd["stdout"].split("\n"):
            for ip_addr in A(ns_host, nameserver):
                ret.append(ip_addr)
        return ret

    return cmd["stdout"].split("\n")


def SPF(domain, record="SPF", nameserver=None):
    """
    Return the allowed IPv4 ranges in the SPF record for ``domain``.

    If record is ``SPF`` and the SPF record is empty, the TXT record will be
    searched automatically. If you know the domain uses TXT and not SPF,
    specifying that will save a lookup.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.SPF google.com
    """
    spf_re = re.compile(r"(?:\+|~)?(ip[46]|include):(.+)")
    cmd = ["dig", "+short", six.text_type(domain), record]

    if nameserver is not None:
        cmd.append("@{0}".format(nameserver))

    result = __salt__["cmd.run_all"](cmd, python_shell=False)
    # In this case, 0 is not the same as False
    if result["retcode"] != 0:
        log.warning(
            "dig returned exit code '{0}'. Returning empty list as fallback.".format(
                result["retcode"]
            )
        )
        return []

    if result["stdout"] == "" and record == "SPF":
        # empty string is successful query, but nothing to return. So, try TXT
        # record.
        return SPF(domain, "TXT", nameserver)

    sections = re.sub('"', "", result["stdout"]).split()
    if len(sections) == 0 or sections[0] != "v=spf1":
        return []

    if sections[1].startswith("redirect="):
        # Run a lookup on the part after 'redirect=' (9 chars)
        return SPF(sections[1][9:], "SPF", nameserver)
    ret = []
    for section in sections[1:]:
        try:
            mechanism, address = spf_re.match(section).groups()
        except AttributeError:
            # Regex was not matched
            continue
        if mechanism == "include":
            ret.extend(SPF(address, "SPF", nameserver))
        elif mechanism in ("ip4", "ip6") and check_ip(address):
            ret.append(address)
    return ret


def MX(domain, resolve=False, nameserver=None):
    """
    Return a list of lists for the MX of ``domain``.

    If the ``resolve`` argument is True, resolve IPs for the servers.

    It's limited to one IP, because although in practice it's very rarely a
    round robin, it is an acceptable configuration and pulling just one IP lets
    the data be similar to the non-resolved version. If you think an MX has
    multiple IPs, don't use the resolver here, resolve them in a separate step.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.MX google.com
    """
    dig = ["dig", "+short", six.text_type(domain), "MX"]

    if nameserver is not None:
        dig.append("@{0}".format(nameserver))

    cmd = __salt__["cmd.run_all"](dig, python_shell=False)
    # In this case, 0 is not the same as False
    if cmd["retcode"] != 0:
        log.warning(
            "dig returned exit code '{0}'. Returning empty list as "
            "fallback.".format(cmd["retcode"])
        )
        return []

    stdout = [x.split() for x in cmd["stdout"].split("\n")]

    if resolve:
        return [(lambda x: [x[0], A(x[1], nameserver)[0]])(x) for x in stdout]

    return stdout


def TXT(host, nameserver=None):
    """
    Return the TXT record for ``host``.

    Always returns a list.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.TXT google.com
    """
    dig = ["dig", "+short", six.text_type(host), "TXT"]

    if nameserver is not None:
        dig.append("@{0}".format(nameserver))

    cmd = __salt__["cmd.run_all"](dig, python_shell=False)

    if cmd["retcode"] != 0:
        log.warning(
            "dig returned exit code '{0}'. Returning empty list as "
            "fallback.".format(cmd["retcode"])
        )
        return []

    return [i for i in cmd["stdout"].split("\n")]


# Let lowercase work, since that is the convention for Salt functions
a = A
aaaa = AAAA
ns = NS
spf = SPF
mx = MX

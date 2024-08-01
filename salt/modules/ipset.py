"""
Support for ipset
"""

import logging

import salt.utils.path
from salt._compat import ipaddress

log = logging.getLogger(__name__)


_IPSET_FAMILIES = {
    "ipv4": "inet",
    "ip4": "inet",
    "ipv6": "inet6",
    "ip6": "inet6",
}

_IPSET_SET_TYPES = {
    "bitmap:ip",
    "bitmap:ip,mac",
    "bitmap:port",
    "hash:ip",
    "hash:mac",
    "hash:ip,port",
    "hash:ip,port,ip",
    "hash:ip,port,net",
    "hash:net",
    "hash:net,net",
    "hash:net,iface",
    "hash:net,port",
    "hash:net,port,net",
    "hash:ip,mark",
    "list:set",
}


_CREATE_OPTIONS = {
    "bitmap:ip": {"range", "netmask", "timeout", "counters", "comment", "skbinfo"},
    "bitmap:ip,mac": {"range", "timeout", "counters", "comment", "skbinfo"},
    "bitmap:port": {"range", "timeout", "counters", "comment", "skbinfo"},
    "hash:ip": {
        "family",
        "hashsize",
        "maxelem",
        "netmask",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "hash:mac": {"hashsize", "maxelem", "timeout", "counters", "comment", "skbinfo"},
    "hash:net": {
        "family",
        "hashsize",
        "maxelem",
        "netmask",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "hash:net,net": {
        "family",
        "hashsize",
        "maxelem",
        "netmask",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "hash:net,port": {
        "family",
        "hashsize",
        "maxelem",
        "netmask",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "hash:net,port,net": {
        "family",
        "hashsize",
        "maxelem",
        "netmask",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "hash:ip,port,ip": {
        "family",
        "hashsize",
        "maxelem",
        "netmask",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "hash:ip,port,net": {
        "family",
        "hashsize",
        "maxelem",
        "netmask",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "hash:ip,port": {
        "family",
        "hashsize",
        "maxelem",
        "netmask",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "hash:ip,mark": {
        "family",
        "markmask",
        "hashsize",
        "maxelem",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "hash:net,iface": {
        "family",
        "hashsize",
        "maxelem",
        "netmask",
        "timeout",
        "counters",
        "comment",
        "skbinfo",
    },
    "list:set": {"size", "timeout", "counters", "comment"},
}

_CREATE_OPTIONS_WITHOUT_VALUE = {"comment", "counters", "skbinfo"}

_CREATE_OPTIONS_REQUIRED = {
    "bitmap:ip": ["range"],
    "bitmap:ip,mac": ["range"],
    "bitmap:port": ["range"],
    "hash:ip": [],
    "hash:mac": [],
    "hash:net": [],
    "hash:net,net": [],
    "hash:ip,port": [],
    "hash:net,port": [],
    "hash:ip,port,ip": [],
    "hash:ip,port,net": [],
    "hash:net,port,net": [],
    "hash:net,iface": [],
    "hash:ip,mark": [],
    "list:set": [],
}


_ADD_OPTIONS = {
    "bitmap:ip": {"timeout", "packets", "bytes", "skbmark", "skbprio", "skbqueue"},
    "bitmap:ip,mac": {"timeout", "packets", "bytes", "skbmark", "skbprio", "skbqueue"},
    "bitmap:port": {"timeout", "packets", "bytes", "skbmark", "skbprio"},
    "hash:ip": {"timeout", "packets", "bytes", "skbmark", "skbprio", "skbqueue"},
    "hash:mac": {"timeout", "packets", "bytes", "skbmark", "skbprio", "skbqueue"},
    "hash:net": {
        "timeout",
        "nomatch",
        "packets",
        "bytes",
        "skbmark",
        "skbprio",
        "skbqueue",
    },
    "hash:net,net": {
        "timeout",
        "nomatch",
        "packets",
        "bytes",
        "skbmark",
        "skbprio",
        "skbqueue",
    },
    "hash:net,port": {
        "timeout",
        "nomatch",
        "packets",
        "bytes",
        "skbmark",
        "skbprio",
        "skbqueue",
    },
    "hash:net,port,net": {
        "timeout",
        "nomatch",
        "packets",
        "bytes",
        "skbmark",
        "skbprio",
        "skbqueue",
    },
    "hash:ip,port,ip": {
        "timeout",
        "packets",
        "bytes",
        "skbmark",
        "skbprio",
        "skbqueue",
    },
    "hash:ip,port,net": {
        "timeout",
        "nomatch",
        "packets",
        "bytes",
        "skbmark",
        "skbprio",
        "skbqueue",
    },
    "hash:ip,port": {
        "timeout",
        "nomatch",
        "packets",
        "bytes",
        "skbmark",
        "skbprio",
        "skbqueue",
    },
    "hash:net,iface": {
        "timeout",
        "nomatch",
        "packets",
        "bytes",
        "skbmark",
        "skbprio",
        "skbqueue",
    },
    "hash:ip,mark": {"timeout", "packets", "bytes", "skbmark", "skbprio", "skbqueue"},
    "list:set": {"timeout", "packets", "bytes", "skbmark", "skbprio", "skbqueue"},
}

__virtualname__ = "ipset"


def __virtual__():
    """
    Only load the module if ipset is installed
    """
    if salt.utils.path.which("ipset"):
        return True
    return (
        False,
        "The ipset execution modules cannot be loaded: ipset binary not in path.",
    )


def _ipset_cmd():
    """
    Return correct command
    """
    return salt.utils.path.which("ipset")


def version():
    """
    Return version from ipset --version

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.version

    """
    cmd = [_ipset_cmd(), "--version"]
    out = __salt__["cmd.run"](cmd, python_shell=False).split()
    return out[1]


def new_set(name=None, set_type=None, family="ipv4", comment=False, **kwargs):
    """
    .. versionadded:: 2014.7.0

    Create new custom set

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.new_set custom_set list:set

        salt '*' ipset.new_set custom_set list:set comment=True

        IPv6:
        salt '*' ipset.new_set custom_set list:set family=ipv6
    """
    ipset_family = _IPSET_FAMILIES[family]
    if not name:
        return "Error: Set Name needs to be specified"

    if not set_type:
        return "Error: Set Type needs to be specified"

    if set_type not in _IPSET_SET_TYPES:
        return "Error: Set Type is invalid"

    # Check for required arguments
    for item in _CREATE_OPTIONS_REQUIRED[set_type]:
        if item not in kwargs:
            return f"Error: {item} is a required argument"

    cmd = [_ipset_cmd(), "create", name, set_type]

    for item in _CREATE_OPTIONS[set_type]:
        if item in kwargs:
            if item in _CREATE_OPTIONS_WITHOUT_VALUE:
                cmd.append(item)
            else:
                cmd.extend([item, kwargs[item]])

    # Family only valid for certain set types
    if "family" in _CREATE_OPTIONS[set_type]:
        cmd.extend(["family", ipset_family])

    if comment:
        cmd.append("comment")

    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        out = True
    return out


def delete_set(name=None, family="ipv4"):
    """
    .. versionadded:: 2014.7.0

    Delete ipset set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.delete_set custom_set

        IPv6:
        salt '*' ipset.delete_set custom_set family=ipv6
    """

    if not name:
        return "Error: Set needs to be specified"

    cmd = [_ipset_cmd(), "destroy", name]
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        out = True
    return out


def rename_set(name=None, new_set=None, family="ipv4"):
    """
    .. versionadded:: 2014.7.0

    Delete ipset set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.rename_set custom_set new_set=new_set_name

        IPv6:
        salt '*' ipset.rename_set custom_set new_set=new_set_name family=ipv6
    """

    if not name:
        return "Error: Set needs to be specified"

    if not new_set:
        return "Error: New name for set needs to be specified"

    settype = _find_set_type(name)
    if not settype:
        return "Error: Set does not exist"

    settype = _find_set_type(new_set)
    if settype:
        return "Error: New Set already exists"

    cmd = [_ipset_cmd(), "rename", name, new_set]
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        out = True
    return out


def list_sets(family="ipv4"):
    """
    .. versionadded:: 2014.7.0

    List all ipset sets.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.list_sets

    """
    cmd = [_ipset_cmd(), "list", "-t"]
    out = __salt__["cmd.run"](cmd, python_shell=False)

    _tmp = out.split("\n")

    count = 0
    sets = []
    sets.append({})
    for item in _tmp:
        if not item:
            count = count + 1
            sets.append({})
            continue
        key, value = item.split(":", 1)
        sets[count][key] = value[1:]
    return sets


def check_set(name=None, family="ipv4"):
    """
    Check that given ipset set exists.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.check_set name

    """
    if not name:
        return "Error: Set needs to be specified"

    setinfo = _find_set_info(name)
    if not setinfo:
        return False
    return True


def add(name=None, entry=None, family="ipv4", **kwargs):
    """
    Append an entry to the specified set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.add name 192.168.1.26

        salt '*' ipset.add name 192.168.0.3,AA:BB:CC:DD:EE:FF

    """
    if not name:
        return "Error: Set needs to be specified"
    if not entry:
        return "Error: Entry needs to be specified"

    setinfo = _find_set_info(name)
    if not setinfo:
        return f"Error: Set {name} does not exist"

    settype = setinfo["Type"]

    cmd = [_ipset_cmd(), "add", "-exist", name] + entry.split()

    if "timeout" in kwargs:
        if "timeout" not in setinfo["Header"]:
            return f"Error: Set {name} not created with timeout support"

    if "packets" in kwargs or "bytes" in kwargs:
        if "counters" not in setinfo["Header"]:
            return f"Error: Set {name} not created with counters support"

    if "comment" in kwargs:
        if "comment" not in setinfo["Header"]:
            return f"Error: Set {name} not created with comment support"
        if "comment" not in entry:
            cmd = cmd + ["comment", f"{kwargs['comment']}"]

    if {"skbmark", "skbprio", "skbqueue"} & set(kwargs.keys()):
        if "skbinfo" not in setinfo["Header"]:
            return f"Error: Set {name} not created with skbinfo support"

    for item in _ADD_OPTIONS[settype]:
        if item in kwargs:
            cmd.extend([item, kwargs[item]])

    current_members = _find_set_members(name)
    if entry in current_members:
        return f"Warn: Entry {entry} already exists in set {name}"

    # Using -exist to ensure entries are updated if the comment changes
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        return "Success"
    return f"Error: {out}"


def delete(name=None, entry=None, family="ipv4", **kwargs):
    """
    Delete an entry from the specified set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.delete name 192.168.0.3,AA:BB:CC:DD:EE:FF

    """
    if not name:
        return "Error: Set needs to be specified"
    if not entry:
        return "Error: Entry needs to be specified"

    settype = _find_set_type(name)

    if not settype:
        return f"Error: Set {name} does not exist"

    cmd = [_ipset_cmd(), "del", name, entry]
    out = __salt__["cmd.run"](cmd, python_shell=False)

    if not out:
        return "Success"
    return f"Error: {out}"


def check(name=None, entry=None, family="ipv4"):
    """
    Check that an entry exists in the specified set.

    name
        The ipset name

    entry
        An entry in the ipset.  This parameter can be a single IP address, a
        range of IP addresses, or a subnet block.  Example:

        .. code-block:: cfg

            192.168.0.1
            192.168.0.2-192.168.0.19
            192.168.0.0/25

    family
        IP protocol version: ipv4 or ipv6

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.check name '192.168.0.1 comment "Hello"'

    """
    if not name:
        return "Error: Set needs to be specified"
    if not entry:
        return "Error: Entry needs to be specified"

    settype = _find_set_type(name)
    if not settype:
        return f"Error: Set {name} does not exist"

    current_members = _parse_members(settype, _find_set_members(name))

    if not current_members:
        return False

    if isinstance(entry, list):
        entries = _parse_members(settype, entry)
    else:
        entries = [_parse_member(settype, entry)]

    for current_member in current_members:
        for entry in entries:
            if _member_contains(current_member, entry):
                return True

    return False


def test(name=None, entry=None, family="ipv4", **kwargs):
    """
    Test if an entry is in the specified set.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.test name 192.168.0.2

        IPv6:
        salt '*' ipset.test name fd81:fc56:9ac7::/48
    """
    if not name:
        return "Error: Set needs to be specified"
    if not entry:
        return "Error: Entry needs to be specified"

    settype = _find_set_type(name)
    if not settype:
        return f"Error: Set {name} does not exist"

    cmd = [_ipset_cmd(), "test", name, entry]
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    if out["retcode"] > 0:
        # Entry doesn't exist in set return false
        return False

    return True


def flush(name=None, family="ipv4"):
    """
    Flush entries in the specified set,
    Flush all sets if set is not specified.

    CLI Example:

    .. code-block:: bash

        salt '*' ipset.flush

        salt '*' ipset.flush set

        IPv6:
        salt '*' ipset.flush

        salt '*' ipset.flush set
    """

    cmd = [_ipset_cmd(), "flush"]
    if name:
        cmd.append(name)
    out = __salt__["cmd.run"](cmd, python_shell=False)

    return not out


def _find_set_members(name):
    """
    Return list of members for a set
    """

    cmd = [_ipset_cmd(), "list", name]
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    if out["retcode"] > 0:
        # Set doesn't exist return false
        return False

    _tmp = out["stdout"].split("\n")
    members = []
    startMembers = False
    for i in _tmp:
        if startMembers:
            members.append(i)
        if "Members:" in i:
            startMembers = True
    return members


def _find_set_info(name):
    """
    Return information about the set
    """

    cmd = [_ipset_cmd(), "list", "-t", name]
    out = __salt__["cmd.run_all"](cmd, python_shell=False)

    if out["retcode"] > 0:
        # Set doesn't exist return false
        return False

    setinfo = {}
    _tmp = out["stdout"].split("\n")
    for item in _tmp:
        # Only split if item has a colon
        if ":" in item:
            key, value = item.split(":", 1)
            setinfo[key] = value[1:]
    return setinfo


def _find_set_type(name):
    """
    Find the type of the set
    """
    setinfo = _find_set_info(name)

    if setinfo:
        return setinfo["Type"]
    else:
        return False


def _parse_members(settype, members):
    if isinstance(members, str):

        return [_parse_member(settype, members)]

    return [_parse_member(settype, member) for member in members]


def _parse_member(settype, member, strict=False):
    subtypes = settype.split(":")[1].split(",")

    all_parts = member.split(" ", 1)
    parts = all_parts[0].split(",")

    parsed_member = []
    for i, subtype in enumerate(subtypes):
        part = parts[i]

        if subtype in ["ip", "net"]:
            try:
                if "/" in part:
                    part = ipaddress.ip_network(part, strict=strict)
                elif "-" in part:
                    start, end = list(map(ipaddress.ip_address, part.split("-")))

                    part = list(ipaddress.summarize_address_range(start, end))
                else:
                    part = ipaddress.ip_address(part)
            except ValueError:
                pass

        elif subtype == "port":
            part = int(part)

        parsed_member.append(part)

    if len(all_parts) > 1:
        parsed_member.append(all_parts[1])

    return parsed_member


def _members_contain(members, entry):
    pass


def _member_contains(member, entry):
    if len(member) < len(entry):
        return False

    for i, _entry in enumerate(entry):
        if not _compare_member_parts(member[i], _entry):
            return False

    return True


def _compare_member_parts(member_part, entry_part):
    if member_part == entry_part:
        # this covers int, string, and equal ip and net
        return True

    # for ip ranges parsed with summarize_address_range
    if isinstance(entry_part, list):
        for entry_part_item in entry_part:
            if not _compare_member_parts(member_part, entry_part_item):
                return False

        return True

    # below we only deal with ip and net objects
    if _is_address(member_part):
        if _is_network(entry_part):
            return member_part in entry_part

    elif _is_network(member_part):
        if _is_address(entry_part):
            return entry_part in member_part

        # both are networks, and == was false
        return False

        # This could be changed to support things like
        # 192.168.0.4/30 contains 192.168.0.4/31
        #
        # return entry_part.network_address in member_part \
        #    and entry_part.broadcast_address in member_part

    return False


def _is_network(o):
    return isinstance(o, (ipaddress.IPv4Network, ipaddress.IPv6Network))


def _is_address(o):
    return isinstance(o, (ipaddress.IPv4Address, ipaddress.IPv6Address))

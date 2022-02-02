"""
Module for gathering and managing bridging information
"""

import re
import sys

import salt.utils.path

__func_alias__ = {"list_": "list"}


# Other BSD-like derivatives that use ifconfig may work too
SUPPORTED_BSD_LIKE = ["FreeBSD", "NetBSD", "OpenBSD"]


def __virtual__():
    """
    Confirm this module is supported by the OS and the system has
    required tools
    """
    supported_os_tool = {
        "FreeBSD": "ifconfig",
        "Linux": "brctl",
        "NetBSD": "brconfig",
        "OpenBSD": "ifconfig",
    }
    cur_os = __grains__["kernel"]
    for _os in supported_os_tool:
        if cur_os == _os and salt.utils.path.which(supported_os_tool[cur_os]):
            return True
    return (
        False,
        "The bridge execution module failed to load: requires one of the following"
        " tool/os combinations: ifconfig on FreeBSD/OpenBSD, brctl on Linux or brconfig"
        " on NetBSD.",
    )


def _tool_path(ostool):
    """
    Internal, returns tools path
    """
    return salt.utils.path.which(ostool)


def _linux_brshow(br=None):
    """
    Internal, returns bridges and enslaved interfaces (GNU/Linux - brctl)
    """
    brctl = _tool_path("brctl")

    if br:
        cmd = "{} show {}".format(brctl, br)
    else:
        cmd = "{} show".format(brctl)

    brs = {}

    for line in __salt__["cmd.run"](cmd, python_shell=False).splitlines():
        # get rid of first line
        if line.startswith("bridge name"):
            continue
        # get rid of ^\n's
        vals = line.split()
        if not vals:
            continue

        # bridge name bridge id       STP enabled interfaces
        # br0       8000.e4115bac8ddc   no      eth0
        #                                       foo0
        # br1       8000.e4115bac8ddc   no      eth1
        if len(vals) > 1:
            brname = vals[0]

            brs[brname] = {
                "id": vals[1],
                "stp": vals[2],
            }
            if len(vals) > 3:
                brs[brname]["interfaces"] = [vals[3]]

        if len(vals) == 1 and brname:
            brs[brname]["interfaces"].append(vals[0])

    if br:
        try:
            return brs[br]
        except KeyError:
            return None
    return brs


def _linux_bradd(br):
    """
    Internal, creates the bridge
    """
    brctl = _tool_path("brctl")
    return __salt__["cmd.run"]("{} addbr {}".format(brctl, br), python_shell=False)


def _linux_brdel(br):
    """
    Internal, deletes the bridge
    """
    brctl = _tool_path("brctl")
    return __salt__["cmd.run"]("{} delbr {}".format(brctl, br), python_shell=False)


def _linux_addif(br, iface):
    """
    Internal, adds an interface to a bridge
    """
    brctl = _tool_path("brctl")
    return __salt__["cmd.run"](
        "{} addif {} {}".format(brctl, br, iface), python_shell=False
    )


def _linux_delif(br, iface):
    """
    Internal, removes an interface from a bridge
    """
    brctl = _tool_path("brctl")
    return __salt__["cmd.run"](
        "{} delif {} {}".format(brctl, br, iface), python_shell=False
    )


def _linux_stp(br, state):
    """
    Internal, sets STP state
    """
    brctl = _tool_path("brctl")
    return __salt__["cmd.run"](
        "{} stp {} {}".format(brctl, br, state), python_shell=False
    )


def _bsd_brshow(br=None):
    """
    Internal, returns bridges and member interfaces (BSD-like: ifconfig)
    """
    if __grains__["kernel"] == "NetBSD":
        return _netbsd_brshow(br)

    ifconfig = _tool_path("ifconfig")

    ifaces = {}

    if br:
        ifaces[br] = br
    else:
        cmd = "{} -g bridge".format(ifconfig)
        for line in __salt__["cmd.run"](cmd, python_shell=False).splitlines():
            ifaces[line] = line

    brs = {}

    for iface in ifaces:
        cmd = "{} {}".format(ifconfig, iface)
        for line in __salt__["cmd.run"](cmd, python_shell=False).splitlines():
            brs[iface] = {"interfaces": [], "stp": "no"}
            line = line.lstrip()
            if line.startswith("member:"):
                brs[iface]["interfaces"].append(line.split(" ")[1])
                if "STP" in line:
                    brs[iface]["stp"] = "yes"

    if br:
        return brs[br]
    return brs


def _netbsd_brshow(br=None):
    """
    Internal, returns bridges and enslaved interfaces (NetBSD - brconfig)
    """
    brconfig = _tool_path("brconfig")

    if br:
        cmd = "{} {}".format(brconfig, br)
    else:
        cmd = "{} -a".format(brconfig)

    brs = {}
    start_int = False

    for line in __salt__["cmd.run"](cmd, python_shell=False).splitlines():
        if line.startswith("bridge"):
            start_int = False
            brname = line.split(":")[0]  # on NetBSD, always ^bridge([0-9]+):
            brs[brname] = {"interfaces": [], "stp": "no"}
        if "Interfaces:" in line:
            start_int = True
            continue
        if start_int and brname:
            m = re.match(r"\s*([a-z0-9]+)\s.*<.*>", line)
            if m:
                brs[brname]["interfaces"].append(m.group(1))
                if "STP" in line:
                    brs[brname]["stp"] = "yes"

    if br:
        try:
            return brs[br]
        except KeyError:
            return None
    return brs


def _bsd_bradd(br):
    """
    Internal, creates the bridge
    """
    kernel = __grains__["kernel"]
    ifconfig = _tool_path("ifconfig")

    if not br:
        return False

    if (
        __salt__["cmd.retcode"](
            "{} {} create up".format(ifconfig, br), python_shell=False
        )
        != 0
    ):
        return False

    # NetBSD is two cmds
    if kernel == "NetBSD":
        brconfig = _tool_path("brconfig")
        if (
            __salt__["cmd.retcode"]("{} {} up".format(brconfig, br), python_shell=False)
            != 0
        ):
            return False

    return True


def _bsd_brdel(br):
    """
    Internal, deletes the bridge
    """
    ifconfig = _tool_path("ifconfig")
    if not br:
        return False
    return __salt__["cmd.run"]("{} {} destroy".format(ifconfig, br), python_shell=False)


def _bsd_addif(br, iface):
    """
    Internal, adds an interface to a bridge
    """
    kernel = __grains__["kernel"]
    if kernel == "NetBSD":
        cmd = _tool_path("brconfig")
        brcmd = "add"
    else:
        cmd = _tool_path("ifconfig")
        brcmd = "addem"

    if not br or not iface:
        return False

    return __salt__["cmd.run"](
        "{} {} {} {}".format(cmd, br, brcmd, iface), python_shell=False
    )


def _bsd_delif(br, iface):
    """
    Internal, removes an interface from a bridge
    """
    kernel = __grains__["kernel"]
    if kernel == "NetBSD":
        cmd = _tool_path("brconfig")
        brcmd = "delete"
    else:
        cmd = _tool_path("ifconfig")
        brcmd = "deletem"

    if not br or not iface:
        return False

    return __salt__["cmd.run"](
        "{} {} {} {}".format(cmd, br, brcmd, iface), python_shell=False
    )


def _bsd_stp(br, state, iface):
    """
    Internal, sets STP state. On BSD-like, it is required to specify the
    STP physical interface
    """
    kernel = __grains__["kernel"]
    if kernel == "NetBSD":
        cmd = _tool_path("brconfig")
    else:
        cmd = _tool_path("ifconfig")

    if not br or not iface:
        return False

    return __salt__["cmd.run"](
        "{} {} {} {}".format(cmd, br, state, iface), python_shell=False
    )


def _os_dispatch(func, *args, **kwargs):
    """
    Internal, dispatches functions by operating system
    """
    if __grains__["kernel"] in SUPPORTED_BSD_LIKE:
        kernel = "bsd"
    else:
        kernel = __grains__["kernel"].lower()

    _os_func = getattr(sys.modules[__name__], "_{}_{}".format(kernel, func))

    if callable(_os_func):
        return _os_func(*args, **kwargs)


# End of internal functions


def show(br=None):
    """
    Returns bridges interfaces along with enslaved physical interfaces. If
    no interface is given, all bridges are shown, else only the specified
    bridge values are returned.

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.show
        salt '*' bridge.show br0
    """
    return _os_dispatch("brshow", br)


def list_():
    """
    Returns the machine's bridges list

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.list
    """
    brs = _os_dispatch("brshow")
    if not brs:
        return None
    brlist = []
    for br in brs:
        brlist.append(br)

    return brlist


def interfaces(br=None):
    """
    Returns interfaces attached to a bridge

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.interfaces br0
    """
    if not br:
        return None

    br_ret = _os_dispatch("brshow", br)
    if br_ret:
        return br_ret["interfaces"]


def find_interfaces(*args):
    """
    Returns the bridge to which the interfaces are bond to

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.find_interfaces eth0 [eth1...]
    """
    brs = _os_dispatch("brshow")
    if not brs:
        return None

    iflist = {}

    for iface in args:
        for br in brs:
            try:  # a bridge may not contain interfaces
                if iface in brs[br]["interfaces"]:
                    iflist[iface] = br
            except Exception:  # pylint: disable=broad-except
                pass

    return iflist


def add(br=None):
    """
    Creates a bridge

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.add br0
    """
    return _os_dispatch("bradd", br)


def delete(br=None):
    """
    Deletes a bridge

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.delete br0
    """
    return _os_dispatch("brdel", br)


def addif(br=None, iface=None):
    """
    Adds an interface to a bridge

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.addif br0 eth0
    """
    return _os_dispatch("addif", br, iface)


def delif(br=None, iface=None):
    """
    Removes an interface from a bridge

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.delif br0 eth0
    """
    return _os_dispatch("delif", br, iface)


def stp(br=None, state="disable", iface=None):
    """
    Sets Spanning Tree Protocol state for a bridge

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.stp br0 enable
        salt '*' bridge.stp br0 disable

    For BSD-like operating systems, it is required to add the interface on
    which to enable the STP.

    CLI Example:

    .. code-block:: bash

        salt '*' bridge.stp bridge0 enable fxp0
        salt '*' bridge.stp bridge0 disable fxp0
    """
    kernel = __grains__["kernel"]
    if kernel == "Linux":
        states = {"enable": "on", "disable": "off"}
        return _os_dispatch("stp", br, states[state])
    elif kernel in SUPPORTED_BSD_LIKE:
        states = {"enable": "stp", "disable": "-stp"}
        return _os_dispatch("stp", br, states[state], iface)
    else:
        return False


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

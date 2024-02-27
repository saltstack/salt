"""
Module for viewing and modifying sysctl parameters
"""

import os
import re

import salt.utils.data
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = "sysctl"


def __virtual__():
    """
    Only run on NetBSD systems
    """
    if __grains__["os"] == "NetBSD":
        return __virtualname__
    return (
        False,
        "The netbsd_sysctl execution module failed to load: only available on NetBSD.",
    )


def show(config_file=False):
    """
    Return a list of sysctl parameters for this minion

    config: Pull the data from the system configuration file
        instead of the live data.

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.show
    """
    roots = (
        "kern",
        "vm",
        "vfs",
        "net",
        "hw",
        "machdep",
        "user",
        "ddb",
        "proc",
        "emul",
        "security",
        "init",
    )
    cmd = "sysctl -ae"
    ret = {}
    out = __salt__["cmd.run"](cmd, output_loglevel="trace")
    comps = [""]
    for line in out.splitlines():
        if any([line.startswith(f"{root}.") for root in roots]):
            comps = re.split("[=:]", line, 1)
            ret[comps[0]] = comps[1]
        elif comps[0]:
            ret[comps[0]] += f"{line}\n"
        else:
            continue
    return ret


def get(name):
    """
    Return a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.get hw.physmem
    """
    cmd = f"sysctl -n {name}"
    out = __salt__["cmd.run"](cmd, python_shell=False)
    return out


def assign(name, value):
    """
    Assign a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.assign net.inet.icmp.icmplim 50
    """
    ret = {}
    cmd = f'sysctl -w {name}="{value}"'
    data = __salt__["cmd.run_all"](cmd, python_shell=False)

    if data["retcode"] != 0:
        raise CommandExecutionError("sysctl failed: {}".format(data["stderr"]))
    new_name, new_value = data["stdout"].split(":", 1)
    ret[new_name] = new_value.split(" -> ")[-1]
    return ret


def persist(name, value, config="/etc/sysctl.conf"):
    """
    Assign and persist a simple sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.persist net.inet.icmp.icmplim 50
    """
    nlines = []
    edited = False
    value = str(value)

    # create /etc/sysctl.conf if not present
    if not os.path.isfile(config):
        try:
            with salt.utils.files.fopen(config, "w+"):
                pass
        except OSError:
            msg = "Could not create {0}"
            raise CommandExecutionError(msg.format(config))

    with salt.utils.files.fopen(config, "r") as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line)
            m = re.match(rf"{name}(\??=)", line)
            if not m:
                nlines.append(line)
                continue
            else:
                key, rest = line.split("=", 1)
                if rest.startswith('"'):
                    _, rest_v, rest = rest.split('"', 2)
                elif rest.startswith("'"):
                    _, rest_v, rest = rest.split("'", 2)
                else:
                    rest_v = rest.split()[0]
                    rest = rest[len(rest_v) :]
                if rest_v == value:
                    return "Already set"
                new_line = f"{name}{m.group(1)}{value}{rest}"
                nlines.append(new_line)
                edited = True

    if not edited:
        newline = f"{name}={value}"
        nlines.append(f"{newline}\n")

    with salt.utils.files.fopen(config, "wb") as ofile:
        ofile.writelines(salt.utils.data.encode(nlines))

    assign(name, value)

    return "Updated"

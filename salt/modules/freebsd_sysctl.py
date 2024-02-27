"""
Module for viewing and modifying sysctl parameters
"""

import logging
import os

import salt.utils.files
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = "sysctl"

# Get logging started
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only runs on FreeBSD systems
    """
    if __grains__["os"] == "FreeBSD":
        return __virtualname__
    return (
        False,
        "The freebsd_sysctl execution module cannot be loaded: "
        "only available on FreeBSD systems.",
    )


def _formatfor(name, value, config, tail=""):
    if config == "/boot/loader.conf":
        return f'{name}="{value}"{tail}'
    else:
        return f"{name}={value}{tail}"


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
        "compat",
        "debug",
        "dev",
        "hptmv",
        "hw",
        "kern",
        "machdep",
        "net",
        "p1003_1b",
        "security",
        "user",
        "vfs",
        "vm",
    )
    cmd = "sysctl -ae"
    ret = {}
    comps = [""]

    if config_file:
        # If the file doesn't exist, return an empty list
        if not os.path.exists(config_file):
            return []

        try:
            with salt.utils.files.fopen(config_file, "r") as f:
                for line in f.readlines():
                    l = line.strip()
                    if l != "" and not l.startswith("#"):
                        comps = line.split("=", 1)
                        ret[comps[0]] = comps[1]
            return ret
        except OSError:
            log.error("Could not open sysctl config file")
            return None
    else:
        out = __salt__["cmd.run"](cmd, output_loglevel="trace")
        value = None
        for line in out.splitlines():
            if any([line.startswith(f"{root}.") for root in roots]):
                if value is not None:
                    ret[key] = "\n".join(value)
                (key, firstvalue) = line.split("=", 1)
                value = [firstvalue]
            elif value is not None:
                value.append(f"{line}")
        if value is not None:
            ret[key] = "\n".join(value)
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
    cmd = f'sysctl {name}="{value}"'
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
        salt '*' sysctl.persist coretemp_load NO config=/boot/loader.conf
    """
    nlines = []
    edited = False
    value = str(value)

    with salt.utils.files.fopen(config, "r") as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line).rstrip("\n")
            if not line.startswith(f"{name}="):
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
                    # If it is correct in the config file, check in memory
                    if str(get(name)) != value:
                        assign(name, value)
                        return "Updated"
                    else:
                        return "Already set"
                new_line = _formatfor(key, value, config, rest)
                nlines.append(new_line)
                edited = True
    if not edited:
        nlines.append(f"{_formatfor(name, value, config)}\n")
    with salt.utils.files.fopen(config, "w+") as ofile:
        nlines = [salt.utils.stringutils.to_str(_l) + "\n" for _l in nlines]
        ofile.writelines(nlines)
    if config != "/boot/loader.conf":
        assign(name, value)
    return "Updated"

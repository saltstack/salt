# -*- coding: utf-8 -*-
"""
The jail module for FreeBSD
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import re
import subprocess

# Import salt libs
import salt.utils.args
import salt.utils.files
import salt.utils.stringutils

# Define the module's virtual name
__virtualname__ = "jail"


def __virtual__():
    """
    Only runs on FreeBSD systems
    """
    if __grains__["os"] == "FreeBSD":
        return __virtualname__
    return (
        False,
        "The freebsdjail execution module cannot be loaded: "
        "only available on FreeBSD systems.",
    )


def start(jail=""):
    """
    Start the specified jail or all, if none specified

    CLI Example:

    .. code-block:: bash

        salt '*' jail.start [<jail name>]
    """
    cmd = "service jail onestart {0}".format(jail)
    return not __salt__["cmd.retcode"](cmd)


def stop(jail=""):
    """
    Stop the specified jail or all, if none specified

    CLI Example:

    .. code-block:: bash

        salt '*' jail.stop [<jail name>]
    """
    cmd = "service jail onestop {0}".format(jail)
    return not __salt__["cmd.retcode"](cmd)


def restart(jail=""):
    """
    Restart the specified jail or all, if none specified

    CLI Example:

    .. code-block:: bash

        salt '*' jail.restart [<jail name>]
    """
    cmd = "service jail onerestart {0}".format(jail)
    return not __salt__["cmd.retcode"](cmd)


def is_enabled():
    """
    See if jail service is actually enabled on boot

    CLI Example:

    .. code-block:: bash

        salt '*' jail.is_enabled <jail name>
    """
    cmd = "service -e"
    services = __salt__["cmd.run"](cmd, python_shell=False)
    for service in services.split("\\n"):
        if re.search("jail", service):
            return True
    return False


def get_enabled():
    """
    Return which jails are set to be run

    CLI Example:

    .. code-block:: bash

        salt '*' jail.get_enabled
    """
    ret = []
    for rconf in ("/etc/rc.conf", "/etc/rc.conf.local"):
        if os.access(rconf, os.R_OK):
            with salt.utils.files.fopen(rconf, "r") as _fp:
                for line in _fp:
                    line = salt.utils.stringutils.to_unicode(line)
                    if not line.strip():
                        continue
                    if not line.startswith("jail_list="):
                        continue
                    jails = line.split('"')[1].split()
                    for j in jails:
                        ret.append(j)
    return ret


def show_config(jail):
    """
    Display specified jail's configuration

    CLI Example:

    .. code-block:: bash

        salt '*' jail.show_config <jail name>
    """
    ret = {}
    if subprocess.call(["jls", "-nq", "-j", jail]) == 0:
        jls = subprocess.check_output(
            ["jls", "-nq", "-j", jail]
        )  # pylint: disable=minimum-python-version
        jailopts = salt.utils.args.shlex_split(salt.utils.stringutils.to_unicode(jls))
        for jailopt in jailopts:
            if "=" not in jailopt:
                ret[jailopt.strip().rstrip(";")] = "1"
            else:
                key = jailopt.split("=")[0].strip()
                value = jailopt.split("=")[-1].strip().strip('"')
                ret[key] = value
    else:
        for rconf in ("/etc/rc.conf", "/etc/rc.conf.local"):
            if os.access(rconf, os.R_OK):
                with salt.utils.files.fopen(rconf, "r") as _fp:
                    for line in _fp:
                        line = salt.utils.stringutils.to_unicode(line)
                        if not line.strip():
                            continue
                        if not line.startswith("jail_{0}_".format(jail)):
                            continue
                        key, value = line.split("=")
                        ret[key.split("_", 2)[2]] = value.split('"')[1]
        for jconf in ("/etc/jail.conf", "/usr/local/etc/jail.conf"):
            if os.access(jconf, os.R_OK):
                with salt.utils.files.fopen(jconf, "r") as _fp:
                    for line in _fp:
                        line = salt.utils.stringutils.to_unicode(line)
                        line = line.partition("#")[0].strip()
                        if line:
                            if line.split()[-1] == "{":
                                if line.split()[0] != jail and line.split()[0] != "*":
                                    while line.split()[-1] != "}":
                                        line = next(_fp)
                                        line = line.partition("#")[0].strip()
                                else:
                                    continue
                            if line.split()[-1] == "}":
                                continue
                            if "=" not in line:
                                ret[line.strip().rstrip(";")] = "1"
                            else:
                                key = line.split("=")[0].strip()
                                value = line.split("=")[-1].strip().strip(";'\"")
                                ret[key] = value
    return ret


def fstab(jail):
    """
    Display contents of a fstab(5) file defined in specified
    jail's configuration. If no file is defined, return False.

    CLI Example:

    .. code-block:: bash

        salt '*' jail.fstab <jail name>
    """
    ret = []
    config = show_config(jail)
    if "fstab" in config:
        c_fstab = config["fstab"]
    elif "mount.fstab" in config:
        c_fstab = config["mount.fstab"]
    if "fstab" in config or "mount.fstab" in config:
        if os.access(c_fstab, os.R_OK):
            with salt.utils.files.fopen(c_fstab, "r") as _fp:
                for line in _fp:
                    line = salt.utils.stringutils.to_unicode(line)
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#"):
                        continue
                    try:
                        device, mpoint, fstype, opts, dump, pas_ = line.split()
                    except ValueError:
                        # Gracefully continue on invalid lines
                        continue
                    ret.append(
                        {
                            "device": device,
                            "mountpoint": mpoint,
                            "fstype": fstype,
                            "options": opts,
                            "dump": dump,
                            "pass": pas_,
                        }
                    )
    if not ret:
        ret = False
    return ret


def status(jail):
    """
    See if specified jail is currently running

    CLI Example:

    .. code-block:: bash

        salt '*' jail.status <jail name>
    """
    cmd = "jls"
    found_jails = __salt__["cmd.run"](cmd, python_shell=False)
    for found_jail in found_jails.split("\\n"):
        if re.search(jail, found_jail):
            return True
    return False


def sysctl():
    """
    Dump all jail related kernel states (sysctl)

    CLI Example:

    .. code-block:: bash

        salt '*' jail.sysctl
    """
    ret = {}
    sysctl_jail = __salt__["cmd.run"]("sysctl security.jail")
    for line in sysctl_jail.splitlines():
        key, value = line.split(":", 1)
        ret[key.strip()] = value.strip()
    return ret

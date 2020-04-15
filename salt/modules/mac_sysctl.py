# -*- coding: utf-8 -*-
"""
Module for viewing and modifying sysctl parameters
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os

# Import salt libs
import salt.utils.files
from salt.exceptions import CommandExecutionError
from salt.ext import six

# Define the module's virtual name
__virtualname__ = "sysctl"


def __virtual__():
    """
    Only run on Darwin (macOS) systems
    """
    if __grains__["os"] == "MacOS":
        return __virtualname__
    return (
        False,
        "The darwin_sysctl execution module cannot be loaded: "
        "Only available on macOS systems.",
    )


def show(config_file=False):
    """
    Return a list of sysctl parameters for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.show
    """
    roots = (
        "audit",
        "debug",
        "hw",
        "hw",
        "kern",
        "machdep",
        "net",
        "net",
        "security",
        "user",
        "vfs",
        "vm",
    )
    cmd = "sysctl -a"
    ret = {}
    out = __salt__["cmd.run"](cmd, output_loglevel="trace", python_shell=False)
    comps = [""]
    for line in out.splitlines():
        # This might need to be converted to a regex, and more, as sysctl output
        # can for some reason contain entries such as:
        #
        # user.tzname_max = 255
        # kern.clockrate: hz = 100, tick = 10000, profhz = 100, stathz = 100
        # kern.clockrate: {hz = 100, tick = 10000, tickadj = 2, profhz = 100,
        #                 stathz = 100}
        #
        # Yes. That's two `kern.clockrate`.
        #
        if any([line.startswith("{0}.".format(root)) for root in roots]):
            comps = line.split(": " if ": " in line else " = ", 1)
            if len(comps) == 2:
                ret[comps[0]] = comps[1]
            else:
                ret[comps[0]] = ""
        elif comps[0]:
            ret[comps[0]] += "{0}\n".format(line)
        else:
            continue
    return ret


def get(name):
    """
    Return a single sysctl parameter for this minion

    name
        The name of the sysctl value to display.

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.get hw.physmem
    """
    cmd = "sysctl -n {0}".format(name)
    out = __salt__["cmd.run"](cmd, python_shell=False)
    return out


def assign(name, value):
    """
    Assign a single sysctl parameter for this minion

    name
        The name of the sysctl value to edit.

    value
        The sysctl value to apply.

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.assign net.inet.icmp.icmplim 50
    """
    ret = {}
    cmd = 'sysctl -w {0}="{1}"'.format(name, value)
    data = __salt__["cmd.run_all"](cmd, python_shell=False)

    if data["retcode"] != 0:
        raise CommandExecutionError("sysctl failed: {0}".format(data["stderr"]))
    new_name, new_value = data["stdout"].split(":", 1)
    ret[new_name] = new_value.split(" -> ")[-1]
    return ret


def persist(name, value, config="/etc/sysctl.conf", apply_change=False):
    """
    Assign and persist a simple sysctl parameter for this minion

    name
        The name of the sysctl value to edit.

    value
        The sysctl value to apply.

    config
        The location of the sysctl configuration file.

    apply_change
        Default is False; Default behavior only creates or edits
        the sysctl.conf file. If apply is set to True, the changes are
        applied to the system.

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.persist net.inet.icmp.icmplim 50
        salt '*' sysctl.persist coretemp_load NO config=/etc/sysctl.conf
    """
    nlines = []
    edited = False
    value = six.text_type(value)

    # If the sysctl.conf is not present, add it
    if not os.path.isfile(config):
        try:
            with salt.utils.files.fopen(config, "w+") as _fh:
                _fh.write("#\n# Kernel sysctl configuration\n#\n")
        except (IOError, OSError):
            msg = "Could not write to file: {0}"
            raise CommandExecutionError(msg.format(config))

    with salt.utils.files.fopen(config, "r") as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line)
            if not line.startswith("{0}=".format(name)):
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
                nlines.append("{0}={1}\n".format(name, value))
                edited = True
    if not edited:
        nlines.append("{0}={1}\n".format(name, value))
    nlines = [salt.utils.stringutils.to_str(_l) for _l in nlines]
    with salt.utils.files.fopen(config, "w+") as ofile:
        ofile.writelines(nlines)
    # If apply_change=True, apply edits to system
    if apply_change is True:
        assign(name, value)
        return "Updated and applied"
    return "Updated"

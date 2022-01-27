"""
Module for viewing and modifying sysctl parameters
"""

import logging
import os
import re

import salt.utils.data
import salt.utils.files
import salt.utils.stringutils
import salt.utils.systemd
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "sysctl"

# TODO: Add unpersist() to remove either a sysctl or sysctl/value combo from
# the config


def __virtual__():
    """
    Only run on Linux systems
    """
    if __grains__["kernel"] != "Linux":
        return (
            False,
            "The linux_sysctl execution module cannot be loaded: only available on"
            " Linux systems.",
        )
    return __virtualname__


def default_config():
    """
    Linux hosts using systemd 207 or later ignore ``/etc/sysctl.conf`` and only
    load from ``/etc/sysctl.d/*.conf``. This function will do the proper checks
    and return a default config file which will be valid for the Minion. Hosts
    running systemd >= 207 will use ``/etc/sysctl.d/99-salt.conf``.

    CLI Example:

    .. code-block:: bash

        salt -G 'kernel:Linux' sysctl.default_config
    """
    if (
        salt.utils.systemd.booted(__context__)
        and salt.utils.systemd.version(__context__) >= 207
    ):
        return "/etc/sysctl.d/99-salt.conf"
    return "/etc/sysctl.conf"


def show(config_file=False):
    """
    Return a list of sysctl parameters for this minion

    config: Pull the data from the system configuration file
        instead of the live data.

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.show
    """
    ret = {}
    if config_file:
        # If the file doesn't exist, return an empty list
        if not os.path.exists(config_file):
            return []

        try:
            with salt.utils.files.fopen(config_file) as fp_:
                for line in fp_:
                    line = salt.utils.stringutils.to_str(line)
                    if not line.startswith("#") and "=" in line:
                        # search if we have some '=' instead of ' = ' separators
                        SPLIT = " = "
                        if SPLIT not in line:
                            SPLIT = SPLIT.strip()
                        key, value = line.split(SPLIT, 1)
                        key = key.strip()
                        value = value.lstrip()
                        ret[key] = value
        except OSError:
            log.error("Could not open sysctl file")
            return None
    else:
        cmd = "sysctl -a"
        out = __salt__["cmd.run_stdout"](cmd, output_loglevel="trace")
        for line in out.splitlines():
            if not line or " = " not in line:
                continue
            comps = line.split(" = ", 1)
            ret[comps[0]] = comps[1]
    return ret


def get(name):
    """
    Return a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.get net.ipv4.ip_forward
    """
    cmd = "sysctl -n {}".format(name)
    out = __salt__["cmd.run"](cmd, python_shell=False)
    return out


def assign(name, value):
    """
    Assign a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.assign net.ipv4.ip_forward 1
    """
    value = str(value)

    tran_tab = name.translate("".maketrans("./", "/."))

    sysctl_file = "/proc/sys/{}".format(tran_tab)
    if not os.path.exists(sysctl_file):
        raise CommandExecutionError("sysctl {} does not exist".format(name))

    ret = {}
    cmd = 'sysctl -w {}="{}"'.format(name, value)
    data = __salt__["cmd.run_all"](cmd, python_shell=False)
    out = data["stdout"]
    err = data["stderr"]

    # Example:
    #    # sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
    #    net.ipv4.tcp_rmem = 4096 87380 16777216
    regex = re.compile(r"^{}\s+=\s+{}$".format(re.escape(name), re.escape(value)))

    if not regex.match(out) or "Invalid argument" in str(err):
        if data["retcode"] != 0 and err:
            error = err
        else:
            error = out
        raise CommandExecutionError("sysctl -w failed: {}".format(error))
    new_name, new_value = out.split(" = ", 1)
    ret[new_name] = new_value
    return ret


def persist(name, value, config=None):
    """
    Assign and persist a simple sysctl parameter for this minion. If ``config``
    is not specified, a sensible default will be chosen using
    :mod:`sysctl.default_config <salt.modules.linux_sysctl.default_config>`.

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.persist net.ipv4.ip_forward 1
    """
    if config is None:
        config = default_config()
    edited = False
    # If the sysctl.conf is not present, add it
    if not os.path.isfile(config):
        sysctl_dir = os.path.dirname(config)
        if not os.path.exists(sysctl_dir):
            os.makedirs(sysctl_dir)
        try:
            with salt.utils.files.fopen(config, "w+") as _fh:
                _fh.write("#\n# Kernel sysctl configuration\n#\n")
        except OSError:
            msg = "Could not write to file: {0}"
            raise CommandExecutionError(msg.format(config))

    # Read the existing sysctl.conf
    nlines = []
    try:
        with salt.utils.files.fopen(config, "r") as _fh:
            # Use readlines because this should be a small file
            # and it seems unnecessary to indent the below for
            # loop since it is a fairly large block of code.
            config_data = salt.utils.data.decode(_fh.readlines())
    except OSError:
        msg = "Could not read from file: {0}"
        raise CommandExecutionError(msg.format(config))

    for line in config_data:
        if line.startswith("#"):
            nlines.append(line)
            continue
        if "=" not in line:
            nlines.append(line)
            continue

        # Strip trailing whitespace and split the k,v
        comps = [i.strip() for i in line.split("=", 1)]

        # On Linux procfs, files such as /proc/sys/net/ipv4/tcp_rmem or any
        # other sysctl with whitespace in it consistently uses 1 tab.  Lets
        # allow our users to put a space or tab between multi-value sysctls
        # and have salt not try to set it every single time.
        if isinstance(comps[1], str) and " " in comps[1]:
            comps[1] = re.sub(r"\s+", "\t", comps[1])

        # Do the same thing for the value 'just in case'
        if isinstance(value, str) and " " in value:
            value = re.sub(r"\s+", "\t", value)

        if len(comps) < 2:
            nlines.append(line)
            continue
        if name == comps[0]:
            # This is the line to edit
            if str(comps[1]) == str(value):
                # It is correct in the config, check if it is correct in /proc
                if str(get(name)) != str(value):
                    assign(name, value)
                    return "Updated"
                else:
                    return "Already set"

            nlines.append("{} = {}\n".format(name, value))
            edited = True
            continue
        else:
            nlines.append(line)
    if not edited:
        nlines.append("{} = {}\n".format(name, value))
    try:
        with salt.utils.files.fopen(config, "wb") as _fh:
            _fh.writelines(salt.utils.data.encode(nlines))
    except OSError:
        msg = "Could not write to file: {0}"
        raise CommandExecutionError(msg.format(config))

    assign(name, value)
    return "Updated"

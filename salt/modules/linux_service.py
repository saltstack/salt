"""
If Salt's OS detection does not identify a different virtual service module, the minion will fall back to using this basic module, which simply wraps sysvinit scripts.
"""

import fnmatch
import os
import re

__func_alias__ = {"reload_": "reload"}

_GRAINMAP = {"Arch": "/etc/rc.d", "Arch ARM": "/etc/rc.d"}


def __virtual__():
    """
    Only work on systems which exclusively use sysvinit
    """
    # Disable on these platforms, specific service modules exist:
    disable = {
        "RedHat",
        "CentOS",
        "Amazon",
        "ScientificLinux",
        "CloudLinux",
        "Fedora",
        "Gentoo",
        "Ubuntu",
        "Debian",
        "Devuan",
        "ALT",
        "OEL",
        "Linaro",
        "elementary OS",
        "McAfee  OS Server",
        "Raspbian",
        "SUSE",
        "Slackware",
    }
    if __grains__.get("os") in disable:
        return (False, "Your OS is on the disabled list")
    # Disable on all non-Linux OSes as well
    if __grains__["kernel"] != "Linux":
        return (False, "Non Linux OSes are not supported")
    init_grain = __grains__.get("init")
    if init_grain not in (None, "sysvinit", "unknown"):
        return (False, f"Minion is running {init_grain}")
    elif __utils__["systemd.booted"](__context__):
        # Should have been caught by init grain check, but check just in case
        return (False, "Minion is running systemd")
    return "service"


def run(name, action):
    """
    Run the specified service with an action.

    .. versionadded:: 2015.8.1

    name
        Service name.

    action
        Action name (like start,  stop,  reload,  restart).

    CLI Example:

    .. code-block:: bash

        salt '*' service.run apache2 reload
        salt '*' service.run postgresql initdb
    """
    cmd = (
        os.path.join(_GRAINMAP.get(__grains__.get("os"), "/etc/init.d"), name)
        + " "
        + action
    )
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def start(name):
    """
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    """
    return run(name, "start")


def stop(name):
    """
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    """
    return run(name, "stop")


def restart(name):
    """
    Restart the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    """
    return run(name, "restart")


def status(name, sig=None):
    """
    Return the status for a service.
    If the name contains globbing, a dict mapping service name to PID or empty
    string is returned.

    .. versionchanged:: 2018.3.0
        The service name can now be a glob (e.g. ``salt*``)

    Args:
        name (str): The name of the service to check
        sig (str): Signature to use to find the service via ps

    Returns:
        string: PID if running, empty otherwise
        dict: Maps service name to PID if running, empty string otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name> [service signature]
    """
    if sig:
        return __salt__["status.pid"](sig)

    contains_globbing = bool(re.search(r"\*|\?|\[.+\]", name))
    if contains_globbing:
        services = fnmatch.filter(get_all(), name)
    else:
        services = [name]
    results = {}
    for service in services:
        results[service] = __salt__["status.pid"](service)
    if contains_globbing:
        return results
    return results[name]


def reload_(name):
    """
    Refreshes config files by calling service reload. Does not perform a full
    restart.

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    """
    return run(name, "reload")


def available(name):
    """
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    """
    return name in get_all()


def missing(name):
    """
    The inverse of service.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing sshd
    """
    return name not in get_all()


def get_all():
    """
    Return a list of all available services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    """
    if not os.path.isdir(_GRAINMAP.get(__grains__.get("os"), "/etc/init.d")):
        return []
    return sorted(os.listdir(_GRAINMAP.get(__grains__.get("os"), "/etc/init.d")))

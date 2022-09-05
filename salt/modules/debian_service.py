"""
Service support for Debian systems (uses update-rc.d and /sbin/service)

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import fnmatch
import glob
import logging
import os
import re
import shlex

import salt.utils.systemd

__func_alias__ = {"reload_": "reload"}

# Define the module's virtual name
__virtualname__ = "service"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only work on Debian and when systemd isn't running
    """
    if __grains__["os"] in (
        "Debian",
        "Raspbian",
        "Devuan",
        "NILinuxRT",
    ) and not salt.utils.systemd.booted(__context__):
        return __virtualname__
    else:
        return (
            False,
            "The debian_service module could not be loaded: "
            "unsupported OS family and/or systemd running.",
        )


def _service_cmd(*args):
    return "service {} {}".format(args[0], " ".join(args[1:]))


def _get_runlevel():
    """
    returns the current runlevel
    """
    out = __salt__["cmd.run"]("runlevel")
    # unknown can be returned while inside a container environment, since
    # this is due to a lack of init, it should be safe to assume runlevel
    # 2, which is Debian's default. If not, all service related states
    # will throw an out of range exception here which will cause
    # other functions to fail.
    if "unknown" in out:
        return "2"
    else:
        return out.split()[1]


def get_enabled():
    """
    Return a list of service that are enabled on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    """
    prefix = "/etc/rc[S{}].d/S".format(_get_runlevel())
    ret = set()
    for line in [x.rsplit(os.sep, 1)[-1] for x in glob.glob("{}*".format(prefix))]:
        ret.add(re.split(r"\d+", line)[-1])
    return sorted(ret)


def get_disabled():
    """
    Return a set of services that are installed but disabled

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    """
    return sorted(set(get_all()) - set(get_enabled()))


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
    Return all available boot services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    """
    ret = set()
    lines = glob.glob("/etc/init.d/*")
    for line in lines:
        service = line.split("/etc/init.d/")[1]
        # Remove README.  If it's an enabled service, it will be added back in.
        if service != "README":
            ret.add(service)
    return sorted(ret | set(get_enabled()))


def start(name):
    """
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    """
    cmd = _service_cmd(name, "start")
    return not __salt__["cmd.retcode"](cmd)


def stop(name):
    """
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    """
    cmd = _service_cmd(name, "stop")
    return not __salt__["cmd.retcode"](cmd)


def restart(name):
    """
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    """
    cmd = _service_cmd(name, "restart")
    return not __salt__["cmd.retcode"](cmd)


def reload_(name):
    """
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    """
    cmd = _service_cmd(name, "reload")
    return not __salt__["cmd.retcode"](cmd)


def force_reload(name):
    """
    Force-reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    """
    cmd = _service_cmd(name, "force-reload")
    return not __salt__["cmd.retcode"](cmd)


def status(name, sig=None):
    """
    Return the status for a service.
    If the name contains globbing, a dict mapping service name to True/False
    values is returned.

    .. versionchanged:: 2018.3.0
        The service name can now be a glob (e.g. ``salt*``)

    Args:
        name (str): The name of the service to check
        sig (str): Signature to use to find the service via ps

    Returns:
        bool: True if running, False otherwise
        dict: Maps service name to True if running, False otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name> [service signature]
    """
    if sig:
        return bool(__salt__["status.pid"](sig))

    contains_globbing = bool(re.search(r"\*|\?|\[.+\]", name))
    if contains_globbing:
        services = fnmatch.filter(get_all(), name)
    else:
        services = [name]
    results = {}
    for service in services:
        cmd = _service_cmd(service, "status")
        results[service] = not __salt__["cmd.retcode"](cmd, ignore_retcode=True)
    if contains_globbing:
        return results
    return results[name]


def enable(name, **kwargs):
    """
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    """
    cmd = "insserv {0} && update-rc.d {0} enable".format(shlex.quote(name))
    return not __salt__["cmd.retcode"](cmd, python_shell=True)


def disable(name, **kwargs):
    """
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    """
    cmd = "update-rc.d {} disable".format(name)
    return not __salt__["cmd.retcode"](cmd)


def enabled(name, **kwargs):
    """
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    """
    return name in get_enabled()


def disabled(name):
    """
    Return True if the named service is disabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    """
    return name in get_disabled()

"""
The service module for NetBSD

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import fnmatch
import glob
import os
import re

__func_alias__ = {"reload_": "reload"}

# Define the module's virtual name
__virtualname__ = "service"


def __virtual__():
    """
    Only work on NetBSD
    """
    if __grains__["os"] == "NetBSD" and os.path.exists("/etc/rc.subr"):
        return __virtualname__
    return (
        False,
        "The netbsdservice execution module failed to load: only available on NetBSD.",
    )


def start(name):
    """
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    """
    cmd = f"/etc/rc.d/{name} onestart"
    return not __salt__["cmd.retcode"](cmd)


def stop(name):
    """
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    """
    cmd = f"/etc/rc.d/{name} onestop"
    return not __salt__["cmd.retcode"](cmd)


def restart(name):
    """
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    """
    cmd = f"/etc/rc.d/{name} onerestart"
    return not __salt__["cmd.retcode"](cmd)


def reload_(name):
    """
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    """
    cmd = f"/etc/rc.d/{name} onereload"
    return not __salt__["cmd.retcode"](cmd)


def force_reload(name):
    """
    Force-reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    """
    cmd = f"/etc/rc.d/{name} forcereload"
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
        cmd = f"/etc/rc.d/{service} onestatus"
        results[service] = not __salt__["cmd.retcode"](cmd, ignore_retcode=True)
    if contains_globbing:
        return results
    return results[name]


def _get_svc(rcd, service_status):
    """
    Returns a unique service status
    """
    ena = None
    lines = __salt__["cmd.run"](f"{rcd} rcvar").splitlines()
    for rcvar in lines:
        if rcvar.startswith("$") and f"={service_status}" in rcvar:
            ena = "yes"
        elif rcvar.startswith("#"):
            svc = rcvar.split(" ", 1)[1]
        else:
            continue

    if ena and svc:
        return svc
    return None


def _get_svc_list(service_status):
    """
    Returns all service statuses
    """
    prefix = "/etc/rc.d/"
    ret = set()
    lines = glob.glob(f"{prefix}*")
    for line in lines:
        svc = _get_svc(line, service_status)
        if svc is not None:
            ret.add(svc)

    return sorted(ret)


def get_enabled():
    """
    Return a list of service that are enabled on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    """
    return _get_svc_list("YES")


def get_disabled():
    """
    Return a set of services that are installed but disabled

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    """
    return _get_svc_list("NO")


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
    return _get_svc_list("")


def _rcconf_status(name, service_status):
    """
    Modifies /etc/rc.conf so a service is started or not at boot time and
    can be started via /etc/rc.d/<service>
    """
    rcconf = "/etc/rc.conf"
    rxname = f"^{name}=.*"
    newstatus = f"{name}={service_status}"
    ret = __salt__["cmd.retcode"](f"grep '{rxname}' {rcconf}")
    if ret == 0:  # service found in rc.conf, modify its status
        __salt__["file.replace"](rcconf, rxname, newstatus)
    else:
        ret = __salt__["file.append"](rcconf, newstatus)

    return ret


def enable(name, **kwargs):
    """
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    """
    return _rcconf_status(name, "YES")


def disable(name, **kwargs):
    """
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    """
    return _rcconf_status(name, "NO")


def enabled(name, **kwargs):
    """
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    """
    return _get_svc(f"/etc/rc.d/{name}", "YES")


def disabled(name):
    """
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    """
    return _get_svc(f"/etc/rc.d/{name}", "NO")

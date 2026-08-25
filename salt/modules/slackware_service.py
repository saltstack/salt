"""
The service module for Slackware

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

prefix = "/etc/rc.d/rc"


def __virtual__():
    """
    Only work on Slackware
    """
    if __grains__["os"] == "Slackware":
        return __virtualname__
    return (
        False,
        "The slackware_service execution module failed to load: only available on"
        " Slackware.",
    )


def start(name):
    """
    Start the specified service

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    """
    cmd = f"/bin/sh {prefix}.{name} start"
    return not __salt__["cmd.retcode"](cmd)


def stop(name):
    """
    Stop the specified service

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    """
    cmd = f"/bin/sh {prefix}.{name} stop"
    return not __salt__["cmd.retcode"](cmd)


def restart(name):
    """
    Restart the named service

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    """
    cmd = f"/bin/sh {prefix}.{name} restart"
    return not __salt__["cmd.retcode"](cmd)


def reload_(name):
    """
    Reload the named service

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    """
    cmd = f"/bin/sh {prefix}.{name} reload"
    return not __salt__["cmd.retcode"](cmd)


def force_reload(name):
    """
    Force-reload the named service

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    """
    cmd = f"/bin/sh {prefix}.{name} forcereload"
    return not __salt__["cmd.retcode"](cmd)


def status(name, sig=None):
    """
    Return the status for a service.
    If the name contains globbing, a dict mapping service name to True/False
    values is returned.

    .. versionadded:: 3002

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
        cmd = f"/bin/sh {prefix}.{service} status"
        results[service] = not __salt__["cmd.retcode"](cmd, ignore_retcode=True)
    if contains_globbing:
        return results
    return results[name]


def _get_svc(rcd, service_status):
    """
    Returns a unique service status
    """
    if os.path.exists(rcd):
        ena = os.access(rcd, os.X_OK)
        svc = rcd.split(".")[2]
        if service_status == "":
            return svc
        elif service_status == "ON" and ena:
            return svc
        elif service_status == "OFF" and (not ena):
            return svc
    return None


def _get_svc_list(service_status):
    """
    Returns all service statuses
    """
    notservice = re.compile(
        r"{}.([A-Za-z0-9_-]+\.conf|0|4|6|K|M|S|inet1|inet2|local|modules.*|wireless)$".format(
            prefix
        )
    )
    ret = set()
    lines = glob.glob(f"{prefix}.*")
    for line in lines:
        if not notservice.match(line):
            svc = _get_svc(line, service_status)
            if svc is not None:
                ret.add(svc)

    return sorted(ret)


def get_enabled():
    """
    Return a list of service that are enabled on boot

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    """
    return _get_svc_list("ON")


def get_disabled():
    """
    Return a set of services that are installed but disabled

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    """
    return _get_svc_list("OFF")


def available(name):
    """
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    .. versionadded:: 3002

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

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing sshd
    """
    return name not in get_all()


def get_all():
    """
    Return all available boot services

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    """
    return _get_svc_list("")


def _rcd_mode(name, ena):
    """
    Enable/Disable a service
    """
    rcd = prefix + "." + name
    if os.path.exists(rcd):
        perms = os.stat(rcd).st_mode
        if ena == "ON":
            perms |= 0o111
            os.chmod(rcd, perms)
        elif ena == "OFF":
            perms &= 0o777666
            os.chmod(rcd, perms)
        return True

    return False


def enable(name, **kwargs):
    """
    Enable the named service to start at boot

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    """
    return _rcd_mode(name, "ON")


def disable(name, **kwargs):
    """
    Disable the named service to start at boot

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    """
    return _rcd_mode(name, "OFF")


def enabled(name, **kwargs):
    """
    Return True if the named service is enabled, false otherwise

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    """
    ret = True
    if _get_svc(f"{prefix}.{name}", "ON") is None:
        ret = False
    return ret


def disabled(name):
    """
    Return True if the named service is enabled, false otherwise

    .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    """
    ret = True
    if _get_svc(f"{prefix}.{name}", "OFF") is None:
        ret = False
    return ret

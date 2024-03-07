"""
Service support for Solaris 10 and 11, should work with other systems
that use SMF also. (e.g. SmartOS)

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import fnmatch
import re

__func_alias__ = {"reload_": "reload"}

# Define the module's virtual name
__virtualname__ = "service"


def __virtual__():
    """
    Only work on systems which default to SMF
    """
    if "Solaris" in __grains__["os_family"]:
        # Don't let this work on Solaris 9 since SMF doesn't exist on it.
        if __grains__["kernelrelease"] == "5.9":
            return (
                False,
                "The smf execution module failed to load: SMF not available on"
                " Solaris 9.",
            )
        return __virtualname__
    return (
        False,
        "The smf execution module failed to load: only available on Solaris.",
    )


def _get_enabled_disabled(enabled_prop="true"):
    """
    DRY: Get all service FMRIs and their enabled property
    """
    ret = set()
    cmd = '/usr/bin/svcprop -c -p general/enabled "*"'
    lines = __salt__["cmd.run_stdout"](cmd, python_shell=False).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if comps[2] == enabled_prop:
            ret.add(comps[0].split("/:properties")[0])
    return sorted(ret)


def get_running():
    """
    Return the running services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_running
    """
    ret = set()
    cmd = "/usr/bin/svcs -H -o FMRI,STATE -s FMRI"
    lines = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if "online" in line:
            ret.add(comps[0])
    return sorted(ret)


def get_stopped():
    """
    Return the stopped services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_stopped
    """
    ret = set()
    cmd = "/usr/bin/svcs -aH -o FMRI,STATE -s FMRI"
    lines = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if "online" not in line and "legacy_run" not in line:
            ret.add(comps[0])
    return sorted(ret)


def available(name):
    """
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    We look up the name with the svcs command to get back the FMRI
    This allows users to use simpler service names

    CLI Example:

    .. code-block:: bash

        salt '*' service.available net-snmp
    """
    cmd = f"/usr/bin/svcs -H -o FMRI {name}"
    name = __salt__["cmd.run"](cmd, python_shell=False)
    return name in get_all()


def missing(name):
    """
    The inverse of service.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing net-snmp
    """
    cmd = f"/usr/bin/svcs -H -o FMRI {name}"
    name = __salt__["cmd.run"](cmd, python_shell=False)
    return name not in get_all()


def get_all():
    """
    Return all installed services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    """
    ret = set()
    cmd = "/usr/bin/svcs -aH -o FMRI,STATE -s FMRI"
    lines = __salt__["cmd.run"](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        ret.add(comps[0])
    return sorted(ret)


def start(name):
    """
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    """
    cmd = f"/usr/sbin/svcadm enable -s -t {name}"
    retcode = __salt__["cmd.retcode"](cmd, python_shell=False)
    if not retcode:
        return True
    if retcode == 3:
        # Return code 3 means there was a problem with the service
        # A common case is being in the 'maintenance' state
        # Attempt a clear and try one more time
        clear_cmd = f"/usr/sbin/svcadm clear {name}"
        __salt__["cmd.retcode"](clear_cmd, python_shell=False)
        return not __salt__["cmd.retcode"](cmd, python_shell=False)
    return False


def stop(name):
    """
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    """
    cmd = f"/usr/sbin/svcadm disable -s -t {name}"
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def restart(name):
    """
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    """
    cmd = f"/usr/sbin/svcadm restart {name}"
    if not __salt__["cmd.retcode"](cmd, python_shell=False):
        # calling restart doesn't clear maintenance
        # or tell us that the service is in the 'online' state
        return start(name)
    return False


def reload_(name):
    """
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    """
    cmd = f"/usr/sbin/svcadm refresh {name}"
    if not __salt__["cmd.retcode"](cmd, python_shell=False):
        # calling reload doesn't clear maintenance
        # or tell us that the service is in the 'online' state
        return start(name)
    return False


def status(name, sig=None):
    """
    Return the status for a service.
    If the name contains globbing, a dict mapping service name to True/False
    values is returned.

    .. versionchanged:: 2018.3.0
        The service name can now be a glob (e.g. ``salt*``)

    Args:
        name (str): The name of the service to check
        sig (str): Not implemented

    Returns:
        bool: True if running, False otherwise
        dict: Maps service name to True if running, False otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    """
    contains_globbing = bool(re.search(r"\*|\?|\[.+\]", name))
    if contains_globbing:
        services = fnmatch.filter(get_all(), name)
    else:
        services = [name]
    results = {}
    for service in services:
        cmd = f"/usr/bin/svcs -H -o STATE {service}"
        line = __salt__["cmd.run"](cmd, python_shell=False)
        results[service] = line == "online"
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
    cmd = f"/usr/sbin/svcadm enable {name}"
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def disable(name, **kwargs):
    """
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    """
    cmd = f"/usr/sbin/svcadm disable {name}"
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def enabled(name, **kwargs):
    """
    Check to see if the named service is enabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    """
    # The property that reveals whether a service is enabled
    # can only be queried using the full FMRI
    # We extract the FMRI and then do the query
    fmri_cmd = f"/usr/bin/svcs -H -o FMRI {name}"
    fmri = __salt__["cmd.run"](fmri_cmd, python_shell=False)
    cmd = f"/usr/sbin/svccfg -s {fmri} listprop general/enabled"
    comps = __salt__["cmd.run"](cmd, python_shell=False).split()
    if comps[2] == "true":
        return True
    else:
        return False


def disabled(name):
    """
    Check to see if the named service is disabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    """
    return not enabled(name)


def get_enabled():
    """
    Return the enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    """
    # Note that this returns the full FMRI
    return _get_enabled_disabled("true")


def get_disabled():
    """
    Return the disabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    """
    # Note that this returns the full FMRI
    return _get_enabled_disabled("false")

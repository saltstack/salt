"""
The service module for FreeBSD

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.
"""

import fnmatch
import logging
import os
import re

import salt.utils.decorators as decorators
import salt.utils.files
import salt.utils.path
from salt.exceptions import CommandNotFoundError

__func_alias__ = {"reload_": "reload"}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "service"


def __virtual__():
    """
    Only work on FreeBSD
    """
    # Disable on these platforms, specific service modules exist:
    if __grains__["os"] == "FreeBSD":
        return __virtualname__
    return (
        False,
        "The freebsdservice execution module cannot be loaded: only available on"
        " FreeBSD systems.",
    )


@decorators.memoize
def _cmd(jail=None):
    """
    Return full path to service command

    .. versionchanged:: 2016.3.4

    Support for jail (representing jid or jail name) keyword argument in kwargs
    """
    service = salt.utils.path.which("service")
    if not service:
        raise CommandNotFoundError("'service' command not found")
    if jail:
        jexec = salt.utils.path.which("jexec")
        if not jexec:
            raise CommandNotFoundError("'jexec' command not found")
        service = "{} {} {}".format(jexec, jail, service)
    return service


def _get_jail_path(jail):
    """
    .. versionadded:: 2016.3.4

    Return the jail's root directory (path) as shown in jls

    jail
        The jid or jail name
    """
    jls = salt.utils.path.which("jls")
    if not jls:
        raise CommandNotFoundError("'jls' command not found")
    jails = __salt__["cmd.run_stdout"]("{} -n jid name path".format(jls))
    for j in jails.splitlines():
        jid, jname, path = (x.split("=")[1].strip() for x in j.split())
        if jid == jail or jname == jail:
            return path.rstrip("/")
    # XΧΧ, TODO, not sure how to handle nonexistent jail
    return ""


def _get_rcscript(name, jail=None):
    """
    Return full path to service rc script

    .. versionchanged:: 2016.3.4

    Support for jail (representing jid or jail name) keyword argument in kwargs
    """
    cmd = "{} -r".format(_cmd(jail))
    prf = _get_jail_path(jail) if jail else ""
    for line in __salt__["cmd.run_stdout"](cmd, python_shell=False).splitlines():
        if line.endswith("{}{}".format(os.path.sep, name)):
            return os.path.join(prf, line.lstrip(os.path.sep))
    return None


def _get_rcvar(name, jail=None):
    """
    Return rcvar

    .. versionchanged:: 2016.3.4

    Support for jail (representing jid or jail name) keyword argument in kwargs
    """
    if not available(name, jail):
        log.error("Service %s not found", name)
        return False

    cmd = "{} {} rcvar".format(_cmd(jail), name)

    for line in __salt__["cmd.run_stdout"](cmd, python_shell=False).splitlines():
        if '_enable="' not in line:
            continue
        rcvar, _ = line.split("=", 1)
        return rcvar

    return None


def get_enabled(jail=None):
    """
    Return what services are set to run on boot

    .. versionchanged:: 2016.3.4

    Support for jail (representing jid or jail name) keyword argument in kwargs

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    """
    ret = []
    service = _cmd(jail)
    prf = _get_jail_path(jail) if jail else ""
    for svc in __salt__["cmd.run"]("{} -e".format(service)).splitlines():
        ret.append(os.path.basename(svc))

    # This is workaround for bin/173454 bug
    for svc in get_all(jail):
        if svc in ret:
            continue
        if not os.path.exists("{}/etc/rc.conf.d/{}".format(prf, svc)):
            continue
        if enabled(svc, jail=jail):
            ret.append(svc)

    return sorted(ret)


def get_disabled(jail=None):
    """
    Return what services are available but not enabled to start at boot

    .. versionchanged:: 2016.3.4

    Support for jail (representing jid or jail name) keyword argument in kwargs

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    """
    en_ = get_enabled(jail)
    all_ = get_all(jail)
    return sorted(set(all_) - set(en_))


def _switch(name, on, **kwargs):  # pylint: disable=C0103  # pylint: disable=C0103
    """
    Switch on/off service start at boot.

    .. versionchanged:: 2016.3.4

    Support for jail (representing jid or jail name) and chroot keyword argument
    in kwargs. chroot should be used when jail's /etc is mounted read-only and
    should point to a root directory where jail's /etc is mounted read-write.
    """
    jail = kwargs.get("jail", "")
    chroot = kwargs.get("chroot", "").rstrip("/")
    if not available(name, jail):
        return False

    rcvar = _get_rcvar(name, jail)
    if not rcvar:
        log.error("rcvar for service %s not found", name)
        return False

    if jail and not chroot:
        # prepend the jail's path in config paths when referring to a jail, when
        # chroot is not provided. chroot should be provided when the jail's /etc
        # is mounted read-only
        chroot = _get_jail_path(jail)

    config = kwargs.get(
        "config",
        __salt__["config.option"](
            "service.config", default="{}/etc/rc.conf".format(chroot)
        ),
    )

    if not config:
        rcdir = "{}/etc/rc.conf.d".format(chroot)
        if not os.path.exists(rcdir) or not os.path.isdir(rcdir):
            log.error("%s not exists", rcdir)
            return False
        config = os.path.join(rcdir, rcvar.replace("_enable", ""))

    nlines = []
    edited = False

    if on:
        val = "YES"
    else:
        val = "NO"

    if os.path.exists(config):
        with salt.utils.files.fopen(config, "r") as ifile:
            for line in ifile:
                line = salt.utils.stringutils.to_unicode(line)
                if not line.startswith("{}=".format(rcvar)):
                    nlines.append(line)
                    continue
                rest = line[len(line.split()[0]) :]  # keep comments etc
                nlines.append('{}="{}"{}'.format(rcvar, val, rest))
                edited = True
    if not edited:
        # Ensure that the file ends in a \n
        if len(nlines) > 1 and nlines[-1][-1] != "\n":
            nlines[-1] = "{}\n".format(nlines[-1])
        nlines.append('{}="{}"\n'.format(rcvar, val))

    with salt.utils.files.fopen(config, "w") as ofile:
        nlines = [salt.utils.stringutils.to_str(_l) for _l in nlines]
        ofile.writelines(nlines)

    return True


def enable(name, **kwargs):
    """
    Enable the named service to start at boot

    name
        service name

    config : /etc/rc.conf
        Config file for managing service. If config value is
        empty string, then /etc/rc.conf.d/<service> used.
        See man rc.conf(5) for details.

        Also service.config variable can be used to change default.

    .. versionchanged:: 2016.3.4

    jail (optional keyword argument)
        the jail's id or name

    chroot (optional keyword argument)
        the jail's chroot, if the jail's /etc is not mounted read-write

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    """
    return _switch(name, True, **kwargs)


def disable(name, **kwargs):
    """
    Disable the named service to start at boot

    Arguments the same as for enable()

    .. versionchanged:: 2016.3.4

    jail (optional keyword argument)
        the jail's id or name

    chroot (optional keyword argument)
        the jail's chroot, if the jail's /etc is not mounted read-write

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    """
    return _switch(name, False, **kwargs)


def enabled(name, **kwargs):
    """
    Return True if the named service is enabled, false otherwise

    name
        Service name

    .. versionchanged:: 2016.3.4

    Support for jail (representing jid or jail name) keyword argument in kwargs

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    """
    jail = kwargs.get("jail", "")
    if not available(name, jail):
        log.error("Service %s not found", name)
        return False

    cmd = "{} {} rcvar".format(_cmd(jail), name)

    for line in __salt__["cmd.run_stdout"](cmd, python_shell=False).splitlines():
        if '_enable="' not in line:
            continue
        _, state, _ = line.split('"', 2)
        return state.lower() in ("yes", "true", "on", "1")

    # probably will never reached
    return False


def disabled(name, **kwargs):
    """
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    """
    return not enabled(name, **kwargs)


def available(name, jail=None):
    """
    Check that the given service is available.

    .. versionchanged:: 2016.3.4

    jail: optional jid or jail name

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    """
    return name in get_all(jail)


def missing(name, jail=None):
    """
    The inverse of service.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    .. versionchanged:: 2016.3.4

    jail: optional jid or jail name

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing sshd
    """
    return name not in get_all(jail)


def get_all(jail=None):
    """
    Return a list of all available services

    .. versionchanged:: 2016.3.4

    jail: optional jid or jail name

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    """
    ret = []
    service = _cmd(jail)
    for srv in __salt__["cmd.run"]("{} -l".format(service)).splitlines():
        if not srv.isupper():
            ret.append(srv)
    return sorted(ret)


def start(name, jail=None):
    """
    Start the specified service

    .. versionchanged:: 2016.3.4

    jail: optional jid or jail name

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    """
    cmd = "{} {} onestart".format(_cmd(jail), name)
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def stop(name, jail=None):
    """
    Stop the specified service

    .. versionchanged:: 2016.3.4

    jail: optional jid or jail name

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    """
    cmd = "{} {} onestop".format(_cmd(jail), name)
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def restart(name, jail=None):
    """
    Restart the named service

    .. versionchanged:: 2016.3.4

    jail: optional jid or jail name

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    """
    cmd = "{} {} onerestart".format(_cmd(jail), name)
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def reload_(name, jail=None):
    """
    Restart the named service

    .. versionchanged:: 2016.3.4

    jail: optional jid or jail name

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    """
    cmd = "{} {} onereload".format(_cmd(jail), name)
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def status(name, sig=None, jail=None):
    """
    Return the status for a service.
    If the name contains globbing, a dict mapping service name to True/False
    values is returned.

    .. versionchanged:: 2016.3.4

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
        cmd = "{} {} onestatus".format(_cmd(jail), service)
        results[service] = not __salt__["cmd.retcode"](
            cmd, python_shell=False, ignore_retcode=True
        )
    if contains_globbing:
        return results
    return results[name]

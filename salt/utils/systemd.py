"""
Contains systemd related help files
"""

import logging
import os
import re
import subprocess

import salt.loader.context
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError

try:
    import dbus
except ImportError:
    dbus = None


log = logging.getLogger(__name__)


def booted(context=None):
    """
    Return True if the system was booted with systemd, False otherwise.  If the
    loader context dict ``__context__`` is passed, this function will set the
    ``salt.utils.systemd.booted`` key to represent if systemd is running and
    keep the logic below from needing to be run again during the same salt run.
    """
    contextkey = "salt.utils.systemd.booted"
    if isinstance(context, (dict, salt.loader.context.NamedLoaderContext)):
        # Can't put this if block on the same line as the above if block,
        # because it willl break the elif below.
        if contextkey in context:
            return context[contextkey]
    elif context is not None:
        raise SaltInvocationError("context must be a dictionary if passed")

    try:
        # This check does the same as sd_booted() from libsystemd-daemon:
        # http://www.freedesktop.org/software/systemd/man/sd_booted.html
        ret = bool(os.stat("/run/systemd/system"))
    except OSError:
        ret = False

    try:
        context[contextkey] = ret
    except TypeError:
        pass

    return ret


def offline(context=None):
    """Return True if systemd is in offline mode

    .. versionadded:: 3004
    """
    contextkey = "salt.utils.systemd.offline"
    if isinstance(context, (dict, salt.loader.context.NamedLoaderContext)):
        if contextkey in context:
            return context[contextkey]
    elif context is not None:
        raise SaltInvocationError("context must be a dictionary if passed")

    # Note that there is a difference from SYSTEMD_OFFLINE=1.  Here we
    # assume that there is no PID 1 to talk with.
    ret = not booted(context) and salt.utils.path.which("systemctl")

    try:
        context[contextkey] = ret
    except TypeError:
        pass

    return ret


def version(context=None):
    """
    Attempts to run systemctl --version. Returns None if unable to determine
    version.
    """
    contextkey = "salt.utils.systemd.version"
    if isinstance(context, (dict, salt.loader.context.NamedLoaderContext)):
        # Can't put this if block on the same line as the above if block,
        # because it will break the elif below.
        if contextkey in context:
            return context[contextkey]
    elif context is not None:
        raise SaltInvocationError("context must be a dictionary if passed")
    stdout = subprocess.Popen(
        ["systemctl", "--version"],
        close_fds=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).communicate()[0]
    outstr = salt.utils.stringutils.to_str(stdout)
    try:
        ret = int(re.search(r"\w+ ([0-9]+)", outstr.splitlines()[0]).group(1))
    except (AttributeError, IndexError, ValueError):
        log.error(
            "Unable to determine systemd version from systemctl "
            "--version, output follows:\n%s",
            outstr,
        )
        return None
    else:
        try:
            context[contextkey] = ret
        except TypeError:
            pass
        return ret


def has_scope(context=None):
    """
    Scopes were introduced in systemd 205, this function returns a boolean
    which is true when the minion is systemd-booted and running systemd>=205.
    """
    if not booted(context):
        return False
    _sd_version = version(context)
    if _sd_version is None:
        return False
    return _sd_version >= 205


def pid_to_service(pid):
    """
    Check if a PID belongs to a systemd service and return its name.
    Return None if the PID does not belong to a service.

    Uses DBUS if available.
    """
    if dbus:
        return _pid_to_service_dbus(pid)
    else:
        return _pid_to_service_systemctl(pid)


def _pid_to_service_systemctl(pid):
    systemd_cmd = ["systemctl", "--output", "json", "status", str(pid)]
    try:
        systemd_output = subprocess.run(
            systemd_cmd, check=True, text=True, capture_output=True
        )
        status_json = salt.utils.json.find_json(systemd_output.stdout)
    except (ValueError, subprocess.CalledProcessError):
        return None

    name = status_json.get("_SYSTEMD_UNIT")
    if name and name.endswith(".service"):
        return _strip_suffix(name)
    else:
        return None


def _pid_to_service_dbus(pid):
    """
    Use DBUS to check if a PID belongs to a running systemd service and return the service name if it does.
    """
    bus = dbus.SystemBus()
    systemd_object = bus.get_object(
        "org.freedesktop.systemd1", "/org/freedesktop/systemd1"
    )
    systemd = dbus.Interface(systemd_object, "org.freedesktop.systemd1.Manager")
    try:
        service_path = systemd.GetUnitByPID(pid)
        service_object = bus.get_object("org.freedesktop.systemd1", service_path)
        service_props = dbus.Interface(
            service_object, "org.freedesktop.DBus.Properties"
        )
        service_name = service_props.Get("org.freedesktop.systemd1.Unit", "Id")
        name = str(service_name)

        if name and name.endswith(".service"):
            return _strip_suffix(name)
        else:
            return None
    except dbus.DBusException:
        return None


def _strip_suffix(service_name):
    """
    Strip ".service" suffix from a given service name.
    """
    return service_name[:-8]

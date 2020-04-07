# -*- coding: utf-8 -*-
"""
GNOME implementations
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import re

# Import Salt libs
import salt.utils.path

try:
    import pwd

    HAS_PWD = True
except ImportError:
    HAS_PWD = False


# Import 3rd-party libs
try:
    from gi.repository import Gio, GLib  # pylint: disable=W0611

    HAS_GLIB = True
except ImportError:
    HAS_GLIB = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "gnome"

# Don't shadow built-in's.
__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    Only load if the Gio and Glib modules are available
    """
    if HAS_PWD and HAS_GLIB:
        return __virtualname__
    return (
        False,
        "The gnome_desktop execution module cannot be loaded: "
        "The Gio and GLib modules are not available",
    )


class _GSettings(object):
    def __init__(self, user, schema, key):
        self.SCHEMA = schema
        self.KEY = key
        self.USER = user
        self.UID = None
        self.HOME = None

    @property
    def gsetting_command(self):
        """
        return the command to run the gsettings binary
        """
        if salt.utils.path.which_bin(["dbus-run-session"]):
            cmd = ["dbus-run-session", "--", "gsettings"]
        else:
            cmd = ["dbus-launch", "--exit-with-session", "gsettings"]
        return cmd

    def _get(self):
        """
        get the value for user in gsettings

        """
        user = self.USER
        try:
            uid = pwd.getpwnam(user).pw_uid
        except KeyError:
            log.info("User does not exist")
            return False

        cmd = self.gsetting_command + ["get", str(self.SCHEMA), str(self.KEY)]
        environ = {}
        environ["XDG_RUNTIME_DIR"] = "/run/user/{0}".format(uid)
        result = __salt__["cmd.run_all"](
            cmd, runas=user, env=environ, python_shell=False
        )

        if "stdout" in result:
            if "uint32" in result["stdout"]:
                return re.sub("uint32 ", "", result["stdout"])
            else:
                return result["stdout"]
        else:
            return False

    def _set(self, value):
        """
        set the value for user in gsettings

        """
        user = self.USER
        try:
            uid = pwd.getpwnam(user).pw_uid
        except KeyError:
            log.info("User does not exist")
            result = {}
            result["retcode"] = 1
            result["stdout"] = "User {0} does not exist".format(user)
            return result

        cmd = self.gsetting_command + ["set", self.SCHEMA, self.KEY, value]
        environ = {}
        environ["XDG_RUNTIME_DIR"] = "/run/user/{0}".format(uid)
        result = __salt__["cmd.run_all"](
            cmd, runas=user, env=environ, python_shell=False
        )
        return result


def ping(**kwargs):
    """
    A test to ensure the GNOME module is loaded

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.ping user=<username>

    """
    return True


def getIdleDelay(**kwargs):
    """
    Return the current idle delay setting in seconds

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.getIdleDelay user=<username>

    """
    _gsession = _GSettings(
        user=kwargs.get("user"), schema="org.gnome.desktop.session", key="idle-delay"
    )
    return _gsession._get()


def setIdleDelay(delaySeconds, **kwargs):
    """
    Set the current idle delay setting in seconds

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.setIdleDelay <seconds> user=<username>

    """
    _gsession = _GSettings(
        user=kwargs.get("user"), schema="org.gnome.desktop.session", key="idle-delay"
    )
    return _gsession._set(delaySeconds)


def getClockFormat(**kwargs):
    """
    Return the current clock format, either 12h or 24h format.

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.getClockFormat user=<username>

    """
    _gsession = _GSettings(
        user=kwargs.get("user"),
        schema="org.gnome.desktop.interface",
        key="clock-format",
    )
    return _gsession._get()


def setClockFormat(clockFormat, **kwargs):
    """
    Set the clock format, either 12h or 24h format.

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.setClockFormat <12h|24h> user=<username>

    """
    if clockFormat != "12h" and clockFormat != "24h":
        return False
    _gsession = _GSettings(
        user=kwargs.get("user"),
        schema="org.gnome.desktop.interface",
        key="clock-format",
    )
    return _gsession._set(clockFormat)


def getClockShowDate(**kwargs):
    """
    Return the current setting, if the date is shown in the clock

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.getClockShowDate user=<username>

    """
    _gsession = _GSettings(
        user=kwargs.get("user"),
        schema="org.gnome.desktop.interface",
        key="clock-show-date",
    )
    return _gsession._get()


def setClockShowDate(kvalue, **kwargs):
    """
    Set whether the date is visible in the clock

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.setClockShowDate <True|False> user=<username>

    """
    if kvalue is not True and kvalue is not False:
        return False
    _gsession = _GSettings(
        user=kwargs.get("user"),
        schema="org.gnome.desktop.interface",
        key="clock-show-date",
    )
    return _gsession._set(kvalue)


def getIdleActivation(**kwargs):
    """
    Get whether the idle activation is enabled

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.getIdleActivation user=<username>

    """
    _gsession = _GSettings(
        user=kwargs.get("user"),
        schema="org.gnome.desktop.screensaver",
        key="idle-activation-enabled",
    )
    return _gsession._get()


def setIdleActivation(kvalue, **kwargs):
    """
    Set whether the idle activation is enabled

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.setIdleActivation <True|False> user=<username>

    """
    if kvalue is not True and kvalue is not False:
        return False
    _gsession = _GSettings(
        user=kwargs.get("user"),
        schema="org.gnome.desktop.screensaver",
        key="idle-activation-enabled",
    )
    return _gsession._set(kvalue)


def get(schema=None, key=None, user=None, **kwargs):
    """
    Get key in a particular GNOME schema

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.get user=<username> schema=org.gnome.desktop.screensaver key=idle-activation-enabled

    """
    _gsession = _GSettings(user=user, schema=schema, key=key)
    return _gsession._get()


def set_(schema=None, key=None, user=None, value=None, **kwargs):
    """
    Set key in a particular GNOME schema

    CLI Example:

    .. code-block:: bash

        salt '*' gnome.set user=<username> schema=org.gnome.desktop.screensaver key=idle-activation-enabled value=False

    """
    _gsession = _GSettings(user=user, schema=schema, key=key)
    return _gsession._set(value)

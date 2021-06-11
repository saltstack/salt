# -*- coding: utf-8 -*-
"""
Support for Apache

Please note: The functions in here are SUSE-specific. Placing them in this
separate file will allow them to load only on SUSE systems, while still
loading under the ``apache`` namespace.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.utils.path

log = logging.getLogger(__name__)

__virtualname__ = "apache"


def __virtual__():
    """
    Only load the module if apache is installed.
    """
    if salt.utils.path.which("apache2ctl") and __grains__["os_family"] == "Suse":
        return __virtualname__
    return (False, "apache execution module not loaded: apache not installed.")


def check_mod_enabled(mod):
    """
    Checks to see if the specific apache mod is enabled.

    This will only be functional on operating systems that support
    `a2enmod -l` to list the enabled mods.

    CLI Example:

    .. code-block:: bash

        salt '*' apache.check_mod_enabled status
    """
    if mod.endswith(".load") or mod.endswith(".conf"):
        mod_name = mod[:-5]
    else:
        mod_name = mod

    cmd = "a2enmod -l"
    try:
        active_mods = __salt__["cmd.run"](cmd, python_shell=False).split(" ")
    except Exception as e:  # pylint: disable=broad-except
        return e

    return mod_name in active_mods


def a2enmod(mod):
    """
    Runs a2enmod for the given mod.

    CLI Example:

    .. code-block:: bash

        salt '*' apache.a2enmod vhost_alias
    """
    ret = {}
    command = ["a2enmod", mod]

    try:
        status = __salt__["cmd.retcode"](command, python_shell=False)
    except Exception as e:  # pylint: disable=broad-except
        return e

    ret["Name"] = "Apache2 Enable Mod"
    ret["Mod"] = mod

    if status == 1:
        ret["Status"] = "Mod {0} Not found".format(mod)
    elif status == 0:
        ret["Status"] = "Mod {0} enabled".format(mod)
    else:
        ret["Status"] = status

    return ret


def a2dismod(mod):
    """
    Runs a2dismod for the given mod.

    CLI Example:

    .. code-block:: bash

        salt '*' apache.a2dismod vhost_alias
    """
    ret = {}
    command = ["a2dismod", mod]

    try:
        status = __salt__["cmd.retcode"](command, python_shell=False)
    except Exception as e:  # pylint: disable=broad-except
        return e

    ret["Name"] = "Apache2 Disable Mod"
    ret["Mod"] = mod

    if status == 256:
        ret["Status"] = "Mod {0} Not found".format(mod)
    elif status == 0:
        ret["Status"] = "Mod {0} disabled".format(mod)
    else:
        ret["Status"] = status

    return ret

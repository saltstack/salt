# -*- coding: utf-8 -*-
"""

This module allows you to control the power settings of a windows minion via
powercfg.

.. versionadded:: 2015.8.0

.. code-block:: yaml

    # Set timeout to 30 minutes on battery power
    monitor:
        powercfg.set_timeout:
            - value: 30
            - power: dc
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt Libs
import salt.utils.data
import salt.utils.platform

log = logging.getLogger(__name__)

__virtualname__ = "powercfg"


def __virtual__():
    """
    Only work on Windows
    """
    if not salt.utils.platform.is_windows():
        return False, "PowerCFG: Module only works on Windows"
    return __virtualname__


def set_timeout(name, value, power="ac", scheme=None):
    """
    Set the sleep timeouts of specific items such as disk, monitor, etc.

    Args:

        name (str)
            The setting to change, can be one of the following:

                - ``monitor``
                - ``disk``
                - ``standby``
                - ``hibernate``

        value (int):
            The amount of time in minutes before the item will timeout

        power (str):
            Set the value for AC or DC power. Default is ``ac``. Valid options
            are:

                - ``ac`` (AC Power)
                - ``dc`` (Battery)

        scheme (str):
            The scheme to use, leave as ``None`` to use the current. Default is
            ``None``. This can be the GUID or the Alias for the Scheme. Known
            Aliases are:

                - ``SCHEME_BALANCED`` - Balanced
                - ``SCHEME_MAX`` - Power saver
                - ``SCHEME_MIN`` - High performance

    CLI Example:

    .. code-block:: yaml

        # Set monitor timeout to 30 minutes on Battery
        monitor:
          powercfg.set_timeout:
            - value: 30
            - power: dc

        # Set disk timeout to 10 minutes on AC Power
        disk:
          powercfg.set_timeout:
            - value: 10
            - power: ac
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    # Validate name values
    name = name.lower()
    if name not in ["monitor", "disk", "standby", "hibernate"]:
        ret["result"] = False
        ret["comment"] = '"{0}" is not a valid setting'.format(name)
        log.debug(ret["comment"])
        return ret

    # Validate power values
    power = power.lower()
    if power not in ["ac", "dc"]:
        ret["result"] = False
        ret["comment"] = '"{0}" is not a power type'.format(power)
        log.debug(ret["comment"])
        return ret

    # Get current settings
    old = __salt__["powercfg.get_{0}_timeout".format(name)](scheme=scheme)

    # Check current settings
    if old[power] == value:
        ret["comment"] = "{0} timeout on {1} power is already set to {2}" "".format(
            name.capitalize(), power.upper(), value
        )
        return ret
    else:
        ret["comment"] = "{0} timeout on {1} power will be set to {2}" "".format(
            name.capitalize(), power.upper(), value
        )

    # Check for test=True
    if __opts__["test"]:
        ret["result"] = None
        return ret

    # Set the timeout value
    __salt__["powercfg.set_{0}_timeout".format(name)](
        timeout=value, power=power, scheme=scheme
    )

    # Get the setting after the change
    new = __salt__["powercfg.get_{0}_timeout".format(name)](scheme=scheme)

    changes = salt.utils.data.compare_dicts(old, new)

    if changes:
        ret["changes"] = {name: changes}
        ret["comment"] = "{0} timeout on {1} power set to {2}" "".format(
            name.capitalize(), power.upper(), value
        )
        log.debug(ret["comment"])
    else:
        ret["changes"] = {}
        ret["comment"] = "Failed to set {0} timeout on {1} power to {2}" "".format(
            name, power.upper(), value
        )
        log.debug(ret["comment"])
        ret["result"] = False

    return ret

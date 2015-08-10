# -*- coding: utf-8 -*-
'''

This module allows you to control the power settings of a windows minion via
powercfg.

.. versionadded:: 2015.8.0

.. code-block:: yaml

    monitor:
        powercfg.set_timeout:
            - value: 30
            - power: dc
'''

# Import Python Libs
from __future__ import absolute_import
import logging

log = logging.getLogger(__name__)

__virtualname__ = "powercfg"


def __virtual__():
    '''
    Only work on Windows
    '''
    if __grains__['os'] == 'Windows':
        return __virtualname__
    return False


def _check_or_set(check_func, set_func, value, power):
    values = check_func()
    if values[power] == value:
        return True
    else:
        set_func(value, power)
        return False


def set_timeout(name, value, power="ac"):
    '''
    Set the sleep timeouts of specific items such as disk, monitor.

    CLI Example:

    .. code-block:: yaml

        monitor:
            powercfg.set_timeout:
                - value: 30
                - power: dc

        disk:
            powercfg.set_timeout:
                - value: 12
                - power: ac

    name
        The setting to change, can be one of the following: monitor, disk, standby, hibernate

    timeout
        The amount of time in minutes before the item will timeout i.e the monitor

    power
        Should we set the value for AC or DC (battery)? Valid options ac,dc.
    '''
    ret = {'name': name,
           'result': True,
           'comment': '',
           'changes': {}}

    comment = []

    if name not in ["monitor", "disk", "standby", "hibernate"]:
        ret["result"] = False
        comment.append("{0} is not a valid setting".format(name))
    elif power not in ["ac", "dc"]:
        ret["result"] = False
        comment.append("{0} is not a power type".format(power))
    else:
        check_func = __salt__["powercfg.get_{0}_timeout".format(name)]
        set_func = __salt__["powercfg.set_{0}_timeout".format(name)]

        values = check_func()
        if values[power] == value:
            comment.append("{0} {1} is already set with the value {2}.".format(name, power, value))
        else:
            ret['changes'] = {name: {power: value}}
            set_func(value, power)

    ret['comment'] = ' '.join(comment)
    return ret

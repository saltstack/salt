# -*- coding: utf-8 -*-
"""
Monit state
===========

Manage monit states

.. code-block:: yaml

    monit_enable_service_monitoring:
      monit.monitor:
        - name: service

    monit_disable_service_monitoring:
      monit.unmonitor:
        - name: service

.. note::
    Use of these states require that the :mod:`monit <salt.modules.monit>`
    execution module is available.
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    """
    Only make this state available if the monit module is available.
    """
    return "monit" if "monit.summary" in __salt__ else False


def monitor(name):
    """
    Get the summary from module monit and try to see if service is
    being monitored. If not then monitor the service.
    """
    ret = {"result": None, "name": name, "comment": "", "changes": {}}
    result = __salt__["monit.summary"](name)

    try:
        for key, value in result.items():
            if "Running" in value[name]:
                ret["comment"] = ("{0} is being being monitored.").format(name)
                ret["result"] = True
            else:
                if __opts__["test"]:
                    ret["comment"] = "Service {0} is set to be monitored.".format(name)
                    ret["result"] = None
                    return ret
                __salt__["monit.monitor"](name)
                ret["comment"] = ("{0} started to be monitored.").format(name)
                ret["changes"][name] = "Running"
                ret["result"] = True
                break
    except KeyError:
        ret["comment"] = ("{0} not found in configuration.").format(name)
        ret["result"] = False

    return ret


def unmonitor(name):
    """
    Get the summary from module monit and try to see if service is
    being monitored. If it is then stop monitoring the service.
    """
    ret = {"result": None, "name": name, "comment": "", "changes": {}}
    result = __salt__["monit.summary"](name)

    try:
        for key, value in result.items():
            if "Not monitored" in value[name]:
                ret["comment"] = ("{0} is not being monitored.").format(name)
                ret["result"] = True
            else:
                if __opts__["test"]:
                    ret["comment"] = "Service {0} is set to be unmonitored.".format(
                        name
                    )
                    ret["result"] = None
                    return ret
                __salt__["monit.unmonitor"](name)
                ret["comment"] = ("{0} stopped being monitored.").format(name)
                ret["changes"][name] = "Not monitored"
                ret["result"] = True
                break
    except KeyError:
        ret["comment"] = ("{0} not found in configuration.").format(name)
        ret["result"] = False

    return ret

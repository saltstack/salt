"""
Manage RabbitMQ Plugins
=======================

.. versionadded:: 2014.1.0

Example:

.. code-block:: yaml

    some_plugin:
      rabbitmq_plugin.enabled: []
"""


import logging

from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if RabbitMQ is installed.
    """
    if __salt__["cmd.has_exec"]("rabbitmqctl"):
        return True
    return (False, "Command not found: rabbitmqctl")


def enabled(name, runas=None):
    """
    Ensure the RabbitMQ plugin is enabled.

    name
        The name of the plugin
    runas
        The user to run the rabbitmq-plugin command as
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        plugin_enabled = __salt__["rabbitmq.plugin_is_enabled"](name, runas=runas)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = "Error: {}".format(err)
        return ret

    if plugin_enabled:
        ret["comment"] = "Plugin '{}' is already enabled.".format(name)
        return ret

    if not __opts__["test"]:
        try:
            __salt__["rabbitmq.enable_plugin"](name, runas=runas)
        except CommandExecutionError as err:
            ret["result"] = False
            ret["comment"] = "Error: {}".format(err)
            return ret
    ret["changes"].update({"old": "", "new": name})

    if __opts__["test"] and ret["changes"]:
        ret["result"] = None
        ret["comment"] = "Plugin '{}' is set to be enabled.".format(name)
        return ret

    ret["comment"] = "Plugin '{}' was enabled.".format(name)
    return ret


def disabled(name, runas=None):
    """
    Ensure the RabbitMQ plugin is disabled.

    name
        The name of the plugin
    runas
        The user to run the rabbitmq-plugin command as
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        plugin_enabled = __salt__["rabbitmq.plugin_is_enabled"](name, runas=runas)
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = "Error: {}".format(err)
        return ret

    if not plugin_enabled:
        ret["comment"] = "Plugin '{}' is already disabled.".format(name)
        return ret

    if not __opts__["test"]:
        try:
            __salt__["rabbitmq.disable_plugin"](name, runas=runas)
        except CommandExecutionError as err:
            ret["result"] = False
            ret["comment"] = "Error: {}".format(err)
            return ret
    ret["changes"].update({"old": name, "new": ""})

    if __opts__["test"] and ret["changes"]:
        ret["result"] = None
        ret["comment"] = "Plugin '{}' is set to be disabled.".format(name)
        return ret

    ret["comment"] = "Plugin '{}' was disabled.".format(name)
    return ret

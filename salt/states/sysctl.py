"""
Configuration of the kernel using sysctl
========================================

Control the kernel sysctl system.

.. code-block:: yaml

  vm.swappiness:
    sysctl.present:
      - value: 20
"""

import re

from salt.exceptions import CommandExecutionError


def __virtual__():
    """
    This state is only available on Minions which support sysctl
    """
    if "sysctl.show" in __salt__:
        return True
    return (False, "sysctl module could not be loaded")


def present(name, value, config=None):
    """
    Ensure that the named sysctl value is set in memory and persisted to the
    named configuration file. The default sysctl configuration file is
    /etc/sysctl.conf

    name
        The name of the sysctl value to edit

    value
        The sysctl value to apply

    config
        The location of the sysctl configuration file. If not specified, the
        proper location will be detected based on platform.
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    if config is None:
        # Certain linux systems will ignore /etc/sysctl.conf, get the right
        # default configuration file.
        if "sysctl.default_config" in __salt__:
            config = __salt__["sysctl.default_config"]()
        else:
            config = "/etc/sysctl.conf"

    if __opts__["test"]:
        configured = __salt__["sysctl.show"](config_file=config)
        if configured is None:
            ret["result"] = None
            ret["comment"] = (
                "Sysctl option {} might be changed, we failed to check "
                "config file at {}. The file is either unreadable, or "
                "missing.".format(name, config)
            )
            return ret
        current = __salt__["sysctl.get"](name)
        if current:
            if name in configured:
                if str(value).split() == current.split():
                    ret["result"] = True
                    ret["comment"] = "Sysctl value {} = {} is already set".format(
                        name, value
                    )
                    return ret
            else:
                if re.sub(" +|\t+", " ", current) != re.sub(" +|\t+", " ", str(value)):
                    ret["result"] = None
                    ret["comment"] = "Sysctl option {} set to be changed to {}".format(
                        name, value
                    )
                    return ret
                else:
                    ret["result"] = None
                    ret["comment"] = (
                        "Sysctl value is currently set on the running system but "
                        "not in a config file. Sysctl option {} set to be "
                        "changed to {} in config file.".format(name, value)
                    )
                    return ret
        elif not current and name in configured:
            ret["result"] = None
            ret["comment"] = (
                "Sysctl value {0} is present in configuration file but is not "
                "present in the running config. The value {0} is set to be "
                "changed to {1}".format(name, value)
            )
            return ret
        # otherwise, we don't have it set anywhere and need to set it
        ret["result"] = None
        ret["comment"] = "Sysctl option {} would be changed to {}".format(name, value)
        return ret

    try:
        update = __salt__["sysctl.persist"](name, value, config)
    except CommandExecutionError as exc:
        ret["result"] = False
        ret["comment"] = "Failed to set {} to {}: {}".format(name, value, exc)
        return ret

    if update == "Updated":
        ret["changes"] = {name: value}
        ret["comment"] = "Updated sysctl value {} = {}".format(name, value)
    elif update == "Already set":
        ret["comment"] = "Sysctl value {} = {} is already set".format(name, value)

    return ret

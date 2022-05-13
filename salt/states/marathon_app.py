"""
Configure Marathon apps via a salt proxy.

.. code-block:: yaml

    my_app:
      marathon_app.config:
        - config:
            cmd: "while [ true ] ; do echo 'Hello Marathon' ; sleep 5 ; done"
            cpus: 0.1
            mem: 10
            instances: 3

.. versionadded:: 2015.8.2
"""

import copy
import logging

import salt.utils.configcomparer

__proxyenabled__ = ["marathon"]
log = logging.getLogger(__file__)


def config(name, config):
    """
    Ensure that the marathon app with the given id is present and is configured
    to match the given config values.

    :param name: The app name/id
    :param config: The configuration to apply (dict)
    :return: A standard Salt changes dictionary
    """
    # setup return structure
    ret = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "",
    }

    # get existing config if app is present
    existing_config = None
    if __salt__["marathon.has_app"](name):
        existing_config = __salt__["marathon.app"](name)["app"]

    # compare existing config with defined config
    if existing_config:
        update_config = copy.deepcopy(existing_config)
        salt.utils.configcomparer.compare_and_update_config(
            config,
            update_config,
            ret["changes"],
        )
    else:
        # the app is not configured--we need to create it from scratch
        ret["changes"]["app"] = {
            "new": config,
            "old": None,
        }
        update_config = config

    # update the config if we registered any changes
    if ret["changes"]:
        # if test, report there will be an update
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Marathon app {} is set to be updated".format(name)
            return ret

        update_result = __salt__["marathon.update_app"](name, update_config)
        if "exception" in update_result:
            ret["result"] = False
            ret["comment"] = "Failed to update app config for {}: {}".format(
                name,
                update_result["exception"],
            )
            return ret
        else:
            ret["result"] = True
            ret["comment"] = "Updated app config for {}".format(name)
            return ret
    ret["result"] = True
    ret["comment"] = "Marathon app {} configured correctly".format(name)
    return ret


def absent(name):
    """
    Ensure that the marathon app with the given id is not present.

    :param name: The app name/id
    :return: A standard Salt changes dictionary
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    if not __salt__["marathon.has_app"](name):
        ret["result"] = True
        ret["comment"] = "App {} already absent".format(name)
        return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "App {} is set to be removed".format(name)
        return ret
    if __salt__["marathon.rm_app"](name):
        ret["changes"] = {"app": name}
        ret["result"] = True
        ret["comment"] = "Removed app {}".format(name)
        return ret
    else:
        ret["result"] = False
        ret["comment"] = "Failed to remove app {}".format(name)
        return ret


def running(name, restart=False, force=True):
    """
    Ensure that the marathon app with the given id is present and restart if set.

    :param name: The app name/id
    :param restart: Restart the app
    :param force: Override the current deployment
    :return: A standard Salt changes dictionary
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    if not __salt__["marathon.has_app"](name):
        ret["result"] = False
        ret["comment"] = "App {} cannot be restarted because it is absent".format(name)
        return ret
    if __opts__["test"]:
        ret["result"] = None
        qualifier = "is" if restart else "is not"
        ret["comment"] = "App {} {} set to be restarted".format(name, qualifier)
        return ret
    restart_result = __salt__["marathon.restart_app"](name, restart, force)
    if "exception" in restart_result:
        ret["result"] = False
        ret["comment"] = "Failed to restart app {}: {}".format(
            name, restart_result["exception"]
        )
        return ret
    else:
        ret["changes"] = restart_result
        ret["result"] = True
        qualifier = "Restarted" if restart else "Did not restart"
        ret["comment"] = "{} app {}".format(qualifier, name)
        return ret

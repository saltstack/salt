"""RESTCONF
State module for  Proxy minions

:codeauthor: Jamie (Bear) Murphy <jamiemurphyit@gmail.com>
:maturity:   new
:platform:   any

About
=====
This state module was designed to manage RESTCONF states.
This module relies on the RESTCONF proxy module to interface with the devices.
"""


import difflib
import json
import logging

import yaml

import salt.utils.odict

log = logging.getLogger(__file__)


def __virtual__():
    if "restconf.set_data" in __salt__:
        return True
    return (False, "RESTCONF module could not be loaded")


def config_manage(
    name, path, method, config, init_path=None, init_method="PATCH", init_config=None
):
    """
    Ensure a specific value exists at a given path

    name:
        (str) The name for this rule

    path:
        (str) The RESTCONF path to set / get config

    method:
        (str) rest method to use eg GET, PUT, POST, PATCH, DELETE

    config:
        (dict) The new value at the given path

    init_path: (optional)
        (str) Alternative path incase the path doesnt exist on first pass

    init_method: (optional)
        (str) Method to use on alternative path when setting config, default: PATCH

    init_config: (optional)
        (dict) The new value at the given init path.
        This is only needed if you need to supply a different style of data to an init path.

    Examples:

    .. code-block:: yaml

        do_configure_restconf_endpoint:
          restconf.config_manage:
            - name: random_name_here
            - path: restconf/data/Cisco-IOS-XE-native:native/interface/GigabitEthernet=1%2F0%2F3
            - config:
                Cisco-IOS-XE-native:GigabitEthernet:
                  description: interfaceDescription
                  name: "1/0/3"

    """
    ret = {"result": False, "comment": ""}

    path = str(path)
    name = str(name)
    method = str(method)
    if path == "":
        ret["comment"] = "CRITICAL: path must not be blank"
        log.critical("path must not be blank")
        return ret
    if name == "":
        ret["comment"] = "CRITICAL: name is required"
        log.critical("name is required")
        return ret
    if method == "":
        ret["comment"] = "CRITICAL: method is required"
        log.critical("method is required")
        return ret
    if not isinstance(config, salt.utils.odict.OrderedDict):
        ret["comment"] = "CRITICAL: config must be an OrderedDict type"
        log.critical(
            "config is required, config must be a salt OrderedDict, not a %s",
            type(config),
        )
        return ret
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    # TODO: add template function so that config var does not need to be passed

    path_check = __salt__["restconf.path_check"](path, init_path)
    log.debug("path_check:")
    log.debug(path_check)
    if not path_check["result"]:
        ret["result"] = False
        ret["comment"] = "RESTCONF could not find a working PATH to get initial config"
        return ret

    use_conf = config
    if path_check["path_used"] == "init":
        # We will be creating a new endpoint as we are using the init path so config will be blank
        existing = {}
        if init_config is not None:
            # some init paths need a special config layout
            use_conf = init_config
    request_method = method
    if path_check["path_used"] == "init":
        request_method = init_method
        # since we are using the init method we are basicly doing a net new change
        path_check["request_restponse"] = {}

    proposed_config = json.loads(
        json.dumps(use_conf)
    )  # convert from orderedDict to Dict (which is now ordered by default in python3.8)

    log.debug(
        "existing path config(type: %s):\n%s",
        type(path_check["request_restponse"]),
        path_check["request_restponse"],
    )
    log.debug("proposed_config(type: %s):\n%s", type(proposed_config), proposed_config)

    # TODO: migrate the below == check to RecursiveDictDiffer when issue 59017 is fixed
    if path_check["request_restponse"] == proposed_config:
        ret["result"] = True
        ret["comment"] = "Config is already set"

    elif __opts__["test"] is True:
        ret["result"] = None
        ret["changes"]["changed"] = _compare_changes(
            path_check["request_restponse"], proposed_config
        )
        # ret["changes"]["rest_method"] = request_method
        ret["changes"]["rest_method_path"] = path_check["path_used"]
        ret["comment"] = "Config will be added"

    else:
        resp = __salt__["restconf.set_data"](
            path_check["request_path"], request_method, proposed_config
        )

        # Success
        if resp["status"] in [201, 200, 204]:
            ret["result"] = True
            ret["changes"]["changed"] = _compare_changes(
                path_check["request_restponse"], proposed_config
            )
            # ret["changes"]["rest_method"] = request_method
            ret["changes"]["rest_method_path"] = path_check["path_used"]
            ret["comment"] = "Successfully added config"
        else:
            ret["result"] = False
            if "dict" in resp:
                why = resp["dict"]
            elif "body" in resp:
                why = resp["body"]
            else:
                why = None
            ret["comment"] = (
                "failed to add / modify config. "
                "API Statuscode: {}, API Response: {}, URI: {}".format(
                    resp["status"], why, path_check["request_path"]
                )
            )
            log.debug("post_content: %s", json.dumps(proposed_config))

    return ret


def _compare_changes(old, new, output_style="yaml"):
    # option to switch to a json output

    old_raw = yaml.safe_dump(old, default_flow_style=False).splitlines()
    old = [
        " " + x for x in old_raw
    ]  # adding a space to start of each line to make it readable
    new_raw = yaml.safe_dump(new, default_flow_style=False).splitlines()
    new = [
        " " + x for x in new_raw
    ]  # adding a space to start of each line to make it readable
    if output_style == "json":
        old = json.dumps(old, sort_keys=False, indent=2).splitlines()
        new = json.dumps(new, sort_keys=False, indent=2).splitlines()

    diffout = difflib.unified_diff(old, new, fromfile="before", tofile="after")
    diffclean = "\n".join([x.replace("\n", "") for x in diffout])
    log.debug("resconf_diff:")
    log.debug(diffclean)
    return diffclean

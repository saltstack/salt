"""
State module for restconf Proxy minions

:codeauthor: Jamie (Bear) Murphy <jamiemurphyit@gmail.com>
:maturity:   new
:platform:   any

About
=====
This state module was designed to manage restconf states.
This module relies on the restconf proxy module to interface with the devices.
"""


import json
import logging

# try:
#     HAS_DEEPDIFF = True
#     from deepdiff import DeepDiff
# except ImportError:
#     HAS_DEEPDIFF = False
from salt.utils.dictdiffer import DictDiffer, RecursiveDictDiffer

# from salt.utils.odict import OrderedDict


log = logging.getLogger(__file__)


def __virtual__():
    # if not HAS_DEEPDIFF:
    #     return (
    #         False,
    #         "Missing dependency: The restconf states method requires the 'deepdiff' Python module.",
    #     )
    if "restconf.set_data" in __salt__:
        return True
    return (False, "restconf module could not be loaded")


def config_manage(
    name, uri, method, config, init_uri=None, init_method="PATCH", init_config=None
):
    """
    Ensure a specific value exists at a given path

    name:
        (str) The name for this rule

    uri:
        (str) The restconf uri to set / get config

    method:
        (str) rest method to use eg GET, PUT, POST, PATCH, DELETE

    config:
        (dict) The new value at the given path

    init_uri: (optional)
        (str) Alternative URI incase the URI doesnt exist on first pass

    init_method: (optional)
        (str) Method to use on alternative URI when setting config, default: PATCH

    init_config: (optional)
        (dict) The new value at the given init path.
        This is only needed if you need to supply a different style of data to an init uri.

    Examples:

    .. code-block:: yaml

        do_configure_restconf_endpoint:
          restconf.config_manage:
            - name: random_name_here
            - uri: restconf/data/Cisco-IOS-XE-native:native/interface/GigabitEthernet=1%2F0%2F3
            - config:
                Cisco-IOS-XE-native:GigabitEthernet:
                  description: interfaceDescription
                  name: "1/0/3"

    """

    uri = str(uri)
    name = str(name)
    method = str(method)
    if uri == "":
        log.critical("uri must not be blank")
        return False
    if name == "":
        log.critical("Name is required")
        return False
    if method == "":
        log.critical("method is required")
        return False
    if "salt.utils.odict.OrderedDict" not in str(type(config)):
        log.critical(
            "config is required, config must be a salt salt.utils.odict.OrderedDict {t}".format(
                t=type(config)
            )
        )
        return False

    # TODO: add template function so that config var does not need to be passed
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    found_working_uri = False
    uri_used = ""
    existing_raw = __salt__["restconf.get_data"](uri)
    print(existing_raw)
    request_uri = ""
    request_method = ""

    # TODO: this could probaby be a loop
    if existing_raw["status"] in [200]:
        existing = existing_raw["dict"]
        found_working_uri = True
        uri_used = "Primary"
        request_uri = uri
        request_method = method

    if not found_working_uri:
        existing_raw_init = __salt__["restconf.get_data"](init_uri)
        if existing_raw_init["status"] in [200]:
            existing = existing_raw_init["dict"]
            found_working_uri = True
            uri_used = "init"
            request_uri = init_uri
            request_method = init_method

    if not found_working_uri:
        ret["result"] = False
        ret["comment"] = "restconf could not find a working URI to get initial config"
        return ret
    # TODO: END

    use_conf = config
    if uri_used == "init":
        # We will be creating a new endpoint as we are using the init uri so config will be blank
        existing = {}
        if init_config is not None:
            # some init uris need a special config layout
            use_conf = init_config

    dict_config = json.loads(
        json.dumps(use_conf)
    )  # convert from orderedDict to Dict (which is now ordered by default in python3.8)

    log.debug("existing:")
    log.debug(existing)
    log.debug("dict_config")
    log.debug(dict_config)

    if existing == dict_config:
        ret["result"] = True
        ret["comment"] = "Config is already set"

    elif __opts__["test"] is True:
        ret["result"] = None
        ret["changes"]["method"] = "test"
        ret["comment"] = "Config will be added"

        try:
            diff = RecursiveDictDiffer(existing, dict_config, False)
            ret["changes"]["diff_method"] = "RecursiveDictDiffer"
            ret["changes"]["new"] = diff.added()
            ret["changes"]["removed"] = diff.removed()
            ret["changes"]["changed"] = diff.changed()
        except TypeError:  # https://github.com/saltstack/salt/issues/59017
            diff = DictDiffer(dict_config, existing)  # , True)
            diff_method = "DictDiffer"
            ret["changes"]["diff_method"] = "DictDiffer"
            ret["changes"]["new"] = diff.added()
            ret["changes"]["removed"] = diff.removed()
            ret["changes"]["changed"] = diff.changed()

    else:
        resp = __salt__["restconf.set_data"](request_uri, request_method, dict_config)
        # Success
        if resp["status"] in [201, 200, 204]:
            ret["result"] = True
            ret["changes"]["method"] = uri_used
            ret["comment"] = "Successfully added config"
            diff_method = "RecursiveDictDiffer"
            try:
                diff = RecursiveDictDiffer(existing, dict_config, False)
            except TypeError:  # https://github.com/saltstack/salt/issues/59017
                diff = DictDiffer(dict_config, existing)  # , True)
                diff_method = "DictDiffer"
            ret["changes"]["diff_method"] = diff_method
            ret["changes"]["new"] = diff.added()
            ret["changes"]["removed"] = diff.removed()
            ret["changes"]["changed"] = diff.changed()
            if method == "PATCH":
                ret["changes"]["removed"] = None
        # full failure
        else:
            ret["result"] = False
            if "dict" in resp:
                why = resp["dict"]
            elif "body" in resp:
                why = resp["body"]
            else:
                why = None
            ret[
                "comment"
            ] = "failed to add / modify config. API Statuscode: {s}, API Response: {w}, URI:{u}".format(
                w=why, s=resp["status"], u=uri_used
            )
            print("post_content: {b}".format(b=json.dumps(dict_config)))

    return ret

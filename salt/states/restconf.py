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

from salt.utils.data import recursive_diff

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

    uri_check = __salt__["restconf.uri_check"](uri, init_uri)
    log.debug("uri_check:")
    log.debug(uri_check)
    if not uri_check[0]:
        ret["result"] = False
        ret["comment"] = "restconf could not find a working URI to get initial config"
        return ret
    # uri_check['uri_used']
    # uri_check['request_uri']
    # uri_check['request_restponse']

    use_conf = config
    if uri_check[1]["uri_used"] == "init":
        # We will be creating a new endpoint as we are using the init uri so config will be blank
        existing = {}
        if init_config is not None:
            # some init uris need a special config layout
            use_conf = init_config
    request_method = method
    if uri_check[1]["uri_used"] == "init":
        request_method = init_method
        # since we are using the init method we are basicly doing a net new change
        uri_check[1]["request_restponse"] = {}

    proposed_config = json.loads(
        json.dumps(use_conf)
    )  # convert from orderedDict to Dict (which is now ordered by default in python3.8)

    log.debug("existing uri config:")
    log.debug(type(uri_check[1]["request_restponse"]))
    log.debug(uri_check[1]["request_restponse"])
    log.debug("proposed_config:")
    log.debug(type(proposed_config))
    log.debug(proposed_config)

    # TODO: migrate the below == check to RecursiveDictDiffer when issue 59017 is fixed
    if uri_check[1]["request_restponse"] == proposed_config:
        ret["result"] = True
        ret["comment"] = "Config is already set"

    elif __opts__["test"] is True:
        ret["result"] = None
        ret["changes"] = _compare_changes(
            uri_check[1]["request_restponse"], proposed_config
        )
        ret["changes"]["method"] = "test"
        ret["comment"] = "Config will be added"

    else:
        resp = __salt__["restconf.set_data"](
            uri_check[1]["request_uri"], request_method, proposed_config
        )
        # Success
        if resp["status"] in [201, 200, 204]:
            ret["result"] = True
            ret["changes"] = _compare_changes(
                uri_check[1]["request_restponse"], proposed_config
            )
            ret["changes"]["method"] = request_method
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
                "API Statuscode: {s}, API Response: {w}, URI:{u}".format(
                    w=why, s=resp["status"], u=uri_check[1]["request_uri"]
                )
            )
            print("post_content: {b}".format(b=json.dumps(proposed_config)))

    return ret


def _compare_changes(old, new):
    compare_complete = False
    changes = {}
    try:
        changes = recursive_diff(old, new)
        compare_complete = True
        changes["diff_method"] = "recursive_diff"
    except ValueError:  # pylint: disable=W0703
        # https://github.com/saltstack/salt/issues/59017#issuecomment-733744465
        compare_complete = False
        changes = {}

    if not compare_complete:
        try:
            diff = RecursiveDictDiffer(old, new, False)
            changes["diff_method"] = "RecursiveDictDiffer"
            changes["new"] = diff.added()
            changes["removed"] = diff.removed()
            changes["changed"] = diff.changed()
        except TypeError:  # https://github.com/saltstack/salt/issues/59017
            diff = DictDiffer(new, old)
            diff_method = "DictDiffer"
            changes["diff_method"] = "DictDiffer"
            changes["new"] = diff.added()
            changes["removed"] = diff.removed()
            changes["changed"] = diff.changed()
    return changes

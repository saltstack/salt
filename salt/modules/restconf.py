"""
Execution module for RESTCONF Proxy minions

:codeauthor: Jamie (Bear) Murphy <jamiemurphyit@gmail.com>
:maturity:   new
:platform:   any

"""


import logging

__proxyenabled__ = ["restconf"]
__virtualname__ = "restconf"

log = logging.getLogger(__file__)


def __virtual__():
    if __opts__.get("proxy", {}).get("proxytype") != __virtualname__:
        return False, "Proxytype does not match: {}".format(__virtualname__)
    return True


def info():
    """
    Returns the RESTCONF capabilities PATH

    CLI Example:

    .. code-block:: bash

        salt '*' restconf.info
    """
    return __proxy__["restconf.request"](
        "restconf/data/ietf-restconf-monitoring:restconf-state/capabilities/capability"
    )


def get_data(path):
    """
    Returns an object containing the content of the request path with a GET request.
    Data returned will contain a dict with at minimum a key of "status" containing the http status code
    Other keys that should be available error (if http error), body, dict (parsed json to dict)

    CLI Example:

    .. code-block:: bash

        salt '*' restconf.get_data restconf/yang-library-version
    """
    return __proxy__["restconf.request"](path)


def set_data(path, method, dict_payload):
    """
    Sends a post/patch/other type of rest method to a specified path with the specified method with specified payload

    CLI Example:

    .. code-block:: bash

        salt '*' restconf.set_data restconf/yang-library-version method=PATCH dict_payload=""
    """
    return __proxy__["restconf.request"](path, method, dict_payload)


def path_check(primary_path, init_path):
    """
    Used to check which path responds with a 200 status
    Returns an array of True/False and a dict with keys path + path_method + response data, used in states code.

    CLI Example:

    .. code-block:: bash

        salt '*' restconf.path_check restconf/yang-library-version/specifc_item restconf/yang-library-version
    """
    ret = {"result": False}

    log.debug("modules_restconf_path_check: about to attempt to get primary path")
    existing_raw = __salt__["restconf.get_data"](primary_path)

    if existing_raw["status"] == 200:
        log.debug("modules_restconf_path_check: found a valid path at primary_path")
        existing = existing_raw["dict"]
        ret["result"] = True
        ret["path_used"] = "primary"
        ret["request_path"] = primary_path
        ret["request_restponse"] = existing

    if not ret["result"]:
        if init_path is not None:
            existing_raw_init = __salt__["restconf.get_data"](init_path)
            if existing_raw_init["status"] in [200]:
                log.debug(
                    "modules_restconf_path_check: found a valid path at init_path"
                )
                existing = existing_raw_init["dict"]
                ret["result"] = True
                ret["path_used"] = "init"
                ret["request_path"] = init_path
                ret["request_restponse"] = existing

    if not ret["result"]:
        log.debug(
            "modules_restconf_path_check: restconf could not find a working path to get initial config"
        )
        ret["result"] = False

    return ret

"""
Execution module for Restconf Proxy minions

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
        Should return some quick state info of the restconf device?
    """
    return "Hello i am a restconf module"


def get_data(uri):
    """
    Returns an object containing the content of the request uri with a GET request.
    Data returned will contain a dict with at minimum a key of "status" containing the http status code
    Other keys that should be available error (if http error), body, dict (parsed json to dict)

    CLI Example:

    .. code-block:: bash

        salt '*' restconf.get_data restconf/yang-library-version
    """
    return __proxy__["restconf.request"](uri)


def set_data(uri, method, dict_payload):
    """
    Sends a post/patch/other type of rest method to a specified URI with the specified method with specified payload

    CLI Example:

    .. code-block:: bash

        salt '*' restconf.get_data restconf/yang-library-version method=PATCH dict_payload=""
    """
    return __proxy__["restconf.request"](uri, method, dict_payload)


def uri_check(primary_uri, init_uri):
    """
    Used to check which URI responds with a 200 status
    Returns an array of True/False and a dict with keys uri + uri_method + response data, used in states code.
    """
    ret = {"result": False}

    log.debug("modules_restconf_uri_check: about to attempt to get primary uri")
    existing_raw = __salt__["restconf.get_data"](primary_uri)

    if existing_raw["status"] in [200]:
        log.debug("modules_restconf_uri_check: found a valid uri at primary_uri")
        existing = existing_raw["dict"]
        ret["result"] = True
        ret["uri_used"] = "primary"
        ret["request_uri"] = primary_uri
        ret["request_restponse"] = existing

    if not ret["result"]:
        if init_uri is not None:
            existing_raw_init = __salt__["restconf.get_data"](init_uri)
            if existing_raw_init["status"] in [200]:
                log.debug("modules_restconf_uri_check: found a valid uri at init_uri")
                existing = existing_raw_init["dict"]
                ret["result"] = True
                ret["uri_used"] = "init"
                ret["request_uri"] = init_uri
                ret["request_restponse"] = existing

    if not ret["result"]:
        log.debug(
            "modules_restconf_uri_check: restconf could not find a working URI to get initial config"
        )
        ret["result"] = False

    return ret

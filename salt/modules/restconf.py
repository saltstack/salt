"""
Execution module for Restconf Proxy minions

:codeauthor: Jamie (Bear) Murphy <jamiemurphyit@gmail.com>
:maturity:   new
:platform:   any

"""

__proxyenabled__ = ["restconf"]
__virtualname__ = "restconf"


def __virtual__():
    if __opts__.get("proxy", {}).get("proxytype") != __virtualname__:  # noqa: F821
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
    return __proxy__["restconf.request"](uri)  # noqa: F821


def set_data(uri, method, dict_payload):
    """
    Sends a post/patch/other type of rest method to a specified URI with the specified method with specified payload

    CLI Example:

    .. code-block:: bash

        salt '*' restconf.get_data restconf/yang-library-version method=PATCH dict_payload=""
    """
    return __proxy__["restconf.request"](uri, method, dict_payload)  # noqa: F821

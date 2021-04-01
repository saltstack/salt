"""
Provide authentication using a REST call

REST auth can be defined like any other eauth module:

.. code-block:: yaml

    external_auth:
      rest:
        ^url: https://url/for/rest/call
        fred:
          - .*
          - '@runner'

If there are entries underneath the ^url entry then they are merged with any responses
from the REST call.  In the above example, assuming the REST call does not return
any additional ACLs, this will authenticate Fred via a REST call and allow him to
run any execution module and all runners.

The REST call should return a JSON object that maps to a regular eauth YAML structure
as above.

"""


import logging

import salt.utils.http

log = logging.getLogger(__name__)

__virtualname__ = "rest"


def __virtual__():
    return __virtualname__


def rest_auth_setup():

    if "^url" in __opts__["external_auth"]["rest"]:
        return __opts__["external_auth"]["rest"]["^url"]
    else:
        return False


def auth(username, password):
    """
    REST authentication
    """

    url = rest_auth_setup()

    data = {"username": username, "password": password}

    # Post to the API endpoint. If 200 is returned then the result will be the ACLs
    # for this user
    result = salt.utils.http.query(
        url, method="POST", data=data, status=True, decode=True
    )
    if result["status"] == 200:
        log.debug("eauth REST call returned 200: %s", result)
        if result["dict"] is not None:
            return result["dict"]
        return True
    else:
        log.debug("eauth REST call failed: %s", result)
        return False

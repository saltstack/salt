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

The REST call should return a JSON array that maps to a regular eauth YAML
structure of a user as above.

"""

import logging

import salt.utils.http

log = logging.getLogger(__name__)

__virtualname__ = "rest"


def __virtual__():
    return __virtualname__


def _rest_auth_setup():

    if "^url" in __opts__["external_auth"]["rest"]:
        return __opts__["external_auth"]["rest"]["^url"]
    else:
        return False


def fetch(username, password):
    """
    Call the rest authentication endpoint
    """
    url = _rest_auth_setup()

    data = {"username": username, "password": password}

    # Post to the API endpoint. If 200 is returned then the result will be the ACLs
    # for this user
    result = salt.utils.http.query(
        url, method="POST", data=data, status=True, decode=True
    )

    if result["status"] == 200:
        log.debug("eauth REST call returned 200: %s", result)
        # Call is successful if None no acl data
        if result["dict"] is not None:
            return result["dict"]
        else:
            return []
    else:
        log.debug("eauth REST call failed: %s", result)
        return False


def auth(username, password):
    """
    REST authentication
    """
    # Check auth on API endpoint
    result = fetch(username, password)
    if result is False:
        log.debug("eauth REST call failed: %s", result)
        return False
    else:
        log.debug("eauth REST call Ok: %s", result)
        return True


def acl(username, **kwargs):
    """
    REST authorization
    """
    salt_eauth_acl = __opts__["external_auth"]["rest"].get(username, [])
    log.debug("acl from salt for user %s: %s", username, salt_eauth_acl)

    # Get ACL from REST API
    eauth_rest_acl = []
    result = fetch(username, kwargs["password"])
    if result:
        eauth_rest_acl = result
        log.debug("acl from rest for user %s: %s", username, eauth_rest_acl)

    merged_acl = salt_eauth_acl + eauth_rest_acl

    log.debug("acl from salt and rest merged for user %s: %s", username, merged_acl)
    # We have to make the .get's above return [] since we can't merge a
    # possible list and None. So if merged_acl is falsey we return None so
    # other eauth's can return an acl.
    if not merged_acl:
        return None
    else:
        return merged_acl

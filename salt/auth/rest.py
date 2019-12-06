# -*- coding: utf-8 -*-
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

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import salt libs
import salt.utils.http

log = logging.getLogger(__name__)

__virtualname__ = "rest"

cached_acl = {}


def __virtual__():
    return __virtualname__


def _rest_auth_setup():

    if "^url" in __opts__["external_auth"]["rest"]:
        return __opts__["external_auth"]["rest"]["^url"]
    else:
        return False


def auth(username, password):
    """
    REST authentication
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
        if result["dict"] is not None:
            cached_acl[username] = result["dict"]
        return True
    else:
        log.debug("eauth REST call failed: %s", result)
        return False


def acl(username, **kwargs):
    """
    REST authorization
    """
    salt_eauth_acl = __opts__["external_auth"]["rest"].get(username, [])
    log.debug("acl from salt for user %s: %s", username, salt_eauth_acl)

    eauth_rest_acl = cached_acl.get(username, [])
    log.debug("acl from cached rest for user %s: %s", username, eauth_rest_acl)
    # This might be an ACL only call with no auth before, so check the rest api
    # again
    if not eauth_rest_acl:
        # Update cached_acl from REST API
        result = auth(username, kwargs["password"])
        log.debug("acl rest result: %s", result)
        if result:
            eauth_rest_acl = cached_acl.get(username, [])
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

# -*- coding: utf-8 -*-
"""
Manage PagerDuty users.

Example:

    .. code-block:: yaml

    ensure bruce test user 1:
        pagerduty.user_present:
            - name: 'Bruce TestUser1'
            - email: bruce+test1@lyft.com
            - requester_id: P1GV5NT

"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    """
    Only load if the pygerduty module is available in __salt__
    """
    return "pagerduty_user" if "pagerduty_util.get_resource" in __salt__ else False


def present(profile="pagerduty", subdomain=None, api_key=None, **kwargs):
    """
    Ensure pagerduty user exists.
    Arguments match those supported by
    https://developer.pagerduty.com/documentation/rest/users/create.
    """
    return __salt__["pagerduty_util.resource_present"](
        "users", ["email", "name", "id"], None, profile, subdomain, api_key, **kwargs
    )


def absent(profile="pagerduty", subdomain=None, api_key=None, **kwargs):
    """
    Ensure pagerduty user does not exist.
    Name can be pagerduty id, email address, or user name.
    """
    return __salt__["pagerduty_util.resource_absent"](
        "users", ["email", "name", "id"], profile, subdomain, api_key, **kwargs
    )

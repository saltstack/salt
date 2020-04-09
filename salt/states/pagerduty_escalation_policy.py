# -*- coding: utf-8 -*-
"""

Manage PagerDuty escalation policies.

Schedules and users can be referenced by pagerduty ID, or by name, or by email address.

For example:

.. code-block:: yaml

    ensure test escalation policy:
        pagerduty_escalation_policy.present:
            - name: bruce test escalation policy
            - escalation_rules:
                - targets:
                    - type: schedule
                      id: 'bruce test schedule level1'
                    - type: user
                      id: 'Bruce Sherrod'
                  escalation_delay_in_minutes: 15
                - targets:
                    - type: schedule
                      id: 'bruce test schedule level2'
                  escalation_delay_in_minutes: 15
                - targets:
                    - type: user
                      id: 'Bruce TestUser1'
                    - type: user
                      id: 'Bruce TestUser2'
                    - type: user
                      id: 'Bruce TestUser3'
                    - type: user
                      id:  'bruce+test4@lyft.com'
                  escalation_delay_in_minutes: 15
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    """
    Only load if the pygerduty module is available in __salt__
    """
    return (
        "pagerduty_escalation_policy"
        if "pagerduty_util.get_resource" in __salt__
        else False
    )


def present(profile="pagerduty", subdomain=None, api_key=None, **kwargs):
    """
    Ensure that a pagerduty escalation policy exists.  Will create or update as needed.

    This method accepts as args everything defined in
    https://developer.pagerduty.com/documentation/rest/escalation_policies/create.
    In addition, user and schedule id's will be translated from name (or email address)
    into PagerDuty unique ids.  For example:

    .. code-block:: yaml

    pagerduty_escalation_policy.present:
        - name: bruce test escalation policy
        - escalation_rules:
            - targets:
                - type: schedule
                  id: 'bruce test schedule level1'
                - type: user
                  id: 'Bruce Sherrod'

    In this example, 'Bruce Sherrod' will be looked up and replaced with the
    PagerDuty id (usually a 7 digit all-caps string, e.g. PX6GQL7)

    """
    # for convenience, we accept id, name, or email for users
    # and we accept the id or name for schedules
    for escalation_rule in kwargs["escalation_rules"]:
        for target in escalation_rule["targets"]:
            target_id = None
            if target["type"] == "user":
                user = __salt__["pagerduty_util.get_resource"](
                    "users",
                    target["id"],
                    ["email", "name", "id"],
                    profile=profile,
                    subdomain=subdomain,
                    api_key=api_key,
                )
                if user:
                    target_id = user["id"]
            elif target["type"] == "schedule":
                schedule = __salt__["pagerduty_util.get_resource"](
                    "schedules",
                    target["id"],
                    ["name", "id"],
                    profile=profile,
                    subdomain=subdomain,
                    api_key=api_key,
                )
                if schedule:
                    target_id = schedule["schedule"]["id"]
            if target_id is None:
                raise Exception("unidentified target: {0}".format(target))
            target["id"] = target_id

    r = __salt__["pagerduty_util.resource_present"](
        "escalation_policies",
        ["name", "id"],
        _diff,
        profile,
        subdomain,
        api_key,
        **kwargs
    )
    return r


def absent(profile="pagerduty", subdomain=None, api_key=None, **kwargs):
    """
    Ensure that a PagerDuty escalation policy does not exist.
    Accepts all the arguments that pagerduty_escalation_policy.present accepts;
    but ignores all arguments except the name.

    Name can be the escalation policy id or the escalation policy name.
    """
    r = __salt__["pagerduty_util.resource_absent"](
        "escalation_policies", ["name", "id"], profile, subdomain, api_key, **kwargs
    )
    return r


def _diff(state_data, resource_object):
    """helper method to compare salt state info with the PagerDuty API json structure,
    and determine if we need to update.

    returns the dict to pass to the PD API to perform the update, or empty dict if no update.
    """
    objects_differ = None

    for k, v in state_data.items():
        if k == "escalation_rules":
            v = _escalation_rules_to_string(v)
            resource_value = _escalation_rules_to_string(resource_object[k])
        else:
            if k not in resource_object.keys():
                objects_differ = True
            else:
                resource_value = resource_object[k]
        if v != resource_value:
            objects_differ = "{0} {1} {2}".format(k, v, resource_value)
            break

    if objects_differ:
        return state_data
    else:
        return {}


def _escalation_rules_to_string(escalation_rules):
    "convert escalation_rules dict to a string for comparison"
    result = ""
    for rule in escalation_rules:
        result += "escalation_delay_in_minutes: {0} ".format(
            rule["escalation_delay_in_minutes"]
        )
        for target in rule["targets"]:
            result += "{0}:{1} ".format(target["type"], target["id"])
    return result

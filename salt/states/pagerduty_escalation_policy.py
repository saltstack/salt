# -*- coding: utf-8 -*-
'''

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
                      id: "bruce test schedule level1"
                    - type: user
                      id: "Bruce Sherrod"
                  escalation_delay_in_minutes: 15
                - targets:
                    - type: schedule
                      id: "bruce test schedule level2"
                  escalation_delay_in_minutes: 15
                - targets:
                    - type: user
                      id: "Bruce TestUser1"
                    - type: user
                      id: "Bruce TestUser2"
                    - type: user
                      id: "Bruce TestUser3"
                    - type: user
                      id:  "bruce+test4@lyft.com"
                  escalation_delay_in_minutes: 15
'''


def __virtual__():
    '''
    Only load if the pygerduty module is available in __salt__
    '''
    return 'pagerduty_escalation_policy' if 'pagerduty_util.get_resource' in __salt__ else False


def present(profile="pagerduty", subdomain=None, api_key=None, **kwargs):
    # for convenience, we accept id, name, or email for users
    # and we accept the id or name for schedules
    for escalation_rule in kwargs["escalation_rules"]:
        for target in escalation_rule["targets"]:
            target_id = None
            if target["type"] == "user":
                user = __salt__['pagerduty_util.get_resource']("users",
                                                               target["id"],
                                                               ["email", "name", "id"],
                                                               profile=profile,
                                                               subdomain=subdomain,
                                                               api_key=api_key)
                if user:
                    target_id = user["id"]
            elif target["type"] == "schedule":
                schedule = __salt__['pagerduty_util.get_resource']("schedules",
                                                                   target["id"],
                                                                   ["name", "id"],
                                                                   profile=profile,
                                                                   subdomain=subdomain,
                                                                   api_key=api_key)
                if schedule:
                    target_id = schedule["schedule"]["id"]
            if target_id is None:
                raise "unidentified target: %s" % str(target)
            target["id"] = target_id

    r = __salt__['pagerduty_util.resource_present']("escalation_policies",
                                                    ["name", "id"],
                                                    _diff,
                                                    profile,
                                                    subdomain,
                                                    api_key,
                                                    **kwargs)
    return r


def absent(profile="pagerduty", subdomain=None, api_key=None, **kwargs):
    r = __salt__['pagerduty_util.resource_absent']("escalation_policies",
                                                   ["name", "id"],
                                                   profile,
                                                   subdomain,
                                                   api_key,
                                                   **kwargs)
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
            resource_value = resource_object[k]
        if v != resource_value:
            objects_differ = "%s %s %s" % (k, v, resource_value)
            break

    if objects_differ:
        return state_data
    else:
        return {}


def _escalation_rules_to_string(escalation_rules):
    "convert escalation_rules dict to a string for comparison"
    result = ""
    for rule in escalation_rules:
        result += "escalation_delay_in_minutes: %s " % rule["escalation_delay_in_minutes"]
        for target in rule["targets"]:
            result += "%s:%s " % (target["type"], target["id"])
    return result

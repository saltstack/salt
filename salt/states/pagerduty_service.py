# -*- coding: utf-8 -*-
"""
Manage PagerDuty services

Escalation policies can be referenced by pagerduty ID or by namea.

For example:

.. code-block:: yaml

    ensure test service
        pagerduty_service.present:
            - name: 'my service'
            - escalation_policy_id: 'my escalation policy'
            - type: nagios

"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    """
    Only load if the pygerduty module is available in __salt__
    """
    return "pagerduty_service" if "pagerduty_util.get_resource" in __salt__ else False


def present(profile="pagerduty", subdomain=None, api_key=None, **kwargs):
    """
    Ensure pagerduty service exists.
    This method accepts as arguments everything defined in
    https://developer.pagerduty.com/documentation/rest/services/create

    Note that many arguments are mutually exclusive, depending on the "type" argument.

    Examples:

    .. code-block:: yaml

        # create a PagerDuty email service at test-email@DOMAIN.pagerduty.com
        ensure generic email service exists:
            pagerduty_service.present:
                - name: my email service
                - service:
                    description: "email service controlled by salt"
                    escalation_policy_id: "my escalation policy"
                    type: "generic_email"
                    service_key: "test-email"

    .. code-block:: yaml

        # create a pagerduty service using cloudwatch integration
        ensure my cloudwatch service exists:
            pagerduty_service.present:
                - name: my cloudwatch service
                - service:
                    escalation_policy_id: "my escalation policy"
                    type: aws_cloudwatch
                    description: "my cloudwatch service controlled by salt"

    """
    # TODO: aws_cloudwatch type should be integrated with boto_sns
    # for convenience, we accept id, name, or email for users
    # and we accept the id or name for schedules
    kwargs["service"]["name"] = kwargs["name"]  # make args mirror PD API structure
    escalation_policy_id = kwargs["service"]["escalation_policy_id"]
    escalation_policy = __salt__["pagerduty_util.get_resource"](
        "escalation_policies",
        escalation_policy_id,
        ["name", "id"],
        profile=profile,
        subdomain=subdomain,
        api_key=api_key,
    )
    if escalation_policy:
        kwargs["service"]["escalation_policy_id"] = escalation_policy["id"]
    r = __salt__["pagerduty_util.resource_present"](
        "services", ["name", "id"], _diff, profile, subdomain, api_key, **kwargs
    )
    return r


def absent(profile="pagerduty", subdomain=None, api_key=None, **kwargs):
    """
    Ensure a pagerduty service does not exist.
    Name can be the service name or pagerduty service id.
    """
    r = __salt__["pagerduty_util.resource_absent"](
        "services", ["name", "id"], profile, subdomain, api_key, **kwargs
    )
    return r


def _diff(state_data, resource_object):
    """helper method to compare salt state info with the PagerDuty API json structure,
    and determine if we need to update.

    returns the dict to pass to the PD API to perform the update, or empty dict if no update.
    """
    objects_differ = None

    for k, v in state_data["service"].items():
        if k == "escalation_policy_id":
            resource_value = resource_object["escalation_policy"]["id"]
        elif k == "service_key":
            # service_key on create must 'foo' but the GET will return 'foo@bar.pagerduty.com'
            resource_value = resource_object["service_key"]
            if "@" in resource_value:
                resource_value = resource_value[0 : resource_value.find("@")]
        else:
            resource_value = resource_object[k]
        if v != resource_value:
            objects_differ = "{0} {1} {2}".format(k, v, resource_value)
            break

    if objects_differ:
        return state_data
    else:
        return {}

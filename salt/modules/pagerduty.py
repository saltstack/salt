"""
Module for Firing Events via PagerDuty

.. versionadded:: 2014.1.0

:configuration: This module can be used by specifying the name of a
    configuration profile in the minion config, minion pillar, or master
    config.

    For example:

    .. code-block:: yaml

        my-pagerduty-account:
            pagerduty.api_key: F3Rbyjbve43rfFWf2214
            pagerduty.subdomain: mysubdomain
"""

import salt.utils.functools
import salt.utils.json
import salt.utils.pagerduty


def __virtual__():
    """
    No dependencies outside of what Salt itself requires
    """
    return True


def list_services(profile=None, api_key=None):
    """
    List services belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.list_services my-pagerduty-account
    """
    return salt.utils.pagerduty.list_items(
        "services", "name", __salt__["config.option"](profile), api_key, opts=__opts__
    )


def list_incidents(profile=None, api_key=None):
    """
    List incidents belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.list_incidents my-pagerduty-account
    """
    return salt.utils.pagerduty.list_items(
        "incidents", "id", __salt__["config.option"](profile), api_key, opts=__opts__
    )


def list_users(profile=None, api_key=None):
    """
    List users belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.list_users my-pagerduty-account
    """
    return salt.utils.pagerduty.list_items(
        "users", "id", __salt__["config.option"](profile), api_key, opts=__opts__
    )


def list_schedules(profile=None, api_key=None):
    """
    List schedules belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.list_schedules my-pagerduty-account
    """
    return salt.utils.pagerduty.list_items(
        "schedules", "id", __salt__["config.option"](profile), api_key, opts=__opts__
    )


def list_windows(profile=None, api_key=None):
    """
    List maintenance windows belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.list_windows my-pagerduty-account
        salt myminion pagerduty.list_maintenance_windows my-pagerduty-account
    """
    return salt.utils.pagerduty.list_items(
        "maintenance_windows",
        "id",
        __salt__["config.option"](profile),
        api_key,
        opts=__opts__,
    )


# The long version, added for consistency
list_maintenance_windows = salt.utils.functools.alias_function(
    list_windows, "list_maintenance_windows"
)


def list_policies(profile=None, api_key=None):
    """
    List escalation policies belonging to this account

    CLI Example:

    .. code-block:: bash

        salt myminion pagerduty.list_policies my-pagerduty-account
        salt myminion pagerduty.list_escalation_policies my-pagerduty-account
    """
    return salt.utils.pagerduty.list_items(
        "escalation_policies",
        "id",
        __salt__["config.option"](profile),
        api_key,
        opts=__opts__,
    )


# The long version, added for consistency
list_escalation_policies = salt.utils.functools.alias_function(
    list_policies, "list_escalation_policies"
)


def create_event(
    service_key=None, description=None, details=None, incident_key=None, profile=None
):
    """
    Create an event in PagerDuty. Designed for use in states.

    CLI Example:

    .. code-block:: yaml

        salt myminion pagerduty.create_event <service_key> <description> <details> \
        profile=my-pagerduty-account

    The following parameters are required:

    service_key
        This key can be found by using pagerduty.list_services.

    description
        This is a short description of the event.

    details
        This can be a more detailed description of the event.

    profile
        This refers to the configuration profile to use to connect to the
        PagerDuty service.
    """
    trigger_url = "https://events.pagerduty.com/generic/2010-04-15/create_event.json"

    if isinstance(details, str):
        details = salt.utils.yaml.safe_load(details)
        if isinstance(details, str):
            details = {"details": details}

    ret = salt.utils.json.loads(
        salt.utils.pagerduty.query(
            method="POST",
            profile_dict=__salt__["config.option"](profile),
            api_key=service_key,
            data={
                "service_key": service_key,
                "incident_key": incident_key,
                "event_type": "trigger",
                "description": description,
                "details": details,
            },
            url=trigger_url,
            opts=__opts__,
        )
    )
    return ret

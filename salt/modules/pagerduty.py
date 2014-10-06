# -*- coding: utf-8 -*-
'''
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
'''

# Import python libs
import yaml
import json

# Import salt libs
import salt.utils.pagerduty
from salt._compat import string_types


def __virtual__():
    '''
    No dependencies outside of what Salt itself requires
    '''
    return True


def list_services(profile=None, api_key=None):
    '''
    List services belonging to this account

    CLI Example:

        pagerduty.list_services my-pagerduty-account
    '''
    return salt.utils.pagerduty.list_items(
        'services', 'name', profile, api_key, opts=__opts__
    )


def list_incidents(profile=None, api_key=None):
    '''
    List services belonging to this account

    CLI Example:

        pagerduty.list_incidents my-pagerduty-account
    '''
    return salt.utils.pagerduty.list_items(
        'incidents', 'id', profile, api_key, opts=__opts__
    )


def create_event(service_key=None, description=None, details=None,
                 incident_key=None, profile=None):
    '''
    Create an event in PagerDuty. Designed for use in states.

    CLI Example:

        pagerduty.create_event <service_key> <description> <details> \
            profile=my-pagerduty-account
:
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
    '''
    trigger_url = 'https://events.pagerduty.com/generic/2010-04-15/create_event.json'

    if isinstance(details, string_types):
        details = yaml.safe_load(details)
        if isinstance(details, string_types):
            details = {'details': details}

    ret = json.loads(salt.utils.pagerduty.query(
        method='POST',
        profile=profile,
        api_key=service_key,
        data={
            'service_key': service_key,
            'incident_key': incident_key,
            'event_type': 'trigger',
            'description': description,
            'details': details,
        },
        url=trigger_url,
        opts=__opts__
    ))
    return ret

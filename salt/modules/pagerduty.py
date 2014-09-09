# -*- coding: utf-8 -*-
'''
Module for Firing Events via PagerDuty

.. versionadded:: 2014.1.0

:depends:   - pygerduty python module
:configuration: This module can be used by either passing a jid and password
    directly to send_message, or by specifying the name of a configuration
    profile in the minion config, minion pillar, or master config.

    For example:

    .. code-block:: yaml

        my-pagerduty-account:
            pagerduty.api_key: F3Rbyjbve43rfFWf2214
            pagerduty.subdomain: mysubdomain
'''

HAS_LIBS = False
try:
    import pygerduty
    HAS_LIBS = True
except ImportError:
    pass

__virtualname__ = 'pagerduty'


def __virtual__():
    '''
    Only load this module if pygerduty is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return False


def _get_pager(profile):
    '''
    Return the pagerduty connection
    '''
    creds = __salt__['config.option'](profile)

    pager = pygerduty.PagerDuty(
        creds.get('pagerduty.subdomain'),
        creds.get('pagerduty.api_key'),
    )

    return pager


def list_services(profile):
    '''
    List services belonging to this account

    CLI Example:

        pagerduty.list_services my-pagerduty-account
    '''
    pager = _get_pager(profile)
    ret = {}
    for service in pager.services.list():
        ret[service.name] = {
            'acknowledgement_timeout': service.acknowledgement_timeout,
            'auto_resolve_timeout': service.auto_resolve_timeout,
            'created_at': service.created_at,
            'deleted_at': service.deleted_at,
            'description': service.description,
            'email_filter_mode': service.email_filter_mode,
            'email_incident_creation': service.email_incident_creation,
            'id': service.id,
            'incident_counts': {
                'acknowledged': service.incident_counts.acknowledged,
                'resolved': service.incident_counts.resolved,
                'total': service.incident_counts.total,
                'triggered': service.incident_counts.triggered,
            },
            'last_incident_timestamp': service.last_incident_timestamp,
            'name': service.name,
            'service_key': service.service_key,
            'service_url': service.service_url,
            'status': service.status,
            'type': service.type,
        }
    return ret


def list_incidents(profile):
    '''
    List services belonging to this account

    CLI Example:

        pagerduty.list_incidents my-pagerduty-account
    '''
    pager = _get_pager(profile)
    ret = {}
    for incident in pager.incidents.list():
        ret[incident.id] = {
            'status': incident.status,
            'service': {
                'deleted_at': incident.service.deleted_at,
                'id': incident.service.id,
                'name': incident.service.name,
                'html_url': incident.service.html_url,
            },
            'trigger_type': incident.trigger_type,
            'escalation_policy': {
                'id': incident.escalation_policy.id,
                'name': incident.escalation_policy.name,
            },
            'assigned_to_user': incident.assigned_to_user,
            'html_url': incident.html_url,
            'last_status_change_on': incident.last_status_change_on,
            'last_status_change_by': {},
            'incident_key': incident.incident_key,
            'created_on': incident.created_on,
            'number_of_escalations': incident.number_of_escalations,
            'incident_number': incident.incident_number,
            'resolved_by_user': {},
            'trigger_details_html_url': incident.trigger_details_html_url,
            'id': incident.id,
            'trigger_summary_data': {
                'subject': None,
            },
        }
        if hasattr(incident.trigger_summary_data, 'subject'):
            ret[incident.id]['trigger_summary_data']['subject'] = \
                incident.trigger_summary_data.subject
        if hasattr(incident, 'resolved_by_user'):
            ret[incident.id]['resolved_by_user'] = {
                'id': incident.resolved_by_user.id,
                'name': incident.resolved_by_user.name,
                'html_url': incident.resolved_by_user.html_url,
                'email': incident.resolved_by_user.email,
            }
        if hasattr(incident.last_status_change_by, 'id'):
            ret[incident.id]['last_status_change_by'] = {
                'id': incident.last_status_change_by.id,
                'name': incident.last_status_change_by.name,
                'html_url': incident.last_status_change_by.html_url,
                'email': incident.last_status_change_by.email,
            }
    return ret


def create_event(service_key, description, details, incident_key=None,
                 profile=None):
    '''
    Create an event in PagerDuty. Designed for use in states.

    CLI Example:

        pagerduty.create_event <service_key> <description> <details> \
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
    '''
    pager = _get_pager(profile)
    event = pager.create_event(
        service_key=service_key,
        description=description,
        details=details,
        event_type='trigger',
        incident_key=incident_key,
    )
    return {'incident_key': str(event)}

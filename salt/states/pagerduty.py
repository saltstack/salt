# -*- coding: utf-8 -*-
'''
Create an Event in PagerDuty
============================

.. versionadded:: 2014.1.0

This state is useful for creating events on the PagerDuty service during state
runs.

.. code-block:: yaml

    server-warning-message:
      pagerduty.create_event:
        - name: 'This is a server warning message'
        - details: 'This is a much more detailed message'
        - service_key: 9abcd123456789efabcde362783cdbaf
        - profile: my-pagerduty-account
'''


def __virtual__():
    '''
    Only load if the pygerduty module is available in __salt__
    '''
    return 'pagerduty' if 'pagerduty.create_event' in __salt__ else False


def create_event(name, details, service_key, profile):
    '''
    Create an event on the PagerDuty service

    .. code-block:: yaml

        server-warning-message:
          pagerduty.create_event:
            - name: 'This is a server warning message'
            - details: 'This is a much more detailed message'
            - service_key: 9abcd123456789efabcde362783cdbaf
            - profile: my-pagerduty-account

    The following parameters are required:

    name
        This is a short description of the event.

    details
        This can be a more detailed description of the event.

    service_key
        This key can be found by using pagerduty.list_services.

    profile
        This refers to the configuration profile to use to connect to the
        PagerDuty service.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if __opts__['test']:
        ret['comment'] = 'Need to create event: {0}'.format(name)
        return ret
    __salt__['pagerduty.create_event'](
        description=name,
        details=details,
        service_key=service_key,
        profile=profile,
    )
    ret['result'] = True
    ret['comment'] = 'Created event: {0}'.format(name)
    return ret

# -*- coding: utf-8 -*-
'''
An execution module that interacts with the Datadog API

Common parameters:

scope
    The scope of the request

api_key
    The datadog API key

app_key
    The datadog application key

Full argument reference is available on the Datadog API reference page
https://docs.datadoghq.com/api/
'''

# Import salt libs
from __future__ import absolute_import
from salt.exceptions import SaltInvocationError

# Import third party libs
import requests
HAS_DATADOG = True
try:
    import datadog
except ImportError:
    HAS_DATADOG = False

# Define the module's virtual name
__virtualname__ = 'datadog'


def __virtual__():
    if HAS_DATADOG:
        return 'datadog'
    else:
        message = 'Unable to import the python datadog module. Is it installed?'
        return False, message


def _initialize_connection(api_key, app_key):
    '''
    Initialize Datadog connection
    '''
    options = {
        'api_key': api_key,
        'app_key': app_key
    }
    datadog.initialize(**options)


def schedule_downtime(scope, api_key=None, app_key=None, monitor_id=None,
                      start=None, end=None, message=None, recurrence=None,
                      timezone=None, test=False):
    '''
    Schedule downtime for a scope of monitors.

    monitor_id
        The ID of the monitor
    start
        Start time in seconds since the epoch
    end
        End time in seconds since the epoch
    message
        A message to send in a notification for this downtime
    recurrence
        Repeat this downtime periodically
    timezone
        Specify the timezone

    CLI Example:

    .. code-block:: bash

        salt-call datadog.schedule_downtime 'host:app2' stop=$(date --date='30
        minutes' +%s) app_key=<app_key> api_key=<api_key>
    '''
    ret = {'result': False,
           'response': None,
           'comment': ''}

    if api_key is None:
        raise SaltInvocationError('api_key must be specified')
    if app_key is None:
        raise SaltInvocationError('app_key must be specified')
    if test is True:
        ret['result'] = True
        ret['comment'] = 'A schedule downtime API call would have been made.'
        return ret
    _initialize_connection(api_key, app_key)

    # Schedule downtime
    try:
        response = datadog.api.Downtime.create(scope=scope,
                                               monitor_id=monitor_id,
                                               start=start,
                                               end=end,
                                               message=message,
                                               recurrence=recurrence,
                                               timezone=timezone)
    except ValueError:
        comment = ('Unexpected exception in Datadog Schedule Downtime API '
                   'call. Are your keys correct?')
        ret['comment'] = comment
        return ret

    ret['response'] = response
    if 'active' in response.keys():
        ret['result'] = True
        ret['comment'] = 'Successfully scheduled downtime'
    return ret


def cancel_downtime(api_key=None, app_key=None, scope=None, id=None):
    '''
    Cancel a downtime by id or by scope.

    Either scope or id is required.

    id
        The ID of the downtime

    CLI Example:

    .. code-block:: bash

        salt-call datadog.cancel_downtime scope='host:app01' api_key=<api_key>
        app_key=<app_key>`
    '''
    if api_key is None:
        raise SaltInvocationError('api_key must be specified')
    if app_key is None:
        raise SaltInvocationError('app_key must be specified')
    _initialize_connection(api_key, app_key)

    ret = {'result': False,
           'response': None,
           'comment': ''}
    if id:
        response = datadog.api.Downtime.delete(id)
        ret['response'] = response
        if not response:  # Then call has succeeded
            ret['result'] = True
            ret['comment'] = 'Successfully cancelled downtime'
        return ret
    elif scope:
        params = {
            'api_key': api_key,
            'application_key': app_key,
            'scope': scope
        }
        response = requests.post(
                    'https://app.datadoghq.com/api/v1/downtime/cancel/by_scope',
                    params=params
                    )
        if response.status_code == 200:
            ret['result'] = True
            ret['response'] = response.json()
            ret['comment'] = 'Successfully cancelled downtime'
        else:
            ret['response'] = response.text
            ret['comment'] = 'Status Code: {}'.format(response.status_code)
        return ret
    else:
        raise SaltInvocationError('One of id or scope must be specified')

    return ret

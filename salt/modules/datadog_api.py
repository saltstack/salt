# -*- coding: utf-8 -*-
'''
An execution module that interacts with the Datadog API

The following parameters are required for all functions.

api_key
    The datadog API key

app_key
    The datadog application key

Full argument reference is available on the Datadog API reference page
https://docs.datadoghq.com/api/
'''

# Import salt libs
from __future__ import absolute_import, print_function, unicode_literals
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
    if api_key is None:
        raise SaltInvocationError('api_key must be specified')
    if app_key is None:
        raise SaltInvocationError('app_key must be specified')
    options = {
        'api_key': api_key,
        'app_key': app_key
    }
    datadog.initialize(**options)


def schedule_downtime(scope,
                      api_key=None,
                      app_key=None,
                      monitor_id=None,
                      start=None,
                      end=None,
                      message=None,
                      recurrence=None,
                      timezone=None,
                      test=False):
    '''
    Schedule downtime for a scope of monitors.

    CLI Example:

    .. code-block:: bash

        salt-call datadog.schedule_downtime 'host:app2' \\
                                            stop=$(date --date='30 minutes' +%s) \\
                                            app_key='0123456789' \\
                                            api_key='9876543210'

    Optional arguments

    :param monitor_id:      The ID of the monitor
    :param start:           Start time in seconds since the epoch
    :param end:             End time in seconds since the epoch
    :param message:         A message to send in a notification for this downtime
    :param recurrence:      Repeat this downtime periodically
    :param timezone:        Specify the timezone
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


def cancel_downtime(api_key=None,
                    app_key=None,
                    scope=None,
                    id=None):
    '''
    Cancel a downtime by id or by scope.

    CLI Example:

    .. code-block:: bash

        salt-call datadog.cancel_downtime scope='host:app01' \\
                                          api_key='0123456789' \\
                                          app_key='9876543210'`

    Arguments - Either scope or id is required.

    :param id:      The downtime ID
    :param scope:   The downtime scope
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


def post_event(api_key=None,
               app_key=None,
               title=None,
               text=None,
               date_happened=None,
               priority=None,
               host=None,
               tags=None,
               alert_type=None,
               aggregation_key=None,
               source_type_name=None):
    '''
    Post an event to the Datadog stream.

    CLI Example

    .. code-block:: bash

        salt-call datadog.post_event api_key='0123456789' \\
                                     app_key='9876543210' \\
                                     title='Salt Highstate' \\
                                     text="Salt highstate was run on $(salt-call grains.get id)" \\
                                     tags='["service:salt", "event:highstate"]'

    Required arguments

    :param title:   The event title. Limited to 100 characters.
    :param text:    The body of the event. Limited to 4000 characters. The text
                    supports markdown.

    Optional arguments

    :param date_happened:       POSIX timestamp of the event.
    :param priority:            The priority of the event ('normal' or 'low').
    :param host:                Host name to associate with the event.
    :param tags:                A list of tags to apply to the event.
    :param alert_type:          "error", "warning", "info" or "success".
    :param aggregation_key:     An arbitrary string to use for aggregation,
                                max length of 100 characters.
    :param source_type_name:    The type of event being posted.
    '''
    _initialize_connection(api_key, app_key)
    if title is None:
        raise SaltInvocationError('title must be specified')
    if text is None:
        raise SaltInvocationError('text must be specified')
    if alert_type not in [None, 'error', 'warning', 'info', 'success']:
        # Datadog only supports these alert types but the API doesn't return an
        # error for an incorrect alert_type, so we can do it here for now.
        # https://github.com/DataDog/datadogpy/issues/215
        message = ('alert_type must be one of "error", "warning", "info", or '
                   '"success"')
        raise SaltInvocationError(message)

    ret = {'result': False,
           'response': None,
           'comment': ''}

    try:
        response = datadog.api.Event.create(title=title,
                                            text=text,
                                            date_happened=date_happened,
                                            priority=priority,
                                            host=host,
                                            tags=tags,
                                            alert_type=alert_type,
                                            aggregation_key=aggregation_key,
                                            source_type_name=source_type_name
                                           )
    except ValueError:
        comment = ('Unexpected exception in Datadog Post Event API '
                   'call. Are your keys correct?')
        ret['comment'] = comment
        return ret

    ret['response'] = response
    if 'status' in response.keys():
        ret['result'] = True
        ret['comment'] = 'Successfully sent event'
    else:
        ret['comment'] = 'Error in posting event.'
    return ret

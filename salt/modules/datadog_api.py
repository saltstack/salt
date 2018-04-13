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
from salt.ext import six

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


def get_all_monitors(name=None,
                     group_states=None,
                     tags=None,
                     monitor_tags=None,
                     with_downtimes=None,
                     api_key=None,
                     app_key=None):
    '''
    Get all monitors in Datadog.

    CLI Example

    .. code-block:: bash

        salt-call datadog.get_all_monitors api_key='0123456789' \\
                                           app_key='9876543210'

    Optional arguments

    :param name:             Name of monitor.
    :param group_states:     If this argument is set, the returned data will
                             include additional information about the group
                             states. Choose one or more from 'all', 'alert'
                             'warn' or 'no data'.
    :param tags:             A comma separated list indicating what tags
                             should be used to filter the list of monitors.
    :param monitor_tags:     A comma separated list indicating what service
                             and/or custom tags should be used to filter the
                             list of monitors.
    :param with_downtimes:   If this argument is set to true, then the returned
                             data includes current downtimes for each monitor.
    '''
    _initialize_connection(api_key, app_key)

    ret = {'result': False,
           'response': None,
           'comment': ''}

    try:
        response = datadog.api.Monitor.get_all(name=name,
                                               group_states=group_states,
                                               tags=tags,
                                               monitor_tags=monitor_tags,
                                               with_downtimes=with_downtimes)
    except ValueError:
        comment = ('Unexpected exception in Datadog Get All Monitors API '
                   'call. Are your keys correct?')
        ret['comment'] = comment
        return ret

    ret['response'] = response
    if isinstance(response, list):
        no_monitors = len(response)
        ret['result'] = True
        ret['comment'] = str(no_monitors) + ' monitors found'
    else:
        ret['comment'] = 'Error in finding monitors.'

    return ret


def get_monitor(id, group_states=None, api_key=None, app_key=None):
    '''
    Get a monitors details based on it's id.

    CLI Example

    .. code-block:: bash

        salt-call datadog.get_monitor id='1234567' \\
                                      api_key='0123456789' \\
                                      app_key='9876543210'

    Required arguments

    :param id:    The id of the monitor
    '''
    _initialize_connection(api_key, app_key)

    ret = {'result': False,
           'response': None,
           'comment': ''}

    try:
        response = datadog.api.Monitor.get(id=id, group_states=group_states)
    except ValueError:
        comment = ('Unexpected exception in Datadog Get Monitor API '
                   'call. Are your keys correct?')
        ret['comment'] = comment
        return ret

    ret['response'] = response
    if 'id' in response.keys():
        ret['result'] = True
        ret['comment'] = 'Successfully found monitor'
    else:
        ret['comment'] = 'Error in finding monitor.'

    return ret


def _get_options(**kwargs):
    '''
    Return dict of options.
    '''
    options = {}
    for key, value in six.iteritems(kwargs):
        if value:
            options[key] = value

    return options


def create_monitor(name,
                   type,
                   query,
                   api_key=None,
                   app_key=None,
                   message=None,
                   tags=None,
                   silenced=None,
                   notify_no_data=None,
                   new_host_delay=None,
                   no_data_timeframe=None,
                   timeout_h=None,
                   require_full_window=None,
                   renotify_interval=None,
                   escalation_message=None,
                   notify_audit=None,
                   locked=None,
                   include_tags=None,
                   thresholds=None,
                   evaluation_delay=None):
    '''
    Create a monitor in Datadog.

    CLI Example

    .. code-block:: bash

        salt-call datadog.create_monitor name='check datadog agent up' \\
                                         type='service check' \\
                                         query='"datadog.agent.up".over("*").by("host").last(2).count_by_status()' \\
                                         api_key='0123456789' \\
                                         app_key='9876543210' \\

    Required arguments

    :param name:                  The name of the alert
    :param type:                  The type of the monitor
    :param query:                 The query defines when a monitor will
                                  trigger.

    Optional arguments

    :param message:               A message to include with notifications for
                                  the monitor.
    :param tags:                  A list of tags to associate with the monitor
    :param silenced:              Dictionary of scopes to timestamps or None.
                                  Scopes will be muted until given timestamp
    :param notify_no_data         A boolean indicating whether this monitor
                                  will notify when data stops reporting.
    :param new_host_delay         Time in seconds to allow a host to boot
                                  before evaulating monitor results.
    :param no_data_timeframe      The number of minutes before a monitor will
                                  notify when data stops reporting.
    :param timeout_h              The number of hours of the monitor not
                                  reporting data before it will automatically
                                  resolve from a triggered state.
    :param require_full_window    A boolean indicating whether this monitor
                                  needs a full window of data before it's
                                  evaluated.
    :param renotify_interval      The number of minutes after the last
                                  notification before a monitor will
                                  re-notify on the current status.
    :param escalation_message     A message to include with a re-notification
    :param notify_audit           A boolean indicating whether tagged users
                                  will be notified on changes to this monitor.
    :param locked                 A boolean indicating whether changes to to
                                  this monitor should be restricted to the
                                  creator or admins.
    :param include_tags           A boolean indicating whether notifications
                                  from this monitor will automatically insert
                                  its triggering tags into the title.
    :param thresholds             A disctionary of thresholds by threshold
                                  type.
    :param evaluation_delay       Time (in seconds) to delay evaluation, as a
                                  non-negative integer.

    '''
    _initialize_connection(api_key, app_key)

    ret = {'result': False,
           'response': None,
           'comment': ''}

    options = _get_options(silenced=silenced,
                           notify_no_data=notify_no_data,
                           new_host_delay=new_host_delay,
                           no_data_timeframe=no_data_timeframe,
                           timeout_h=timeout_h,
                           require_full_window=require_full_window,
                           renotify_interval=renotify_interval,
                           escalation_message=escalation_message,
                           notify_audit=notify_audit,
                           locked=locked,
                           include_tags=include_tags,
                           thresholds=thresholds,
                           evaluation_delay=evaluation_delay)

    try:
        response = datadog.api.Monitor.create(name=name,
                                              type=type,
                                              query=query,
                                              message=message,
                                              tags=tags,
                                              options=options)
    except ValueError:
        comment = ('Unexpected exception in Datadog Create Monitor API '
                   'call. Are your keys correct?')
        ret['comment'] = comment
        return ret

    ret['response'] = response
    if 'id' in response.keys():
        ret['result'] = True
        ret['comment'] = 'Successfully created monitor'
    else:
        ret['comment'] = 'Error in creating monitor.'

    return ret


def update_monitor(name,
                   id,
                   query,
                   api_key=None,
                   app_key=None,
                   message=None,
                   tags=None,
                   silenced=None,
                   notify_no_data=None,
                   new_host_delay=None,
                   no_data_timeframe=None,
                   timeout_h=None,
                   require_full_window=None,
                   renotify_interval=None,
                   escalation_message=None,
                   notify_audit=None,
                   locked=None,
                   include_tags=None,
                   thresholds=None,
                   evaluation_delay=None):
    '''
    Update a monitor in Datadog.

    CLI Example

    .. code-block:: bash

        salt-call datadog.update_monitor name='check datadog agent up' \\
                                         id='1234567' \\
                                         query='"datadog.agent.up".over("*").by("host").last(2).count_by_status()' \\
                                         api_key='0123456789' \\
                                         app_key='9876543210' \\

    Required arguments

    :param name:                  The name of the alert
    :param query:                 The query defines when a monitor will
                                  trigger.

    Optional arguments

    :param message:               A message to include with notifications for
                                  the monitor.
    :param tags:                  A list of tags to associate with the monitor
    :param silenced:              Dictionary of scopes to timestamps or None.
                                  Scopes will be muted until given timestamp
    :param notify_no_data         A boolean indicating whether this monitor
                                  will notify when data stops reporting.
    :param new_host_delay         Time in seconds to allow a host to boot
                                  before evaulating monitor results.
    :param no_data_timeframe      The number of minutes before a monitor will
                                  notify when data stops reporting.
    :param timeout_h              The number of hours of the monitor not
                                  reporting data before it will automatically
                                  resolve from a triggered state.
    :param require_full_window    A boolean indicating whether this monitor
                                  needs a full window of data before it's
                                  evaluated.
    :param renotify_interval      The number of minutes after the last
                                  notification before a monitor will
                                  re-notify on the current status.
    :param escalation_message     A message to include with a re-notification
    :param notify_audit           A boolean indicating whether tagged users
                                  will be notified on changes to this monitor.
    :param locked                 A boolean indicating whether changes to to
                                  this monitor should be restricted to the
                                  creator or admins.
    :param include_tags           A boolean indicating whether notifications
                                  from this monitor will automatically insert
                                  its triggering tags into the title.
    :param thresholds             A disctionary of thresholds by threshold
                                  type.
    :param evaluation_delay       Time (in seconds) to delay evaluation, as a
                                  non-negative integer.

    '''
    _initialize_connection(api_key, app_key)

    ret = {'result': False,
           'response': None,
           'comment': ''}

    options = _get_options(silenced=silenced,
                           notify_no_data=notify_no_data,
                           new_host_delay=new_host_delay,
                           no_data_timeframe=no_data_timeframe,
                           timeout_h=timeout_h,
                           require_full_window=require_full_window,
                           renotify_interval=renotify_interval,
                           escalation_message=escalation_message,
                           notify_audit=notify_audit,
                           locked=locked,
                           include_tags=include_tags,
                           thresholds=thresholds,
                           evaluation_delay=evaluation_delay)

    try:
        response = datadog.api.Monitor.update(name=name,
                                              id=id,
                                              query=query,
                                              message=message,
                                              tags=tags,
                                              options=options)
    except ValueError:
        comment = ('Unexpected exception in Datadog Update Monitor API '
                   'call. Are your keys correct?')
        ret['comment'] = comment
        return ret

    ret['response'] = response
    if 'id' in response.keys():
        ret['result'] = True
        ret['comment'] = 'Successfully updated monitor'
    else:
        ret['comment'] = 'Error in updating monitor.'

    return ret


def delete_monitor(id, api_key=None, app_key=None):
    '''
    Delete a monitor.

    CLI Example

    .. code-block:: bash

        salt-call datadog.delete_monitor id='1234567' \\
                                         api_key='0123456789' \\
                                         app_key='9876543210'

    Required arguments

    :param id:    The id of the monitor
    '''
    _initialize_connection(api_key, app_key)

    ret = {'result': False,
           'response': None,
           'comment': ''}

    try:
        response = datadog.api.Monitor.delete(id=id)
    except ValueError:
        comment = ('Unexpected exception in Datadog Delete Monitor API '
                   'call. Are your keys correct?')
        ret['comment'] = comment
        return ret

    ret['response'] = response
    if 'deleted_monitor_id' in response.keys():
        ret['result'] = True
        ret['comment'] = 'Successfully deleted monitor'
    else:
        ret['comment'] = 'Error in deleting monitor.'

    return ret

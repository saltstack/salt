# -*- coding: utf-8 -*-

# This module redefines built-in's 'id' and 'type' as Datadog's resource ID's
# types. Disabling invalid-name, because 'id' is too short.
# pylint: disable=redefined-builtin, invalid-name
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

# Import built-in libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import re
from functools import reduce

# Import salt libs
from salt.ext import six
from salt.ext.six import string_types
from salt.ext.six.moves import map
from salt.exceptions import SaltInvocationError

# Import third party libs
import requests
HAS_DATADOG = True
try:
    import datadog
except ImportError:
    HAS_DATADOG = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'datadog'


def __virtual__():
    if HAS_DATADOG:
        return 'datadog'
    message = 'Unable to import the python datadog module. Is it installed?'
    return False, message


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
    __utils__['datadog.initialize_connection'](api_key, app_key)

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
    __utils__['datadog.initialize_connection'](api_key, app_key)

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
    __utils__['datadog.initialize_connection'](api_key, app_key)
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
        response = datadog.api.Event.create(
            title=title,
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


def create_monitor(api_key=None,
                   app_key=None,
                   type=None,
                   query=None,
                   name=None,
                   message=None,
                   tags=None,
                   options=None):
    '''
    Create a datadog monitor

    Required arguments:

    :param query: The query which triggers the monitor
    :type query: str

    :param type: The type of the monitor
    :type type: str

    Optional arguments:

    :param name: The name of the monitor
    :type name: str

    :param message: The message sent when the monitor is triggered
    :type message: message

    :param tags: A list of tags to attach to the monitor
    :type tags: list

    :param options: An options dictionary
    :type options: dict

    CLI Example:

    .. code-block:: bash

        salt-call datadog.create_monitor \\
            query='avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100' \\
            app_key='0123456789' \\
            api_key='9876543210'
    '''
    __utils__['datadog.initialize_connection'](api_key, app_key)

    ret = {
        'result': False,
        'response': None,
        'comment': ''
    }

    if __opts__['test']:
        message = (
            'A datadog monitor create call would be called.'
        )
        ret['result'] = None
        ret['comment'] = message
        return ret

    if tags is None:
        tags = []
    if options is None:
        options = {}

    if type == 'composite':
        success, query = _generate_composite_query(query)
        if not success:
            ret['comment'] = query
            return ret

    res = datadog.api.Monitor.create(
        type=type,
        query=query,
        name=name,
        message=message,
        tags=tags,
        options=options
    )

    ret['response'] = res
    if 'errors' in res.keys():
        ret['comment'] = 'Failed to create monitor'
        return ret

    ret['result'] = True
    ret['comment'] = 'Successfully created monitor {}'.format(res['name'])

    return ret


def read_monitor(api_key=None,
                 app_key=None,
                 id=None,
                 name=None,
                 group_states=None,
                 tags=None,
                 monitor_tags=None,
                 with_downtimes=True):
    '''
    Get monitor details by name and filters or by id

    Optional arguments:

    :param id: A Datadog ID or list of IDs
    :type id: int/str/list

    :param name: A Datadog monitor name or list of names
    :type name: str/list

    :param group_states: Include additional information regarding group states
    :type group_states: str

    :param tags: A list of tags to filter by
    :type tags: list

    :param monitor_tags: A list of service or custom tags to filter by
    :type monitor_tags: list

    :param with_downtimes: Include current downtimes
    :type with_downtimes: bool

    CLI Example:

    .. code-block:: bash

        salt-call datadog.get_monitor id=4861948 \\
            app_key='0123456789' \\
            api_key='9876543210'

    Note:

    The tag filters act only on monitors specified by name.

    Note:

    If id is passed to this function, all other filter arguments will be ignored
    '''

    __utils__['datadog.initialize_connection'](api_key, app_key)

    ret = {
        'result': False,
        'response': None,
        'comment': ''
    }

    if __opts__['test']:
        message = (
            'A datadog monitor read call would be called for {}'
        )
        ret['result'] = None
        ret['comment'] = message.format(
            'ids {}'.format(id) if id is not None else 'names {}'.format(name)
        )
        return ret

    if tags is None:
        tags = []
    if monitor_tags is None:
        monitor_tags = []

    response = []
    if id is not None:
        ids = []
        if isinstance(id, list):
            ids += id
        else:
            ids += [id]

        for _id in ids:
            if _id:
                res = datadog.api.Monitor.get(
                    _id,
                    group_states=group_states
                )
                if 'errors' in res.keys():
                    ret['response'] = res
                    ret['comment'] = (
                        'An error occured when trying to read monitors.'
                    )
                    return ret
                else:
                    response += [res]
    elif name is not None:
        names = []
        if isinstance(name, list):
            names += name
        else:
            names += [name]

        for _name in names:
            res = __utils__['datadog.get_all_monitors'](
                name=_name,
                group_states=group_states,
                tags=tags,
                monitor_tags=monitor_tags,
                with_downtimes=with_downtimes
            )
            if not res['result']:
                ret['response'] = res['response']
                ret['comment'] = (
                    'An error occured when trying to read monitors.'
                )
                return ret
            else:
                response += res['response']
    else:  # Case for tag or monitor_tag searches
        res = __utils__['datadog.get_all_monitors'](
            group_states=group_states,
            tags=tags,
            monitor_tags=monitor_tags,
            with_downtimes=with_downtimes
        )
        if not res['result']:
            ret['response'] = res['response']
            ret['comment'] = (
                'An error occured when trying to read monitors.'
            )
            return ret
        else:
            response += res['response']

    ret['result'] = True
    ret['response'] = response
    return ret


def update_monitor(api_key=None,
                   app_key=None,
                   id=None,
                   name=None,
                   query=None,
                   message=None,
                   options=None,
                   tags=None):
    '''
    Modify a monitor by id or, if none is specified, then by name. If multiple
    monitors match the name given, this function will take action on the first.

    Optional arguments:

    :param id: The type of the monitor
    :type id: int

    :param name: The type of the monitor
    :type name: str

    :param query: The type of the monitor
    :type query: str

    :param message: The type of the monitor
    :type message: str

    :param tags: The type of the monitor
    :type tags: list

    :param options: The type of the monitor
    :type options: dict

    CLI Example:

    .. code-block:: bash

        salt-call datadog.update_monitor name='CPU on host0 - last hour' \\
            message='CPU has exceeded limit on host0' \\
            app_key='0123456789' \\
            api_key='9876543210'
    '''

    __utils__['datadog.initialize_connection'](api_key, app_key)

    ret = {
        'result': False,
        'response': None,
        'comment': ''
    }

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'A datadog monitor create call would be called.'
        return ret

    if options is None:
        options = {}
    if tags is None:
        tags = []
    if message is None:
        message = ''

    res = read_monitor(
        api_key=api_key,
        app_key=app_key,
        id=id,
        name=name
    )
    if not res['result']:
        ret['response'] = res['response']
        ret['comment'] = res['comment']
        return ret

    if not name:
        name = res['response'][0]['name']
    if not query:
        query = res['response'][0]['query']

    res = datadog.api.Monitor.update(
        res['response'][0]['id'],
        name=name,
        query=query,
        message=message,
        options=options,
        tags=tags
    )

    ret['response'] = res
    if 'errors' in res.keys():
        ret['comment'] = 'Update call failed.'
        return ret

    ret['result'] = True
    ret['comment'] = 'Update call returned successfully.'
    return ret


def delete_monitor(api_key=None,
                   app_key=None,
                   id=None,
                   name=None):
    '''
    Delete a monitor by ID or name

    .. warning::

    Datadog supports multiple monitors with the same name and different IDs. If
    passed a name, this module will delete all monitors with that name.

    Optional arguments:

    :param id:       (str/list) - A Datadog ID or list of IDs
    :type id:       (str/list) - A Datadog ID or list of IDs

    :param name:     (str/list) - A name or list of names
    :type name:     (str/list) - A name or list of names

    CLI Example:

    .. code-block:: bash

        salt-call datadog.delete_monitor name='CPU on host0 - last hour'\\
            app_key='0123456789' \\
            api_key='9876543210'
    '''

    __utils__['datadog.initialize_connection'](api_key, app_key)

    ret = {
        'result': False,
        'response': None,
        'comment': ''
    }

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'A datadog monitor delete call would be called.'
        return ret

    ids = []
    if isinstance(id, (int, string_types)):
        id = [id]
    if isinstance(id, list):
        ids += id
    if isinstance(name, string_types):
        name = [name]
    if isinstance(name, list):
        for _name in name:
            ids += __utils__['datadog.find_monitors_with_name'](
                api_key=api_key,
                app_key=app_key,
                name=_name
            )

    response = list(map(datadog.api.Monitor.delete, ids))
    intermediate = ['deleted_monitor_id' in res for res in response]
    reduced = reduce(lambda x, y: x and y, intermediate, True)

    ret['response'] = response
    if not reduced:
        ret['result'] = False
        failed_ids = []
        while True:
            try:
                _index = intermediate.index(False)
            except ValueError:
                break
            failed_ids.append(ids[_index])
            intermediate.pop(_index)
        ret['comment'] = 'Failed to delete indices {}'.format(', '.join(map(str, failed_ids)))
        return ret

    ret['result'] = True
    ret['comment'] = (
        'Successfuly deleted monitors {}'.format(', '.join(map(str, ids)))
    )

    return ret


def _generate_composite_query(query):
    '''
    Composite queries must be defined with monitor IDS. Replace names with
    monitor ids.
    '''

    word = r'\s*[a-zA-Z0-9\'\.\-\\_:/,%]+\s*'
    patterns = {
        'id': r'\d+',
        'name': r'({})+'.format(word),
        'open_parentheses': r'\(',
        'closed_parentheses': r'\)',
        'and': r'&&',
        'or': r'\|\|'
    }

    tokens = []
    while query:
        for _name, _pattern in six.iteritems(patterns):
            _match = re.match(_pattern, query)
            if _match:
                token = _match.group(0).rstrip(' ')
                tokens.append(token)
                query = query[len(token):].lstrip(' ')
                break
        else:  # string did not match patterns
            return False, 'Trouble matching string {}.'.format(query)

    replaced_tokens = []
    for token in tokens:
        if not re.match(patterns['id'], token) and re.match(patterns['name'], token):
            _id = __utils__['datadog.find_monitors_with_name'](name=token)
            if not _id:
                return False, 'Could not find monitor {}.'.format(token)
            replaced_tokens.append(_id[0])
        else:
            replaced_tokens.append(token)

    return True, ' '.join(replaced_tokens)

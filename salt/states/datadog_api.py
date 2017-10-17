# -*- coding: utf-8 -*-

# This module redefines the built-in 'id' as datadog's resource ID
# pylint: disable=redefined-builtin
'''
Datadog state

A state to manage datadog resources

The following parameters are required for all functions.

api_key
    The datadog API key

app_key
    The datadog application key

Full argument reference is available on the Datadog API reference page
https://docs.datadoghq.com/api/

.. code:: yaml

    cpu_monitor_managed:
      datadog.monitor_managed:
        - name: 'Bytes received on host0'
        - query: 'avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100'
        - type: 'metric alert'
        - message: 'Bytes received on host0 exceeeded limit'
        - tags:
            - host: host0
            - type: net
        - options:
            renotify_interval: 20
'''

# pylint: disable=invalid-name

from __future__ import absolute_import
import logging
import time

# Import salt libs
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'datadog'


def __virtual__():
    return True


# The monitor functions simply pass tags and options along to the datadog
# library. No modifications are made.
# pylint: disable=dangerous-default-value
def monitor_managed(api_key=None,
                    app_key=None,
                    name=None,
                    type=None,
                    query=None,
                    message='',
                    tags=[],
                    options={}):
    '''
    Manage a monitor by name.

    .. warning::

    Datadog supports multiple monitors with the same name and different IDs.
    In contrast, this state assumes monitors have unique names and operates on
    the first monitor it finds with the given name.

    Required arguments:

    :param name: The name of the monitor
    :type name: str

    :param query: The query that triggers the monitor
    :type query: str

    :param type: The type of the monitor
    :type type: str

    Optional arguments:

    :param message: The message sent when the monitor is triggered
    :type message: str

    :param tags: A list of tags to attach to the monitor
    :type tags: list

    :param options: An options dictionary
    :type options: dict

    CLI Example

    .. code-block:: bash

    salt-call state.apply datadog.monitor_managed \\
        name='Bytes received on host0' \\
        type='metric alert' \\
        query='avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 150'
    '''

    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': ''
    }

    if name is None:
        raise SaltInvocationError('name must be specified')
    if query is None:
        raise SaltInvocationError('query must be specified')
    if type is None:
        raise SaltInvocationError('type must be specified')

    defaults = _get_defaults(api_key=api_key, app_key=app_key)
    if message == '':
        message = defaults[type]['message']
    if options == {}:
        options = defaults[type]['options']
    if tags == []:
        tags = defaults[type]['tags']

    desired = {
        'type': type,
        'query': query,
        'message': message,
        'tags': tags,
        'options': options
    }

    monitor_id_list = __utils__['datadog.find_monitors_with_name'](
        api_key=api_key,
        app_key=app_key,
        name=name
    )

    if monitor_id_list:  # The monitor exists -> compare and update
        monitor_id = monitor_id_list[0]
        monitor = __salt__['datadog.read_monitor'](
            api_key=api_key,
            app_key=app_key,
            id=monitor_id
        )['response'][0]
        monitor_is_same, _ = _compare_monitor(monitor, desired)
        if monitor_is_same:
            ret['result'] = True
            ret['comment'] = 'The monitor {} is in the correct state'.format(name)
            return ret
        else:
            _type = monitor['type']
            res = __salt__['datadog.update_monitor'](
                api_key=api_key,
                app_key=app_key,
                id=monitor_id,
                name=name,
                query=query,
                message=message,
                options=defaults[_type]['options'],
                tags=tags
            )
            updated = res['response']
            _, changes = _compare_monitor(monitor, updated)
            if res['result']:
                ret['result'] = True
                ret['comment'] = 'Updated monitor {}'.format(name)
                ret['changes'] = changes
            else:
                ret['comment'] = 'Update monitor {} failed'.format(name)
            return ret
    else:  # The monitor does not exist -> create it
        res = __salt__['datadog.create_monitor'](
            api_key=api_key,
            app_key=app_key,
            name=name,
            type=type,
            query=query,
            message=message,
            tags=tags,
            options=options
        )
        if res['result']:
            ret['result'] = True
            ret['comment'] = 'Created monitor {}'.format(name)
            ret['changes'] = res['response']
        else:
            ret['comment'] = 'Create monitor {} failed: {}'.format(
                name,
                '\n\t'.join(res['response']['errors'])
            )
        return ret
# pylint: enable=dangerous-default-value


def monitor_absent(api_key=None,
                   app_key=None,
                   name=None):
    '''
    Ensure a monitor is absent by name

    Required arguments:

    :param name: The name of the monitor
    :type name: str

    CLI Example

    .. code-block:: bash

    salt-call state.apply datadog.monitor_absent name='CPU on host0 - last hour'
    '''

    ret = {
        'name': name,
        'changes': {},
        'result': False,
        'comment': ''
    }

    if name is None:
        raise SaltInvocationError('Parameter "name" must be specified')

    res = __salt__['datadog.read_monitor'](
        api_key=api_key,
        app_key=app_key,
        name=name
    )

    if res['result']:
        res = __salt__['datadog.delete_monitor'](
            api_key=api_key,
            app_key=app_key,
            name=name
        )
        if res['result']:
            ret['result'] = True
            ret['comment'] = 'Removed monitor {}'.format(name)
            ret['changes'] = {}  # What should I put here?
        else:
            ret['comment'] = 'Failed to remove monitor {}'.format(name)
    else:
        ret['result'] = True
        ret['comment'] = 'Monitor {} is not present'.format(name)

    return ret


def _compare_monitor(current, desired):
    '''
    Compare the existing monitor with the wanted one
    '''

    results = []
    changes = {}
    for attribute in ['type', 'query', 'message', 'tags', 'options']:
        if current[attribute] != desired[attribute]:
            changes[attribute] = {
                'old': current[attribute],
                'new': desired[attribute]
            }
            results.append(False)
        results.append(True)
    return all(results), changes


def _get_defaults(api_key=None, app_key=None):
    '''
    Get a monitor's default values

    This function maintains an up to date dummy monitor in the users datadog
    account for each type of monitor and queries it to get the default values
    for parameters like options, message, and tags.

    Returns a dictionary of default values:
    {
        'metric alert': {
            'options': {
                'notify_audit': False,
                'notify_no_data': True
            }
            'message': '',
            'tags': []
        },
        'service check': {
            'options: {
                'no_data_timeframe': 20
            }
        }
        ...
    }
    '''

    # Get defaults only once per state run
    if __context__.get('datadog_monitor_defaults', None) is not None:
        return __context__['datadog_monitor_defaults']

    threshold = 604800  # 1 week
    prefix = 'Salt test monitor'
    name_template = '{}: {}'  # prefix, type
    types = {
        'metric alert': 'avg(last_1h):avg:system.cpu.user{host:salt_datadog_host} > 200',
        'service check': '"process.up".over("host:salt_datadog_host").last(4).count_by_status()',
        'event alert': 'events("host:salt_datadog_host").rollup("count").last("1m") > 1000'
        #'composite': '{0} && {0}'.format(name_template.format(prefix, 'metric alert'))
    }

    names = [name_template.format(prefix, _type) for _type in types]
    res = __salt__['datadog.read_monitor'](
        api_key=api_key,
        app_key=app_key,
        name=names
    )

    monitor_list = res['response']
    current_names = [monitor['name'] for monitor in monitor_list]
    missing_monitors = set(names) - set(current_names)
    for monitor_name in missing_monitors:
        _type = monitor_name.split(':')[-1].lstrip(' ')
        res = __salt__['datadog.create_monitor'](
            api_key=api_key,
            app_key=app_key,
            name=monitor_name,
            type=_type,
            query=types[_type]
        )
        if res['result']:
            monitor_list.append(res['response'])

    # Refresh monitor defaults
    current_monitors = {}
    for monitor in monitor_list:
        # Datadog has three extra digits than does time.time()
        monitor_created = monitor['created_at'] / 1000
        if monitor_created - time.time() > threshold:
            res = __salt__['datadog.delete_monitor'](
              api_key=api_key,
              app_key=app_key,
              name=monitor['name']
            )
            res = __salt__['datadog.create_monitor'](
              api_key=api_key,
              app_key=app_key,
              name=monitor['name'],
              type=monitor['type'],
              query=monitor['query']
            )
            if res['result']:
                current_monitors[monitor['type']] = res['response']
        else:
            current_monitors[monitor['type']] = monitor

    # In case any of the calls above failed, set static defaults and update the
    # defualts dictionary with the dynamic ones
    defaults = {
        'metric alert': {
            'options': {
                'notify_audit': False,
                'locked': False,
                'silenced': {},
                'require_full_window': True,
                'new_host_delay': 300,
                'notify_no_data': False
            },
            'message': '',
            'tags': []
        },
        'service check': {
            'options': {
                'notify_no_data': False,
                'notify_audit': False,
                'locked': False,
                'new_host_delay': 300,
                'silenced': {}
            },
            'message': '',
            'tags': []
        },
        'event alert': {
            'options': {
                'notify_no_data': False,
                'notify_audit': False,
                'locked': False,
                'new_host_delay': 300,
                'silenced': {}
            },
            'message': '',
            'tags': []
        }
    }

    for _type in types:
        defaults[_type] = {}
    for _type in types:
        defaults[_type]['options'] = current_monitors[_type]['options']
        defaults[_type]['message'] = current_monitors[_type]['message']
        defaults[_type]['tags'] = current_monitors[_type]['tags']

    __context__['datadog_monitor_defaults'] = defaults
    return defaults

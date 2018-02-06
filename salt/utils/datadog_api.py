# -*- coding: utf-8 -*-
'''
Utilities for working with the Datadog API
'''

from __future__ import absolute_import

# Import salt libs
from salt.exceptions import SaltInvocationError

# Import third party libs
HAS_DATADOG = True
try:
    import datadog
except ImportError:
    HAS_DATADOG = False

# Define the module's virtual name
__virtualname__ = 'datadog'


def __virtual__():
    '''
    Only load if datadog library is installed
    '''

    if HAS_DATADOG:
        return True
    message = (
        'Missing dependency: the salt.utils.datadog module requires the '
        'datadog library'
    )
    return False, message


def initialize_connection(api_key, app_key):
    '''
    Initialize Datadog connection
    '''

    if __context__.get('datadog_client', None) is not None:
        return
    if api_key is None:
        raise SaltInvocationError('api_key must be specified')
    if app_key is None:
        raise SaltInvocationError('app_key must be specified')
    options = {
        'api_key': api_key,
        'app_key': app_key
    }
    datadog.initialize(**options)
    __context__['datadog_client'] = 'created'


def find_monitors_with_name(api_key=None,
                            app_key=None,
                            name=None):
    '''
    Find all monitors with a given name
    '''

    res = get_all_monitors(
        api_key=api_key,
        app_key=app_key,
        group_states='all',
        name=name
    )

    try:
        monitor_ids = [str(m['id']) for m in res['response']]
    except KeyError:
        monitor_ids = []
    return monitor_ids


def get_all_monitors(api_key=None,
                     app_key=None,
                     name=None,
                     tags=None,
                     group_states=None,
                     monitor_tags=None,
                     with_downtimes=True):
    '''
    Get all monitor details

    Optional arguments:

    :param name: Filter by the name of the monitor
    :type name: str

    :param tags: A list of tags to filter by
    :type tags: list

    :param group_states: Include additional information regarding group states
    :type group_states: str

    :param monitor_tags: A list of service or custom tags to filter by
    :type monitor_tags: list

    :param with_downtimes: Include current downtimes
    :type with_downtimes: bool
    '''

    initialize_connection(api_key, app_key)

    ret = {
        'result': False,
        'response': None,
        'comment': ''
    }

    res = datadog.api.Monitor.get_all(
        group_states=group_states,
        name=name,
        tags=tags,
        monitor_tags=monitor_tags,
        with_downtimes=with_downtimes
    )

    if 'errors' in res:
        ret['response'] = res
        ret['comment'] = 'Datadog monitor get_all call failed'
        return ret

    # Datadog's get_all returns monitors whose name matches the glob <name>*
    # This function should return only monitors whose names match exactly.
    if name is not None:
        res = [m for m in res if m['name'] == name]

    if not res:
        ret['comment'] = 'No monitors matched that filter'
    ret['result'] = True
    ret['response'] = res

    return ret

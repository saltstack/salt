# -*- coding: utf-8 -*-
'''
Module for execution of ServiceNow CI (configuration items)

.. versionadded:: Carbon

:depends: servicenow_rest python module

:configuration: Configure this module by specifying the name of a configuration
    profile in the minion config, minion pillar, or master config. The module
    will use the 'servicenow' key by default, if defined.

    For example:

    .. code-block:: yaml

        servicenow:
          instance_name: ''
          username: ''
          password: ''
'''
# Import python libs
from __future__ import absolute_import
import logging

# Import third party libs
HAS_LIBS = False
try:
    from servicenow_rest.api import Client

    HAS_LIBS = True
except ImportError:
    pass

log = logging.getLogger(__name__)

__virtualname__ = 'servicenow'

SERVICE_NAME = 'servicenow'


def __virtual__():
    '''
    Only load this module if servicenow is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return (False, 'The servicenow execution module failed to load: '
            'requires servicenow_rest python library to be installed.')


def _get_client():
    config = __salt__['config.option'](SERVICE_NAME)
    instance_name = config['instance_name']
    username = config['username']
    password = config['password']
    return Client(instance_name, username, password)


def set_change_request_state(change_id, state='approved'):
    '''
    Set the approval state of a change request/record

    :param change_id: The ID of the change request, e.g. CHG123545
    :type  change_id: ``str``

    :param state: The target state, e.g. approved
    :type  state: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion servicenow.set_change_request_state CHG000123 declined
        salt myminion servicenow.set_change_request_state CHG000123 approved
    '''
    client = _get_client()
    client.table = 'change_request'
    # Get the change record first
    record = client.get({'number': change_id})
    if record is None or len(record) == 0:
        log.error('Failed to fetch change record, maybe it does not exist?')
        return False
    # Use the sys_id as the unique system record
    sys_id = record[0]['sys_id']
    response = client.update({'approval': state}, sys_id)
    return response


def delete_record(table, sys_id):
    '''
    Delete an existing record

    :param table: The table name, e.g. sys_user
    :type  table: ``str``

    :param sys_id: The unique ID of the record
    :type  sys_id: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion servicenow.delete_record sys_computer 2134566
    '''
    client = _get_client()
    client.table = table
    response = client.delete(sys_id)
    return response


def non_structured_query(table, query=None, **kwargs):
    '''
    Run a non-structed (not a dict) query on a servicenow table.
    See http://wiki.servicenow.com/index.php?title=Encoded_Query_Strings#gsc.tab=0
    for help on constructing a non-structured query string.

    :param table: The table name, e.g. sys_user
    :type  table: ``str``

    :param query: The query to run (or use keyword arguments to filter data)
    :type  query: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion servicenow.non_structured_query sys_computer 'role=web'
        salt myminion servicenow.non_structured_query sys_computer role=web type=computer
    '''
    client = _get_client()
    client.table = table
    # underlying lib doesn't use six or past.basestring,
    # does isinstance(x,str)
    # http://bit.ly/1VkMmpE
    if query is None:
        # try and assemble a query by keyword
        query_parts = []
        for key, value in kwargs.items():
            query_parts.append('{0}={1}'.format(key, value))
        query = '^'.join(query_parts)
    query = str(query)
    response = client.get(query)
    return response


def update_record_field(table, sys_id, field, value):
    '''
    Update the value of a record's field in a servicenow table

    :param table: The table name, e.g. sys_user
    :type  table: ``str``

    :param sys_id: The unique ID of the record
    :type  sys_id: ``str``

    :param field: The new value
    :type  field: ``str``

    :param value: The new value
    :type  value: ``str``

    CLI Example:

    .. code-block:: bash

        salt myminion servicenow.update_record_field sys_user 2348234 first_name jimmy
    '''
    client = _get_client()
    client.table = table
    response = client.update({field: value}, sys_id)
    return response

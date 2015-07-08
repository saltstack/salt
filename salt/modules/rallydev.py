# -*- coding: utf-8 -*-
'''
Support for RallyDev

.. versionadded:: 2015.8.0

Requires a ``username`` and a ``password`` in ``/etc/salt/minion``:

.. code-block: yaml

    rallydev:
      username: myuser@example.com
      password: 123pass
'''

# Import python libs
from __future__ import absolute_import, print_function
import json
import logging

# Import salt libs
from salt.exceptions import SaltInvocationError
import salt.utils.http

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load the module if apache is installed
    '''
    if not __opts__.get('rallydev', {}).get('username', None):
        return False
    if not __opts__.get('rallydev', {}).get('password', None):
        return False
    return True


def _get_token():
    '''
    Get an auth token
    '''
    username = __opts__.get('rallydev', {}).get('username', None)
    password = __opts__.get('rallydev', {}).get('password', None)
    path = 'https://rally1.rallydev.com/slm/webservice/v2.0/security/authorize'
    result = salt.utils.http.query(
        path,
        decode=True,
        decode_type='json',
        text=True,
        status=True,
        username=username,
        password=password,
        cookies=True,
        persist_session=True,
        opts=__opts__,
    )
    if 'dict' not in result:
        return None

    return result['dict']['OperationResult']['SecurityToken']


def _query(action=None,
           command=None,
           args=None,
           method='GET',
           header_dict=None,
           data=None):
    '''
    Make a web call to RallyDev.
    '''
    token = _get_token()
    username = __opts__.get('rallydev', {}).get('username', None)
    password = __opts__.get('rallydev', {}).get('password', None)
    path = 'https://rally1.rallydev.com/slm/webservice/v2.0/'

    if action:
        path += action

    if command:
        path += '/{0}'.format(command)

    log.debug('RallyDev URL: {0}'.format(path))

    if not isinstance(args, dict):
        args = {}

    args['key'] = token

    if header_dict is None:
        header_dict = {'Content-type': 'application/json'}

    if method != 'POST':
        header_dict['Accept'] = 'application/json'

    decode = True
    if method == 'DELETE':
        decode = False

    return_content = None
    result = salt.utils.http.query(
        path,
        method,
        params=args,
        data=data,
        header_dict=header_dict,
        decode=decode,
        decode_type='json',
        text=True,
        status=True,
        username=username,
        password=password,
        cookies=True,
        persist_session=True,
        opts=__opts__,
    )
    log.debug('RallyDev Response Status Code: {0}'.format(result['status']))
    if 'error' in result:
        log.error(result['error'])
        return [result['status'], result['error']]

    return [result['status'], result.get('dict', {})]


def list_items(name):
    '''
    List items of a particular type

    CLI Examples:

    .. code-block:: bash

        salt myminion rallydev.list_<item name>s
        salt myminion rallydev.list_users
        salt myminion rallydev.list_artifacts
    '''
    status, result = _query(action=name)
    return result


def query_item(name, query_string, order='Rank'):
    '''
    Query a type of record for one or more items. Requires a valid query string.
    See https://rally1.rallydev.com/slm/doc/webservice/introduction.jsp for
    information on query syntax.

    CLI Example:

    .. code-block:: bash

        salt myminion rallydev.query_<item name> <query string> [<order>]
        salt myminion rallydev.query_task '(Name contains github)'
        salt myminion rallydev.query_task '(Name contains reactor)' Rank
    '''
    status, result = _query(
        action=name,
        args={'query': query_string,
              'order': order}
    )
    return result


def show_item(name, id_):
    '''
    Show an item

    CLI Example:

    .. code-block:: bash

        salt myminion rallydev.show_<item name> <item id>
    '''
    status, result = _query(action=name, command=id_)
    return result


def update_item(name, id_, field=None, value=None, postdata=None):
    '''
    Update an item. Either a field and a value, or a chunk of POST data, may be
    used, but not both.

    CLI Example:

    .. code-block:: bash

        salt myminion rallydev.update_<item name> <item id> field=<field> value=<value>
        salt myminion rallydev.update_<item name> <item id> postdata=<post data>
    '''

    if field and value:
        if postdata:
            raise SaltInvocationError('Either a field and a value, or a chunk '
                'of POST data, may be specified, but not both.')
        postdata = {name.title(): {field: value}}

    if postdata is None:
        raise SaltInvocationError('Either a field and a value, or a chunk of '
            'POST data must be specified.')

    status, result = _query(
        action=name,
        command=id_,
        method='POST',
        data=json.dumps(postdata),
    )
    return result


def show_artifact(id_):
    '''
    Show an artifact

    CLI Example:

    .. code-block:: bash

        salt myminion rallydev.show_artifact <artifact id>
    '''
    return show_item('artifact', id_)


def list_users():
    '''
    List the users

    CLI Example:

    .. code-block:: bash

        salt myminion rallydev.list_users
    '''
    return list_items('user')


def show_user(id_):
    '''
    Show a user

    CLI Example:

    .. code-block:: bash

        salt myminion rallydev.show_user <user id>
    '''
    return show_item('user', id_)


def update_user(id_, field, value):
    '''
    Update a user

    CLI Example:

    .. code-block:: bash

        salt myminion rallydev.update_user <user id> <field> <new value>
    '''
    return update_item('user', id_, field, value)


def query_user(query_string, order='UserName'):
    '''
    Update a user

    CLI Example:

    .. code-block:: bash

        salt myminion rallydev.query_user '(Name contains Jo)'
    '''
    return query_item('user', query_string, order)

# -*- coding: utf-8 -*-
'''
Module for sending messages to hipchat.

.. versionadded:: 2015.5.0

:configuration: This module can be used by either passing an api key and version
    directly or by specifying both in a configuration profile in the salt
    master/minion config.

    For example:

    .. code-block:: yaml

        hipchat:
          api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
          api_version: v1
'''
# Import Python Libs
from __future__ import absolute_import
import json
import logging

# Import 3rd-party Libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
from salt.ext.six.moves.urllib.parse import urlencode as _urlencode
from salt.ext.six.moves import range
import salt.ext.six.moves.http_client

import salt.utils.http

# pylint: enable=import-error,no-name-in-module,redefined-builtin

log = logging.getLogger(__name__)

__virtualname__ = 'hipchat'


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    return __virtualname__


def _query(function,
           api_key=None,
           api_version=None,
           room_id=None,
           method='GET',
           data=None):
    '''
    HipChat object method function to construct and execute on the API URL.

    :param api_key:     The HipChat api key.
    :param function:    The HipChat api function to perform.
    :param api_version: The HipChat api version (v1 or v2).
    :param method:      The HTTP method, e.g. GET or POST.
    :param data:        The data to be sent for POST method.
    :return:            The json response from the API call or False.
    '''
    headers = {}
    query_params = {}

    if not api_key or not api_version:
        try:
            options = __salt__['config.option']('hipchat')
            if not api_key:
                api_key = options.get('api_key')
            if not api_version:
                api_version = options.get('api_version')
        except (NameError, KeyError, AttributeError):
            log.error("No HipChat api key or version found.")
            return False

    if room_id:
        room_id = 'room/{0}/notification'.format(str(room_id))
    else:
        room_id = 'room/0/notification'

    hipchat_functions = {
        'v1': {
            'rooms': {
                'request': 'rooms/list',
                'response': 'rooms',
            },
            'users': {
                'request': 'users/list',
                'response': 'users',
            },
            'message': {
                'request': 'rooms/message',
                'response': 'status',
            },
        },
        'v2': {
            'rooms': {
                'request': 'room',
                'response': 'items',
            },
            'users': {
                'request': 'user',
                'response': 'items',
            },
            'message': {
                'request': room_id,
                'response': None,
            },
        },
    }

    api_url = 'https://api.hipchat.com'
    base_url = _urljoin(api_url, api_version + '/')
    path = hipchat_functions.get(api_version).get(function).get('request')
    url = _urljoin(base_url, path, False)

    if api_version == 'v1':
        query_params['format'] = 'json'
        query_params['auth_token'] = api_key

        if method == 'POST':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

        if data:
            if data.get('notify', None):
                data['notify'] = 1
            data = _urlencode(data)
    elif api_version == 'v2':
        headers['Authorization'] = 'Bearer {0}'.format(api_key)
        if data:
            data = json.dumps(data)

        if method == 'POST':
            headers['Content-Type'] = 'application/json'
    else:
        log.error('Unsupported HipChat API version')
        return False

    result = salt.utils.http.query(
        url,
        method,
        params=query_params,
        data=data,
        decode=True,
        status=True,
        header_dict=headers,
        opts=__opts__,
    )

    if result.get('status', None) == salt.ext.six.moves.http_client.OK:
        response = hipchat_functions.get(api_version).get(function).get('response')
        return result.get('dict', {}).get(response, None)
    elif result.get('status', None) == salt.ext.six.moves.http_client.NO_CONTENT:
        return False
    else:
        log.debug(url)
        log.debug(query_params)
        log.debug(data)
        log.debug(result)
        if result.get('error'):
            log.error(result)
        return False


def list_rooms(api_key=None, api_version=None):
    '''
    List all HipChat rooms.

    :param api_key: The HipChat admin api key.
    :param api_version: The HipChat api version, if not specified in the configuration.
    :return: The room list.

    CLI Example:

    .. code-block:: bash

        salt '*' hipchat.list_rooms

        salt '*' hipchat.list_rooms api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15 api_version=v1
    '''
    foo = _query(function='rooms', api_key=api_key, api_version=api_version)
    log.debug('foo {0}'.format(foo))
    return foo


def list_users(api_key=None, api_version=None):
    '''
    List all HipChat users.
    :param api_key: The HipChat admin api key.
    :param api_version: The HipChat api version, if not specified in the configuration.
    :return: The user list.

    CLI Example:

    .. code-block:: bash

        salt '*' hipchat.list_users

        salt '*' hipchat.list_users api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15 api_version=v1
    '''
    return _query(function='users', api_key=api_key, api_version=api_version)


def find_room(name, api_key=None, api_version=None):
    '''
    Find a room by name and return it.
    :param name:    The room name.
    :param api_key: The HipChat admin api key.
    :param api_version: The HipChat api version, if not specified in the configuration.
    :return:        The room object.

    CLI Example:

    .. code-block:: bash

        salt '*' hipchat.find_room name="Development Room"

        salt '*' hipchat.find_room name="Development Room" api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15 api_version=v1
    '''
    rooms = list_rooms(api_key=api_key, api_version=api_version)
    if rooms:
        for x in range(0, len(rooms)):
            if rooms[x]['name'] == name:
                return rooms[x]
    return False


def find_user(name, api_key=None, api_version=None):
    '''
    Find a user by name and return it.
    :param name:        The user name.
    :param api_key:     The HipChat admin api key.
    :param api_version: The HipChat api version, if not specified in the configuration.
    :return:            The user object.

    CLI Example:

    .. code-block:: bash

        salt '*' hipchat.find_user name="Thomas Hatch"

        salt '*' hipchat.find_user name="Thomas Hatch" api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15 api_version=v1
    '''
    users = list_users(api_key=api_key, api_version=api_version)
    if users:
        for x in range(0, len(users)):
            if users[x]['name'] == name:
                return users[x]
    return False


def send_message(room_id,
                 message,
                 from_name,
                 api_key=None,
                 api_version=None,
                 color='yellow',
                 notify=False):
    '''
    Send a message to a HipChat room.
    :param room_id:     The room id or room name, either will work.
    :param message:     The message to send to the HipChat room.
    :param from_name:   Specify who the message is from.
    :param api_key:     The HipChat api key, if not specified in the configuration.
    :param api_version: The HipChat api version, if not specified in the configuration.
    :param color:       The color for the message, default: yellow.
    :param notify:      Whether to notify the room, default: False.
    :return:            Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt '*' hipchat.send_message room_id="Development Room" message="Build is done" from_name="Build Server"

        salt '*' hipchat.send_message room_id="Development Room" message="Build failed" from_name="Build Server" color="red" notify=True
    '''

    parameters = dict()
    parameters['room_id'] = room_id
    parameters['from'] = from_name[:15]
    parameters['message'] = message[:10000]
    parameters['message_format'] = 'text'
    parameters['color'] = color
    parameters['notify'] = notify

    result = _query(function='message',
                    api_key=api_key,
                    api_version=api_version,
                    room_id=room_id,
                    method='POST',
                    data=parameters)

    if result:
        return True
    else:
        return False

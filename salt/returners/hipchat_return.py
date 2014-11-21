# -*- coding: utf-8 -*-
'''
Return salt data via hipchat

The following fields can be set in the minion conf file::

    hipchat.room_id (required)
    hipchat.api_key (required)
    hipchat.api_version (required)
    hipchat.from_name (required)
    hipchat.color (optional)
    hipchat.notify (optional)
    hipchat.profile (optional)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    hipchat.room_id
    hipchat.api_key
    hipchat.api_version
    hipchat.from_name

Hipchat settings may also be configured as::

    hipchat:
        room_id: RoomName
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        api_version: v1
        from_name: user@email.com

    alternative.hipchat:
        room_id: RoomName
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        api_version: v1
        from_name: user@email.com

    hipchat_profile:
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        api_version: v1
        from_name: user@email.com

    hipchat:
        profile: hipchat_profile
        room_id: RoomName

    alternative.hipchat:
        profile: hipchat_profile
        room_id: RoomName

  To use the HipChat returner, append '--return hipchat' to the salt command. ex:

  .. code-block:: bash

    salt '*' test.ping --return hipchat

  To use the alternative configuration, append '--return_config alternative' to the salt command. ex:

    salt '*' test.ping --return hipchat --return_config alternative
'''
from __future__ import absolute_import

# Import Python libs
import json
import pprint
import logging

# Import 3rd-party libs
import requests
from requests.exceptions import ConnectionError
# pylint: disable=import-error
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin  # pylint: disable=import-error,no-name-in-module
# pylint: enable=import-error

# Import Salt Libs
import salt.returners


log = logging.getLogger(__name__)
__virtualname__ = 'hipchat'


def _get_options(ret=None):
    '''
    Get the hipchat options from salt.
    '''

    defaults = {'color': 'yellow',
                'notify': False}

    attrs = {'hipchat_profile': 'profile',
             'room_id': 'room_id',
             'from_name': 'from_name',
             'api_key': 'api_key',
             'api_version': 'api_version',
             'color': 'color',
             'notify': 'notify',
             }

    profile_attr = 'hipchat_profile'

    profile_attrs = {'from_jid': 'from_jid',
                     'api_key': 'api_key',
                     'api_version': 'api_key'
                     }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   profile_attr=profile_attr,
                                                   profile_attrs=profile_attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__,
                                                   defaults=defaults)
    return _options


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    return __virtualname__


def _query(function, api_key=None, api_version=None, method='GET', data=None):
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

    if data is None:
        data = {}

    if data.get('room_id'):
        room_id = str(data.get('room_id'))
    else:
        room_id = '0'

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
                'request': 'room/' + room_id + '/notification',
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

        if data.get('notify'):
            data['notify'] = 1
        else:
            data['notify'] = 0
    elif api_version == 'v2':
        headers['Authorization'] = 'Bearer {0}'.format(api_key)
        data = json.dumps(data)
    else:
        log.error('Unsupported HipChat API version')
        return False

    try:
        result = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=query_params,
            data=data,
            verify=True,
        )
    except ConnectionError as e:
        log.error(e)
        return False

    if result.status_code == 200:
        result = result.json()
        response = hipchat_functions.get(api_version).get(function).get('response')
        return result.get(response)
    elif result.status_code == 204:
        return True
    else:
        log.debug(url)
        log.debug(query_params)
        log.debug(data)
        log.debug(result)
        if result.json().get('error'):
            log.error(result.json())
        return False


def _send_message(room_id,
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
                    method='POST',
                    data=parameters)

    if result:
        return True
    else:
        return False


def returner(ret):
    '''
    Send an hipchat message with the data
    '''

    _options = _get_options(ret)

    room_id = _options.get('room_id')
    from_name = _options.get('from_name')
    api_key = _options.get('api_key')
    api_version = _options.get('api_version')
    color = _options.get('color')
    notify = _options.get('notify')

    if not room_id:
        log.error('hipchat.room_id not defined in salt config')
        return

    if not from_name:
        log.error('hipchat.from_name not defined in salt config')
        return

    if not api_key:
        log.error('hipchat.api_key not defined in salt config')
        return

    if not api_version:
        log.error('hipchat.api_version not defined in salt config')
        return

    message = ('id: {0}\r\n'
               'function: {1}\r\n'
               'function args: {2}\r\n'
               'jid: {3}\r\n'
               'return: {4}\r\n').format(
                    ret.get('id'),
                    ret.get('fun'),
                    ret.get('fun_args'),
                    ret.get('jid'),
                    pprint.pformat(ret.get('return')))

    hipchat = _send_message(room_id,
                            message,
                            from_name,
                            api_key,
                            api_version,
                            color,
                            notify)
    return hipchat

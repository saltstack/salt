# -*- coding: utf-8 -*-
'''
Module for sending messages to Slack

.. versionadded:: 2015.5.0

:configuration: This module can be used by either passing an api key and version
    directly or by specifying both in a configuration profile in the salt
    master/minion config.

    For example:

    .. code-block:: yaml

        slack:
          api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
'''

# Import Python libs
from __future__ import absolute_import
import logging

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
from salt.ext.six.moves import range

try:
    import requests
    from requests.exceptions import ConnectionError
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# pylint: enable=import-error,no-name-in-module

log = logging.getLogger(__name__)
__virtualname__ = 'slack'


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    if not HAS_REQUESTS:
        return False

    return __virtualname__


def _query(function, api_key=None, method='GET', data=None):
    '''
    Slack object method function to construct and execute on the API URL.

    :param api_key:     The Slack api key.
    :param function:    The Slack api function to perform.
    :param method:      The HTTP method, e.g. GET or POST.
    :param data:        The data to be sent for POST method.
    :return:            The json response from the API call or False.
    '''
    headers = {}
    query_params = {}

    if data is None:
        data = {}

    ret = {'message': '',
           'res': True}

    slack_functions = {
        'rooms': {
            'request': 'channels.list',
            'response': 'channels',
        },
        'users': {
            'request': 'users.list',
            'response': 'members',
        },
        'message': {
            'request': 'chat.postMessage',
            'response': 'channel',
        },
    }

    if not api_key:
        try:
            options = __salt__['config.option']('slack')
            if not api_key:
                api_key = options.get('api_key')
        except (NameError, KeyError, AttributeError):
            log.error('No Slack api key found.')
            ret['message'] = 'No Slack api key found.'
            ret['res'] = False
            return ret

    api_url = 'https://slack.com'
    base_url = _urljoin(api_url, '/api/')
    path = slack_functions.get(function).get('request')
    url = _urljoin(base_url, path, False)
    query_params['token'] = api_key

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
        ret['message'] = e
        ret['res'] = False
        return ret

    if result.status_code == 200:
        result = result.json()
        response = slack_functions.get(function).get('response')
        if 'error' in result:
            ret['message'] = result['error']
            ret['res'] = False
            return ret
        ret['message'] = result.get(response)
        return ret
    elif result.status_code == 204:
        return True
    else:
        log.debug(url)
        log.debug(query_params)
        log.debug(data)
        log.debug(result)
        if 'error' in result:
            ret['message'] = result['error']
            ret['res'] = False
            return ret
        ret['message'] = result
        return ret


def list_rooms(api_key=None):
    '''
    List all Slack rooms.

    :param api_key: The Slack admin api key.
    :return: The room list.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.list_rooms

        salt '*' slack.list_rooms api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15
    '''
    return _query(function='rooms', api_key=api_key)


def list_users(api_key=None):
    '''
    List all Slack users.
    :param api_key: The Slack admin api key.
    :return: The user list.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.list_users

        salt '*' slack.list_users api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15
    '''
    return _query(function='users', api_key=api_key)


def find_room(name, api_key=None):
    '''
    Find a room by name and return it.
    :param name:    The room name.
    :param api_key: The Slack admin api key.
    :return:        The room object.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.find_room name="random"

        salt '*' slack.find_room name="random" api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15
    '''

    # search results don't include the name of the
    # channel with a hash, if the passed channel name
    # has a hash we remove it.
    if name.startswith('#'):
        name = name[1:]
    ret = list_rooms(api_key)
    if ret['res']:
        rooms = ret['message']
        if rooms:
            for room in range(0, len(rooms)):
                if rooms[room]['name'] == name:
                    return rooms[room]
    return False


def find_user(name, api_key=None):
    '''
    Find a user by name and return it.
    :param name:        The user name.
    :param api_key:     The Slack admin api key.
    :return:            The user object.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.find_user name="ThomasHatch"

        salt '*' slack.find_user name="ThomasHatch" api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15
    '''
    ret = list_users(api_key)
    if ret['res']:
        users = ret['message']
        if users:
            for user in range(0, len(users)):
                if users[user]['name'] == name:
                    return users[user]
    return False


def post_message(channel,
                 message,
                 from_name,
                 api_key=None):
    '''
    Send a message to a Slack channel.
    :param channel:     The channel name, either will work.
    :param message:     The message to send to the HipChat room.
    :param from_name:   Specify who the message is from.
    :param api_key:     The Slack api key, if not specified in the configuration.
    :return:            Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.send_message channel="Development Room" message="Build is done" from_name="Build Server"

    '''

    if not channel:
        log.error('channel is a required option.')

    # channel must start with a hash
    if not channel.startswith('#'):
        channel = '#{0}'.format(channel)

    if not from_name:
        log.error('from_name is a required option.')

    if not message:
        log.error('message is a required option.')

    if not from_name:
        log.error('from_name is a required option.')

    parameters = dict()
    parameters['channel'] = channel
    parameters['username'] = from_name
    parameters['text'] = message

    result = _query(function='message',
                    api_key=api_key,
                    method='POST',
                    data=parameters)

    if result['res']:
        return True
    else:
        return result

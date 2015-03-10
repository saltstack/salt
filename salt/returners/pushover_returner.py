# -*- coding: utf-8 -*-
'''
Return salt data via pushover

.. versionadded:: Boron

The following fields can be set in the minion conf file::

    slack.user (required)
    slack.api_key (required)
    slack.from_name (required)
    slack.profile (optional)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    slack.channel
    slack.api_key
    slack.from_name

Hipchat settings may also be configured as::

    slack:
        channel: RoomName
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        from_name: user@email.com

    alternative.slack:
        room_id: RoomName
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        from_name: user@email.com

    slack_profile:
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        from_name: user@email.com

    slack:
        profile: slack_profile
        channel: RoomName

    alternative.slack:
        profile: slack_profile
        channel: RoomName

  To use the HipChat returner, append '--return slack' to the salt command. ex:

  .. code-block:: bash

    salt '*' test.ping --return slack

  To use the alternative configuration, append '--return_config alternative' to the salt command. ex:

    salt '*' test.ping --return slack --return_config alternative
'''
from __future__ import absolute_import

# Import Python libs
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

__virtualname__ = 'pushover'


def _get_options(ret=None):
    '''
    Get the pushover options from salt.
    '''

    attrs = {'pushover_profile': 'profile',
             'user': 'user',
             'token': 'token',
             }

    profile_attr = 'pushover_profile'

    profile_attrs = {'user': 'user',
                     'token': 'token',
                     'api_version': 'api_key'
                     }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   profile_attr=profile_attr,
                                                   profile_attrs=profile_attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    return __virtualname__


def _query(function, token=None, api_version='1', method='POST', data=None):
    '''
    Slack object method function to construct and execute on the API URL.

    :param token:       The PushOver api key.
    :param api_version: The PushOver API version to use, defaults to version 1.
    :param function:    The PushOver api function to perform.
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

    pushover_functions = {
        'message': {
            'request': 'messages.json',
            'response': 'channel',
        },
    }

    if not token:
        try:
            options = __salt__['config.option']('pushover')
            if not token:
                token = options.get('token')
        except (NameError, KeyError, AttributeError):
            log.error('No PushOver token found.')
            ret['message'] = 'No PushOver token found.'
            ret['res'] = False
            return ret

    api_url = 'https://api.pushover.net'
    base_url = _urljoin(api_url, api_version + '/')
    path = pushover_functions.get(function).get('request')
    url = _urljoin(base_url, path, False)
    query_params['token'] = token

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
        response = pushover_functions.get(function).get('response')
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


def _post_message(user,
                  message,
                  title,
                  token=None):
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
    parameters['user'] = user
    parameters['token'] = token
    parameters['title'] = title
    parameters['message'] = message

    result = _query(function='message',
                    method='POST',
                    data=parameters)

    log.debug('result {0}'.format(result))
    if result:
        return True
    else:
        return False


def returner(ret):
    '''
    Send an PushOver message with the data
    '''

    _options = _get_options(ret)

    user = _options.get('user')
    token = _options.get('token')
    title = _options.get('title')

    if not user:
        log.error('pushover.user not defined in salt config')
        return

    if not token:
        log.error('pushover.token not defined in salt config')
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

    pushover = _post_message(user,
                             message,
                             title,
                             token)
    return pushover

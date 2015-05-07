# -*- coding: utf-8 -*-
'''
Return salt data via slack

.. versionadded:: 2015.5.0

The following fields can be set in the minion conf file::

    slack.channel (required)
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

To use the HipChat returner, append '--return slack' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return slack

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return slack --return_config alternative
'''
from __future__ import absolute_import

# Import Python libs
import pprint
import logging

# Import 3rd-party libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from requests.exceptions import ConnectionError
# pylint: disable=import-error
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin  # pylint: disable=import-error,no-name-in-module
# pylint: enable=import-error

# Import Salt Libs
import salt.returners

log = logging.getLogger(__name__)

__virtualname__ = 'slack'


def _get_options(ret=None):
    '''
    Get the slack options from salt.
    '''

    defaults = {'channel': '#general'}

    attrs = {'slack_profile': 'profile',
             'channel': 'channel',
             'from_name': 'from_name',
             'api_key': 'api_key',
             }

    profile_attr = 'slack_profile'

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


def _post_message(channel,
                  message,
                  from_name,
                  api_key=None):
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
    parameters['channel'] = channel
    parameters['from'] = from_name
    parameters['text'] = message

    result = _query(function='message',
                    api_key=api_key,
                    method='POST',
                    data=parameters)

    log.debug('result {0}'.format(result))
    if result:
        return True
    else:
        return False


def returner(ret):
    '''
    Send an slack message with the data
    '''

    _options = _get_options(ret)

    channel = _options.get('channel')
    from_name = _options.get('from_name')
    api_key = _options.get('api_key')

    if not channel:
        log.error('slack.channel not defined in salt config')
        return

    if not from_name:
        log.error('slack.from_name not defined in salt config')
        return

    if not api_key:
        log.error('slack.api_key not defined in salt config')
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

    slack = _post_message(channel,
                          message,
                          channel,
                          api_key)
    return slack

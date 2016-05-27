# -*- coding: utf-8 -*-
'''
Return salt data via hipchat.

.. versionadded:: 2015.5.0

The following fields can be set in the minion conf file::

    hipchat.room_id (required)
    hipchat.api_key (required)
    hipchat.api_version (required)
    hipchat.api_url (optional)
    hipchat.from_name (required)
    hipchat.color (optional)
    hipchat.notify (optional)
    hipchat.profile (optional)
    hipchat.url (optional)

.. note::

    When using Hipchat's API v2, ``api_key`` needs to be assigned to the room with the
    "Label" set to what you would have been set in the hipchat.from_name field. The v2
    API disregards the ``from_name`` in the data sent for the room notification and uses
    the Label assigned through the Hipchat control panel.

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    hipchat.room_id
    hipchat.api_key
    hipchat.api_version
    hipchat.api_url
    hipchat.from_name

Hipchat settings may also be configured as:

.. code-block:: yaml

    hipchat:
      room_id: RoomName
      api_url: https://hipchat.myteam.con
      api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      api_version: v1
      from_name: user@email.com

    alternative.hipchat:
      room_id: RoomName
      api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      api_version: v1
      from_name: user@email.com

    hipchat_profile:
      hipchat.api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      hipchat.api_version: v1
      hipchat.from_name: user@email.com

    hipchat:
      profile: hipchat_profile
      room_id: RoomName

    alternative.hipchat:
      profile: hipchat_profile
      room_id: RoomName

    hipchat:
      room_id: RoomName
      api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      api_version: v1
      api_url: api.hipchat.com
      from_name: user@email.com

To use the HipChat returner, append '--return hipchat' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return hipchat

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return hipchat --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return hipchat --return_kwargs '{"room_id": "another-room"}'

'''
from __future__ import absolute_import

# Import Python libs
import json
import pprint
import logging

# pylint: disable=import-error,no-name-in-module
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
from salt.ext.six.moves.urllib.parse import urlencode as _urlencode
import salt.ext.six.moves.http_client
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
                'notify': False,
                'api_url': 'api.hipchat.com'}

    attrs = {'hipchat_profile': 'profile',
             'room_id': 'room_id',
             'from_name': 'from_name',
             'api_key': 'api_key',
             'api_version': 'api_version',
             'color': 'color',
             'notify': 'notify',
             'api_url': 'api_url',
             }

    profile_attr = 'hipchat_profile'

    profile_attrs = {'from_jid': 'from_jid',
                     'api_key': 'api_key',
                     'api_version': 'api_key',
                     'api_url': 'api_url',
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


def _query(function,
           api_key=None,
           api_version=None,
           room_id=None,
           api_url=None,
           method='GET',
           data=None):
    '''
    HipChat object method function to construct and execute on the API URL.

    :param api_url:     The HipChat API URL.
    :param api_key:     The HipChat api key.
    :param function:    The HipChat api function to perform.
    :param api_version: The HipChat api version (v1 or v2).
    :param method:      The HTTP method, e.g. GET or POST.
    :param data:        The data to be sent for POST method.
    :return:            The json response from the API call or False.
    '''
    headers = {}
    query_params = {}

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

    api_url = 'https://{0}'.format(api_url)
    base_url = _urljoin(api_url, api_version + '/')
    path = hipchat_functions.get(api_version).get(function).get('request')
    url = _urljoin(base_url, path, False)

    if api_version == 'v1':
        query_params['format'] = 'json'
        query_params['auth_token'] = api_key

        if method == 'POST':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

        if data:
            if data.get('notify'):
                data['notify'] = 1
            else:
                data['notify'] = 0
            data = _urlencode(data)
    elif api_version == 'v2':
        headers['Content-Type'] = 'application/json'
        headers['Authorization'] = 'Bearer {0}'.format(api_key)
        if data:
            data = json.dumps(data)
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


def _send_message(room_id,
                  message,
                  from_name,
                  api_key=None,
                  api_version=None,
                  api_url=None,
                  color=None,
                  notify=False):
    '''
    Send a message to a HipChat room.
    :param room_id:     The room id or room name, either will work.
    :param message:     The message to send to the HipChat room.
    :param from_name:   Specify who the message is from.
    :param api_url:     The HipChat API URL, if not specified in the configuration.
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
                    room_id=room_id,
                    api_url=api_url,
                    method='POST',
                    data=parameters)

    if result:
        return True
    else:
        return False


def _verify_options(options):
    '''
    Verify Hipchat options and log warnings

    Returns True if all options can be verified,
    otherwise False
    '''
    if not options.get('room_id'):
        log.error('hipchat.room_id not defined in salt config')
        return False

    if not options.get('from_name'):
        log.error('hipchat.from_name not defined in salt config')
        return False

    if not options.get('api_key'):
        log.error('hipchat.api_key not defined in salt config')
        return False

    if not options.get('api_version'):
        log.error('hipchat.api_version not defined in salt config')
        return False

    return True


def returner(ret):
    '''
    Send an hipchat message with the return data from a job
    '''

    _options = _get_options(ret)

    if not _verify_options(_options):
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

    if ret.get('retcode') == 0:
        color = _options.get('color')
    else:
        color = 'red'

    hipchat = _send_message(_options.get('room_id'),  # room_id
                            message,  # message
                            _options.get('from_name'),  # from_name
                            api_key=_options.get('api_key'),
                            api_version=_options.get('api_version'),
                            api_url=_options.get('api_url'),
                            color=color,
                            notify=_options.get('notify'))

    return hipchat


def event_return(events):
    '''
    Return event data to hipchat
    '''
    _options = _get_options()

    for event in events:
        # TODO:
        # Pre-process messages to apply individualized colors for various
        # event types.
        log.trace('Hipchat returner received event: {0}'.format(event))
        _send_message(_options.get('room_id'),  # room_id
                      event['data'],  # message
                      _options.get('from_name'),  # from_name
                      api_key=_options.get('api_key'),
                      api_version=_options.get('api_version'),
                      api_url=_options.get('api_url'),
                      color=_options.get('color'),
                      notify=_options.get('notify'))

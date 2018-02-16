# -*- coding: utf-8 -*-
'''
Return salt data via mattermost

.. versionadded:: 2017.7.0

The following fields can be set in the minion conf file:

.. code-block:: yaml

    mattermost.hook (required)
    mattermost.username (optional)
    mattermost.channel (optional)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    mattermost.channel
    mattermost.hook
    mattermost.username

mattermost settings may also be configured as:

.. code-block:: yaml

    mattermost:
      channel: RoomName
      hook: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      username: user

To use the mattermost returner, append '--return mattermost' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return mattermost

To override individual configuration items, append --return_kwargs '{'key:': 'value'}' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return mattermost --return_kwargs '{'channel': '#random'}'
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging

# Import 3rd-party libs
from salt.ext import six
# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six.moves.http_client
# pylint: enable=import-error,no-name-in-module,redefined-builtin

# Import Salt Libs
import salt.returners
import salt.utils.json
import salt.utils.mattermost

log = logging.getLogger(__name__)

__virtualname__ = 'mattermost'


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the mattermost options from salt.
    '''

    attrs = {'channel': 'channel',
             'username': 'username',
             'hook': 'hook',
             'api_url': 'api_url'
             }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    log.debug('Options: %s', _options)
    return _options


def returner(ret):
    '''
    Send an mattermost message with the data
    '''

    _options = _get_options(ret)

    api_url = _options.get('api_url')
    channel = _options.get('channel')
    username = _options.get('username')
    hook = _options.get('hook')

    if not hook:
        log.error('mattermost.hook not defined in salt config')
        return

    returns = ret.get('return')

    message = ('id: {0}\r\n'
               'function: {1}\r\n'
               'function args: {2}\r\n'
               'jid: {3}\r\n'
               'return: {4}\r\n').format(
                    ret.get('id'),
                    ret.get('fun'),
                    ret.get('fun_args'),
                    ret.get('jid'),
                    returns)

    mattermost = post_message(channel,
                              message,
                              username,
                              api_url,
                              hook)
    return mattermost


def event_return(events):
    '''
    Send the events to a mattermost room.

    :param events:      List of events
    :return:            Boolean if messages were sent successfully.
    '''
    _options = _get_options()

    api_url = _options.get('api_url')
    channel = _options.get('channel')
    username = _options.get('username')
    hook = _options.get('hook')

    is_ok = True
    for event in events:
        log.debug('Event: %s', event)
        log.debug('Event data: %s', event['data'])
        message = 'tag: {0}\r\n'.format(event['tag'])
        for key, value in six.iteritems(event['data']):
            message += '{0}: {1}\r\n'.format(key, value)
        result = post_message(channel,
                              message,
                              username,
                              api_url,
                              hook)
        if not result:
            is_ok = False

    return is_ok


def post_message(channel,
                 message,
                 username,
                 api_url,
                 hook):
    '''
    Send a message to a mattermost room.

    :param channel:     The room name.
    :param message:     The message to send to the mattermost room.
    :param username:    Specify who the message is from.
    :param hook:        The mattermost hook, if not specified in the configuration.
    :return:            Boolean if message was sent successfully.
    '''

    parameters = dict()
    if channel:
        parameters['channel'] = channel
    if username:
        parameters['username'] = username
    parameters['text'] = '```' + message + '```'  # pre-formatted, fixed-width text
    log.debug('Parameters: %s', parameters)
    result = salt.utils.mattermost.query(
        api_url=api_url,
        hook=hook,
        data=str('payload={0}').format(salt.utils.json.dumps(parameters)))  # future lint: disable=blacklisted-function

    log.debug('result %s', result)
    return bool(result)

# -*- coding: utf-8 -*-
'''
Module for sending messages to Mattermost

.. versionadded:: 2017.7.0

:configuration: This module can be used by either passing an api_url and hook
    directly or by specifying both in a configuration profile in the salt
    master/minion config. For example:

    .. code-block:: yaml

        mattermost:
          hook: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
          api_url: https://example.com
'''

# Import Python libs
from __future__ import absolute_import
import json
import logging

# Import 3rd-party libs
import salt.ext.six as six

# Import Salt libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.utils.mattermost
# pylint: enable=import-error,no-name-in-module
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = 'mattermost'


def __virtual__():
    '''
    Return virtual name of the module.
    :return: The virtual name of the module.
    '''
    return __virtualname__


def _get_hook():
    '''
    Retrieves and return the Mattermost's configured hook
    :return:            String: the hook string
    '''
    hook = __salt__['config.get']('mattermost.hook') or \
        __salt__['config.get']('mattermost:hook')
    if not hook:
        raise SaltInvocationError('No Mattermost Hook found')

    return hook


def _get_api_url():
    '''
    Retrieves and return the Mattermost's configured api url
    :return:            String: the api url string
    '''
    api_url = __salt__['config.get']('mattermost.api_url') or \
        __salt__['config.get']('mattermost:api_url')
    if not api_url:
        raise SaltInvocationError('No Mattermost API URL found')

    return api_url


def _get_channel():
    '''
    Retrieves the Mattermost's configured channel
    :return:            String: the channel string
    '''
    channel = __salt__['config.get']('mattermost.channel') or \
        __salt__['config.get']('mattermost:channel')

    return channel


def _get_username():
    '''
    Retrieves the Mattermost's configured username
    :return:            String: the username string
    '''
    username = __salt__['config.get']('mattermost.username') or \
        __salt__['config.get']('mattermost:username')

    return username


def post_message(message,
                 channel=None,
                 username=None,
                 api_url=None,
                 hook=None):
    '''
    Send a message to a Mattermost channel.
    :param channel:     The channel name, either will work.
    :param username:    The username of the poster.
    :param message:     The message to send to the Mattermost channel.
    :param api_url:     The Mattermost api url, if not specified in the configuration.
    :param hook:        The Mattermost hook, if not specified in the configuration.
    :return:            Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt-run mattermost.post_message message='Build is done'
    '''
    if not api_url:
        api_url = _get_api_url()

    if not hook:
        hook = _get_hook()

    if not username:
        username = _get_username()

    if not channel:
        channel = _get_channel()

    if not message:
        log.error('message is a required option.')

    parameters = dict()
    if channel:
        parameters['channel'] = channel
    if username:
        parameters['username'] = username
    parameters['text'] = '```' + message + '```'  # pre-formatted, fixed-width text
    log.debug('Parameters: {0}'.format(parameters))
    result = salt.utils.mattermost.query(api_url=api_url,
                                         hook=hook,
                                         data='payload={0}'.format(json.dumps(parameters)))

    if result:
        return True
    else:
        return result


def post_event(event,
               channel=None,
               username=None,
               api_url=None,
               hook=None):
    '''
    Send an event to a Mattermost channel.
    :param channel:     The channel name, either will work.
    :param username:    The username of the poster.
    :param event:       The event to send to the Mattermost channel.
    :param api_url:     The Mattermost api url, if not specified in the configuration.
    :param hook:        The Mattermost hook, if not specified in the configuration.
    :return:            Boolean if message was sent successfully.
    '''
    if not api_url:
        api_url = _get_api_url()

    if not hook:
        hook = _get_hook()

    if not username:
        username = _get_username()

    if not channel:
        channel = _get_channel()

    if not event:
        log.error('message is a required option.')

    log.debug('Event: {0}'.format(str(event)))
    log.debug('Event data: {0}'.format(str(event['data'])))
    message = 'tag: {0}\r\n'.format(event['tag'])
    for key, value in six.iteritems(event['data']):
        message += '{0}: {1}\r\n'.format(key, value)
    result = post_message(channel,
                          username,
                          message,
                          api_url,
                          hook)
    return bool(result)

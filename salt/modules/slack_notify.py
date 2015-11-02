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
from salt.ext.six.moves.urllib.parse import urlencode as _urlencode
from salt.ext.six.moves import range
import salt.ext.six.moves.http_client

import salt.utils.slack
# pylint: enable=import-error,no-name-in-module

from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = 'slack'


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    return __virtualname__


def _get_api_key():
    api_key = __salt__['config.get']('slack.api_key') or \
        __salt__['config.get']('slack:api_key')

    if not api_key:
        raise SaltInvocationError('No Slack API key found.')

    return api_key


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
    if not api_key:
        api_key = _get_api_key()
    return salt.utils.slack.query(function='rooms',
                                  api_key=api_key,
                                  opts=__opts__)


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
    if not api_key:
        api_key = _get_api_key()
    return salt.utils.slack.query(function='users',
                                  api_key=api_key,
                                  opts=__opts__)


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
    if not api_key:
        api_key = _get_api_key()

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
    if not api_key:
        api_key = _get_api_key()

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
                 api_key=None,
                 icon=None):
    '''
    Send a message to a Slack channel.

    :param channel:     The channel name, either will work.
    :param message:     The message to send to the Slack channel.
    :param from_name:   Specify who the message is from.
    :param api_key:     The Slack api key, if not specified in the configuration.
    :param icon:        URL to an image to use as the icon for this message
    :return:            Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.post_message channel="Development Room" message="Build is done" from_name="Build Server"

    '''
    if not api_key:
        api_key = _get_api_key()

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

    parameters = {
        'channel': channel,
        'username': from_name,
        'text': message
    }

    if icon is not None:
        parameters['icon_url'] = icon

    # Slack wants the body on POST to be urlencoded.
    result = salt.utils.slack.query(function='message',
                                    api_key=api_key,
                                    method='POST',
                                    header_dict={'Content-Type': 'application/x-www-form-urlencoded'},
                                    data=_urlencode(parameters),
                                    opts=__opts__)

    if result['res']:
        return True
    else:
        return result

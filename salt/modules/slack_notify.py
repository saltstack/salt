# -*- coding: utf-8 -*-
'''
Module for notifications via Slack.
See https://slack.com for more info.

.. versionadded:: Lithium

:depends:   - pyslack python module
:configuration: Configure this module by specifying the name of a configuration
    profile in the minion config, minion pillar, or master config.

    For example:

    .. code-block:: yaml

        slack.api_token: <api token>
        slack.username: salt-bot
'''
import logging
from salt.exceptions import CommandExecutionError

HAS_LIBS = False
try:
    import slack
    import slack.chat
    from slack.exception import ChannelNotFoundError
    from slack.exception import NotAuthedError
    HAS_LIBS = True
except ImportError:
    pass

log = logging.getLogger(__name__)

__virtualname__ = 'slack'


def __virtual__():
    '''
    Only load this module if slack is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return False


def _setup():
    '''
    Return the slack connection
    '''
    creds = {}
    creds['api_token'] = __salt__['config.option']('slack.api_token')
    creds['username'] = __salt__['config.option']('slack.username')
    slack.api_token = creds.get('api_token')
    return creds


def post_message(message, channel='#general', username=None):
    '''
    Post a message to a channel

    CLI Example:

    .. code-block:: yaml

        salt '*' slack.post_message 'Test message'
    '''
    ret = {}
    creds = _setup()
    if username is None:
        username = creds['username']
    try:
        ret = slack.chat.post_message(channel, message, username=username)
    except ChannelNotFoundError as exc:
        raise CommandExecutionError('Channel "{0}" does not exist. {1}'.format(channel, exc))
    except NotAuthedError as exc:
        raise CommandExecutionError('Authentication Failed. {0}'.format(exc))
    return ret

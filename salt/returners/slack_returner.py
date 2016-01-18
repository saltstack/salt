# -*- coding: utf-8 -*-
'''
Return salt data via slack

.. versionadded:: 2015.5.0

The following fields can be set in the minion conf file::

    slack.channel (required)
    slack.api_key (required)
    slack.from_name (required)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    slack.channel
    slack.api_key
    slack.from_name

Slack settings may also be configured as::

    slack:
        channel: RoomName
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        from_name: user

    alternative.slack:
        room_id: RoomName
        api_key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        from_name: user@email.com

To use the Slack returner, append '--return slack' to the salt command.

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

# Import Salt Libs
import salt.returners
import salt.states.slack

log = logging.getLogger(__name__)

__virtualname__ = 'slack'


def _get_options(ret=None):
    '''
    Get the slack options from salt.
    '''

    defaults = {'channel': '#general'}

    attrs = {'channel': 'channel',
             'from_name': 'from_name',
             'api_key': 'api_key',
             }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__,
                                                   defaults=defaults)
    return _options


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    return __virtualname__ if 'slack.post_message' in __salt__ else False


def _post_message(name,
                  channel,
                  from_name,
                  message,
                  api_key=None):

    '''
    Send a message to a Slack channel.
    .. code-block:: yaml
        slack-message:
          slack.post_message:
            - channel: '#general'
            - from_name: SuperAdmin
            - message: 'This state was executed successfully.'
            - api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
    The following parameters are required:
    name
        The unique name for this event.
    channel
        The channel to send the message to. Can either be the ID or the name.
    from_name
        The name of that is to be shown in the "from" field.
    message
        The message that is to be sent to the Slack channel.
    The following parameters are optional:
    api_key
        The api key for Slack to use for authentication,
        if not specified in the configuration options of master or minion.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not channel:
        ret['comment'] = 'Slack channel is missing: {0}'.format(channel)
        return ret

    if not from_name:
        ret['comment'] = 'Slack from name is missing: {0}'.format(from_name)
        return ret

    if not message:
        ret['comment'] = 'Slack message is missing: {0}'.format(message)
        return ret

    result = __salt__['slack.post_message'](
        channel=channel,
        message=message,
        from_name=from_name,
        api_key=api_key,
    )

    if result:
        ret['result'] = True
        ret['comment'] = 'Sent message: {0}'.format(name)
    else:
        ret['comment'] = 'Failed to send message: {0}'.format(name)

    return ret


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
                          from_name,
                          api_key)
    return slack


def event_return(events):
    '''
    Return event data to slack
    '''
    _options = _get_options()

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

    for event in events:
        '''
        Event message format

        salt/beacon/<minion_id>/service/        {
            "_stamp": "2016-01-15T17:44:19.890790",
            "data": {
                "id": "<minion_id>",
                "<service name>": {
                    "running": <state boolean>
                }
            },
            "tag": "salt/beacon/<minion_id>/service/"
        }
        '''

        tag = event.get('tag', '')
        data = event.values()[1]
        host = data.values()[2]['id']
        service = data.values()[2].keys()[0]
        status = str(data.values()[2].values()[0].values()[0])

        message = ('id: {0}\r\n'
                   '{1}: running = {2}\r\n').format(
                       host,
                       service,
                       status)

        message = '```' + message + '```'

        log.trace('Slack returner received event: {0}'.format(event))
        _post_message(tag,
                      channel,
                      from_name,
                      message,
                      api_key)

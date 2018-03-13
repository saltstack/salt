# -*- coding: utf-8 -*-
'''
Send a message to Slack
=======================

This state is useful for sending messages to Slack during state runs.

.. versionadded:: 2015.5.0

.. code-block:: yaml

    slack-message:
      slack.post_message:
        - channel: '#general'
        - from_name: SuperAdmin
        - message: 'This state was executed successfully.'
        - api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15

The api key can be specified in the master or minion configuration like below:

.. code-block:: yaml

    slack:
      api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15

'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt libs
from salt.exceptions import SaltInvocationError


def __virtual__():
    '''
    Only load if the slack module is available in __salt__
    '''
    return 'slack' if 'slack.post_message' in __salt__ else False


def post_message(name,
                 channel,
                 from_name,
                 message,
                 api_key=None,
                 icon=None):
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

    icon
        URL to an image to use as the icon for this message
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'The following message is to be sent to Slack: {0}'.format(message)
        ret['result'] = None
        return ret

    if not channel:
        ret['comment'] = 'Slack channel is missing: {0}'.format(channel)
        return ret

    if not from_name:
        ret['comment'] = 'Slack from name is missing: {0}'.format(from_name)
        return ret

    if not message:
        ret['comment'] = 'Slack message is missing: {0}'.format(message)
        return ret

    try:
        result = __salt__['slack.post_message'](
            channel=channel,
            message=message,
            from_name=from_name,
            api_key=api_key,
            icon=icon,
        )
    except SaltInvocationError as sie:
        ret['comment'] = 'Failed to send message ({0}): {1}'.format(sie, name)
    else:
        if isinstance(result, bool) and result:
            ret['result'] = True
            ret['comment'] = 'Sent message: {0}'.format(name)
        else:
            ret['comment'] = 'Failed to send message ({0}): {1}'.format(result['message'], name)

    return ret

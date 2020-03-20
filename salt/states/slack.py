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


def post_message(name, **kwargs):
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

    api_key parameters:
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

    webhook parameters:
        name
            The unique name for this event.

        message
            The message that is to be sent to the Slack channel.

        color
            The color of border of left side

        short
            An optional flag indicating whether the value is short
            enough to be displayed side-by-side with other values.

        identifier
            The identifier of WebHook.

        channel
            The channel to use instead of the WebHook default.

        username
            Username to use instead of WebHook default.

        icon_emoji
            Icon to use instead of WebHook default.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not kwargs.get('api_key') and not kwargs.get('webhook'):
        ret['comment'] = 'Please specify api_key or webhook.'
        return ret

    if kwargs.get('api_key') and kwargs.get('webhook'):
        ret['comment'] = 'Please specify only either api_key or webhook.'
        return ret

    if kwargs.get('api_key') and not kwargs.get('channel'):
        ret['comment'] = 'Slack channel is missing.'
        return ret

    if kwargs.get('api_key') and not kwargs.get('from_name'):
        ret['comment'] = 'Slack from name is missing.'
        return ret

    if not kwargs.get('message'):
        ret['comment'] = 'Slack message is missing.'
        return ret

    if __opts__['test']:
        ret['comment'] = 'The following message is to be sent to Slack: {0}'.format(kwargs.get('message'))
        ret['result'] = None
        return ret

    try:
        if kwargs.get('api_key'):
            result = __salt__['slack.post_message'](
                channel=kwargs.get('channel'),
                message=kwargs.get('message'),
                from_name=kwargs.get('from_name'),
                api_key=kwargs.get('api_key'),
                icon=kwargs.get('icon'),
            )
        elif kwargs.get('webhook'):
            result = __salt__['slack.call_hook'](
                message=kwargs.get('message'),
                attachment=kwargs.get('attachment'),
                color=kwargs.get('color', 'good'),
                short=kwargs.get('short'),
                identifier=kwargs.get('webhook'),
                channel=kwargs.get('channel'),
                username=kwargs.get('username'),
                icon_emoji=kwargs.get('icon_emoji')
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

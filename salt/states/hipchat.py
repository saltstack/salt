# -*- coding: utf-8 -*-
'''
Send a message to Hipchat
=========================

This state is useful for sending messages to Hipchat during state runs.

The property api_url is optional. By defaul will use the public HipChat API at https://api.hipchat.com

.. versionadded:: 2015.5.0

.. code-block:: yaml

    hipchat-message:
      hipchat.send_message:
        - room_id: 123456
        - from_name: SuperAdmin
        - message: 'This state was executed successfully.'
        - api_url: https://hipchat.myteam.com
        - api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
        - api_version: v1

The api key can be specified in the master or minion configuration like below:

.. code-block:: yaml

    hipchat:
      api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
      api_version: v1

'''


def __virtual__():
    '''
    Only load if the hipchat module is available in __salt__
    '''
    return 'hipchat' if 'hipchat.send_message' in __salt__ else False


def send_message(name,
                 room_id,
                 from_name,
                 message,
                 api_url=None,
                 api_key=None,
                 api_version=None,
                 message_color='yellow',
                 notify=False):
    '''
    Send a message to a Hipchat room.

    .. code-block:: yaml

        hipchat-message:
          hipchat.send_message:
            - room_id: 123456
            - from_name: SuperAdmin
            - message: 'This state was executed successfully.'
            - api_url: https://hipchat.myteam.com
            - api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
            - api_version: v1
            - color: green
            - notify: True

    The following parameters are required:

    name
        The unique name for this event.

    room_id
        The room to send the message to. Can either be the ID or the name.

    from_name
        The name of that is to be shown in the "from" field.
        If not specified, defaults to.

    message
        The message that is to be sent to the Hipchat room.

    The following parameters are optional:

    api_url
        The API URl to be used.
        If not specified here or in the configuration options of master or minion,
        will use the public HipChat API: https://api.hipchat.com

    api_key
        The api key for Hipchat to use for authentication,
        if not specified in the configuration options of master or minion.

    api_version
        The api version for Hipchat to use,
        if not specified in the configuration options of master or minion.

    color
        The color the Hipchat message should be displayed in. One of the following, default: yellow
        "yellow", "red", "green", "purple", "gray", or "random".

    notify
        Should a notification in the room be raised.
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'The following message is to be sent to Hipchat: {0}'.format(message)
        ret['result'] = None
        return ret

    if not room_id:
        ret['comment'] = 'Hipchat room id is missing: {0}'.format(name)
        return ret

    if not from_name:
        ret['comment'] = 'Hipchat from name is missing: {0}'.format(name)
        return ret

    if not message:
        ret['comment'] = 'Hipchat message is missing: {0}'.format(name)
        return ret

    ret['result'] = __salt__['hipchat.send_message'](
        room_id=room_id,
        message=message,
        from_name=from_name,
        api_url=api_url,
        api_key=api_key,
        api_version=api_version,
        color=message_color,
        notify=notify,
    )

    if ret and ret['result']:
        ret['comment'] = 'Sent message: {0}'.format(name)
    else:
        ret['comment'] = 'Failed to send message: {0}'.format(name)

    return ret

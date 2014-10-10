# -*- coding: utf-8 -*-
"""
Send a message to Hipchat
============================

This state is useful for sending messages to Hipchat during state runs.

.. code-block:: yaml

    hipchat-message:
      hipchat.send_message:
        - api_key: nwg13WyLKiFq0ghpnwg13WyLKiFq0ghp
        - message: 'This state was executed successfully.'
        - from_name: SuperAdmin
        - room_id: 123456

The api key can be specified in the master or minion configuration like below:
.. code-block:: yaml

    hipchat:
      api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15

"""


def __virtual__():
    """
    Only load if the hipchat module is available in __salt__
    """
    return 'hipchat' if 'hipchat.send_message' in __salt__ else False


# Explicitly alias the SALT special global values to assist an IDE
try:
    __pillar__ = globals()["__pillar__"]
    __grains__ = globals()["__grains__"]
    __salt__ = globals()["__salt__"]
except (NameError, KeyError):
    # Set these to none as Salt will come back and set values to these after the module is loaded
    # and prior to calling any functions on this module
    __pillar__ = None
    __grains__ = None
    __salt__ = None


def send_message(name,
                 message,
                 from_name,
                 room_id=None,
                 room_name=None,
                 api_key=None,
                 message_color='yellow',
                 notify=False):
    """
    Send a message to a hipchat room.

    .. code-block:: yaml

        hipchat-message:
          hipchat.send_message:
            - api_key: nwg13WyLKiFq0ghpnwg13WyLKiFq0ghp
            - message: 'This state was executed successfully.'
            - from_name: SuperAdmin
            - room_id: 123456
            - message_color: green
            - notify: True

    The following parameters are required:

    name
        The unique name for this event.

    message
        The message that is to be sent to the Hipchat room.

    from_name
        The name of that is to be shown in the "from" field.
        If not specified, defaults to.

    room_id OR room_name
        Either of those properties has to be specified.
        If only the room_name is specified, the api_key has to be an
        admin key so the module can look up the room id.

    The following parameters are optional:
    api_key
        The api key for hipchat to use for authentication,
        if not specified in the configuration options of master or minion.

    message_color
        The color the hipchat message should be displayed in. One of the following, default: yellow
        "yellow", "red", "green", "purple", "gray", or "random".

    notify
        Should a notification in the room be raised.
    """
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if __opts__['test']:
        ret['comment'] = 'The following message is to be sent to hipchat: {0}'.format(message)
        ret['result'] = None
        return ret

    if not message:
        ret['comment'] = 'Hipchat message is missing: {0}'.format(name)
        return ret

    if not from_name:
        ret['comment'] = 'Hipchat from name is missing: {0}'.format(name)
        return ret

    ret['result'] = __salt__['hipchat.send_message'](
        api_key=api_key,
        message=message,
        from_name=from_name,
        room_id=room_id,
        room_name=room_name,
        message_color=message_color,
        notify=notify,
    )

    if ret and ret['result']:
        ret['comment'] = 'Sent message: {0}'.format(name)
    else:
        ret['comment'] = 'Failed to send message: {0}'.format(name)

    return ret
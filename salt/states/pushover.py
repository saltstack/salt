"""
Send a message to PushOver
==========================

This state is useful for sending messages to PushOver during state runs.

.. versionadded:: 2015.5.0

.. code-block:: yaml

    pushover-message:
      pushover.post_message:
        - user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        - token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        - title: Salt Returner
        - device: phone
        - priority: -1
        - expire: 3600
        - retry: 5
        - message: 'This state was executed successfully.'

The api key can be specified in the master or minion configuration like below:
.. code-block:: yaml

    pushover:
      token: peWcBiMOS9HrZG15peWcBiMOS9HrZG15

"""


def __virtual__():
    """
    Only load if the pushover module is available in __salt__
    """
    if "pushover.post_message" in __salt__:
        return "pushover"
    return (False, "pushover module could not be loaded")


def post_message(
    name,
    user=None,
    device=None,
    message=None,
    title=None,
    priority=None,
    expire=None,
    retry=None,
    sound=None,
    api_version=1,
    token=None,
):
    """
    Send a message to a PushOver channel.

    .. code-block:: yaml

        pushover-message:
          pushover.post_message:
            - user: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
            - token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
            - title: Salt Returner
            - device: phone
            - priority: -1
            - expire: 3600
            - retry: 5

    The following parameters are required:

    name
        The unique name for this event.

    user
        The user or group of users to send the message to. Must be ID of user, not name
        or email address.

    message
        The message that is to be sent to the PushOver channel.

    The following parameters are optional:

    title
        The title to use for the message.

    device
        The device for the user to send the message to.

    priority
        The priority for the message.

    expire
        The message should expire after specified amount of seconds.

    retry
        The message should be resent this many times.

    token
        The token for PushOver to use for authentication,
        if not specified in the configuration options of master or minion.

    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if __opts__["test"]:
        ret["comment"] = "The following message is to be sent to PushOver: {}".format(
            message
        )
        ret["result"] = None
        return ret

    if not user:
        ret["comment"] = "PushOver user is missing: {}".format(user)
        return ret

    if not message:
        ret["comment"] = "PushOver message is missing: {}".format(message)
        return ret

    result = __salt__["pushover.post_message"](
        user=user,
        message=message,
        title=title,
        device=device,
        priority=priority,
        expire=expire,
        retry=retry,
        token=token,
    )

    if result:
        ret["result"] = True
        ret["comment"] = "Sent message: {}".format(name)
    else:
        ret["comment"] = "Failed to send message: {}".format(name)

    return ret

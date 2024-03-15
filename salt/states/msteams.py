"""
Send a message card to Microsoft Teams
======================================

This state is useful for sending messages to Teams during state runs.

.. versionadded:: 2017.7.0

.. code-block:: yaml

    teams-message:
      msteams.post_card:
        - message: 'This state was executed successfully.'
        - hook_url:  https://outlook.office.com/webhook/837

The hook_url can be specified in the master or minion configuration like below:

.. code-block:: yaml

    msteams:
      hook_url: https://outlook.office.com/webhook/837
"""

from salt.exceptions import SaltInvocationError


def __virtual__():
    """
    Only load if the msteams module is available in __salt__
    """
    if "msteams.post_card" in __salt__:
        return "msteams"
    return (False, "msteams module could not be loaded")


def post_card(name, message, hook_url=None, title=None, theme_color=None):
    """
    Send a message to a Microsft Teams channel

    .. code-block:: yaml

        send-msteams-message:
          msteams.post_card:
            - message: 'This state was executed successfully.'
            - hook_url: https://outlook.office.com/webhook/837

    The following parameters are required:

    message
        The message that is to be sent to the MS Teams channel.

    The following parameters are optional:

    hook_url
        The webhook URL given configured in Teams interface,
        if not specified in the configuration options of master or minion.
    title
        The title for the card posted to the channel
    theme_color
        A hex code for the desired highlight color
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if __opts__["test"]:
        ret["comment"] = "The following message is to be sent to Teams: {}".format(
            message
        )
        ret["result"] = None
        return ret

    if not message:
        ret["comment"] = f"Teams message is missing: {message}"
        return ret

    try:
        result = __salt__["msteams.post_card"](
            message=message,
            hook_url=hook_url,
            title=title,
            theme_color=theme_color,
        )
    except SaltInvocationError as sie:
        ret["comment"] = f"Failed to send message ({sie}): {name}"
    else:
        if isinstance(result, bool) and result:
            ret["result"] = True
            ret["comment"] = f"Sent message: {name}"
        else:
            ret["comment"] = "Failed to send message ({}): {}".format(
                result["message"], name
            )

    return ret

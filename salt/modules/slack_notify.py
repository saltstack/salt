"""
Module for sending messages to Slack

.. versionadded:: 2015.5.0

:configuration: This module can be used by either passing an api key and version
    directly or by specifying both in a configuration profile in the salt
    master/minion config.

    For example:

    .. code-block:: yaml

        slack:
          api_key: peWcBiMOS9HrZG15peWcBiMOS9HrZG15
"""

import logging
import urllib.parse

import salt.utils.json
import salt.utils.slack
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = "slack"


def __virtual__():
    """
    Return virtual name of the module.

    :return: The virtual name of the module.
    """
    return __virtualname__


def _get_api_key():
    api_key = __salt__["config.get"]("slack.api_key") or __salt__["config.get"](
        "slack:api_key"
    )

    if not api_key:
        raise SaltInvocationError("No Slack API key found.")

    return api_key


def _get_hook_id():
    url = __salt__["config.get"]("slack.hook") or __salt__["config.get"]("slack:hook")
    if not url:
        raise SaltInvocationError("No Slack WebHook url found")

    return url


def list_rooms(api_key=None):
    """
    List all Slack rooms.

    :param api_key: The Slack admin api key.
    :return: The room list.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.list_rooms

        salt '*' slack.list_rooms api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15
    """
    if not api_key:
        api_key = _get_api_key()
    return salt.utils.slack.query(function="rooms", api_key=api_key, opts=__opts__)


def list_users(api_key=None):
    """
    List all Slack users.

    :param api_key: The Slack admin api key.
    :return: The user list.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.list_users

        salt '*' slack.list_users api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15
    """
    if not api_key:
        api_key = _get_api_key()
    return salt.utils.slack.query(function="users", api_key=api_key, opts=__opts__)


def find_room(name, api_key=None):
    """
    Find a room by name and return it.

    :param name:    The room name.
    :param api_key: The Slack admin api key.
    :return:        The room object.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.find_room name="random"

        salt '*' slack.find_room name="random" api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15
    """
    if not api_key:
        api_key = _get_api_key()

    # search results don't include the name of the
    # channel with a hash, if the passed channel name
    # has a hash we remove it.
    if name.startswith("#"):
        name = name[1:]
    ret = list_rooms(api_key)
    if ret["res"]:
        rooms = ret["message"]
        if rooms:
            for room in rooms:
                if room["name"] == name:
                    return room
    return False


def find_user(name, api_key=None):
    """
    Find a user by name and return it.

    :param name:        The user name.
    :param api_key:     The Slack admin api key.
    :return:            The user object.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.find_user name="ThomasHatch"

        salt '*' slack.find_user name="ThomasHatch" api_key=peWcBiMOS9HrZG15peWcBiMOS9HrZG15
    """
    if not api_key:
        api_key = _get_api_key()

    ret = list_users(api_key)
    if ret["res"]:
        users = ret["message"]
        if users:
            for user in users:
                if user["name"] == name:
                    return user
    return False


def post_message(
    channel,
    message,
    from_name,
    api_key=None,
    icon=None,
    attachments=None,
    blocks=None,
):
    """
    Send a message to a Slack channel.

    .. versionchanged:: 3003
        Added `attachments` and `blocks` kwargs

    :param channel:     The channel name, either will work.
    :param message:     The message to send to the Slack channel.
    :param from_name:   Specify who the message is from.
    :param api_key:     The Slack api key, if not specified in the configuration.
    :param icon:        URL to an image to use as the icon for this message
    :param attachments: Any attachments to be sent with the message.
    :param blocks:      Any blocks to be sent with the message.
    :return:            Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.post_message channel="Development Room" message="Build is done" from_name="Build Server"

    """
    if not api_key:
        api_key = _get_api_key()

    if not channel:
        log.error("channel is a required option.")

    # channel must start with a hash or an @ (direct-message channels)
    if not channel.startswith("#") and not channel.startswith("@"):
        log.warning(
            "Channel name must start with a hash or @. "
            'Prepending a hash and using "#%s" as '
            "channel name instead of %s",
            channel,
            channel,
        )
        channel = f"#{channel}"

    if not from_name:
        log.error("from_name is a required option.")

    if not message:
        log.error("message is a required option.")

    if not from_name:
        log.error("from_name is a required option.")

    parameters = {
        "channel": channel,
        "username": from_name,
        "text": message,
        "attachments": attachments or [],
        "blocks": blocks or [],
    }

    if icon is not None:
        parameters["icon_url"] = icon

    # Slack wants the body on POST to be urlencoded.
    result = salt.utils.slack.query(
        function="message",
        api_key=api_key,
        method="POST",
        header_dict={"Content-Type": "application/x-www-form-urlencoded"},
        data=urllib.parse.urlencode(parameters),
        opts=__opts__,
    )

    if result["res"]:
        return True
    else:
        return result


def call_hook(
    message,
    attachment=None,
    color="good",
    short=False,
    identifier=None,
    channel=None,
    username=None,
    icon_emoji=None,
):
    """
    Send message to Slack incoming webhook.

    :param message:     The topic of message.
    :param attachment:  The message to send to the Slack WebHook.
    :param color:       The color of border of left side
    :param short:       An optional flag indicating whether the value is short
                        enough to be displayed side-by-side with other values.
    :param identifier:  The identifier of WebHook.
    :param channel:     The channel to use instead of the WebHook default.
    :param username:    Username to use instead of WebHook default.
    :param icon_emoji:  Icon to use instead of WebHook default.
    :return:            Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt '*' slack.call_hook message='Hello, from SaltStack'

    """
    base_url = "https://hooks.slack.com/services/"
    if not identifier:
        identifier = _get_hook_id()

    url = urllib.parse.urljoin(base_url, identifier)

    if not message:
        log.error("message is required option")

    if attachment:
        payload = {
            "attachments": [
                {
                    "fallback": message,
                    "color": color,
                    "pretext": message,
                    "fields": [{"value": attachment, "short": short}],
                }
            ]
        }
    else:
        payload = {
            "text": message,
        }

    if channel:
        payload["channel"] = channel

    if username:
        payload["username"] = username

    if icon_emoji:
        payload["icon_emoji"] = icon_emoji

    data = urllib.parse.urlencode({"payload": salt.utils.json.dumps(payload)})
    result = salt.utils.http.query(url, method="POST", data=data, status=True)

    if result["status"] <= 201:
        return True
    else:
        return {"res": False, "message": result.get("body", result["status"])}

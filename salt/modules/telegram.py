"""
Module for sending messages via Telegram.

:configuration: In order to send a message via the Telegram, certain
    configuration is required in /etc/salt/minion on the relevant minions or
    in the pillar. Some sample configs might look like::

        telegram.chat_id: '123456789'
        telegram.token: '00000000:xxxxxxxxxxxxxxxxxxxxxxxx'

"""

import logging

from salt.exceptions import SaltInvocationError

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

log = logging.getLogger(__name__)

__virtualname__ = "telegram"


def __virtual__():
    """
    Return virtual name of the module.

    :return: The virtual name of the module.
    """
    if not HAS_REQUESTS:
        return (False, "Missing dependency requests")
    return __virtualname__


def _get_chat_id():
    """
    Retrieves and return the Telegram's configured chat id

    :return:    String: the chat id string
    """
    chat_id = __salt__["config.get"]("telegram:chat_id") or __salt__["config.get"](
        "telegram.chat_id"
    )
    if not chat_id:
        raise SaltInvocationError("No Telegram chat id found")

    return chat_id


def _get_token():
    """
    Retrieves and return the Telegram's configured token

    :return:    String: the token string
    """
    token = __salt__["config.get"]("telegram:token") or __salt__["config.get"](
        "telegram.token"
    )
    if not token:
        raise SaltInvocationError("No Telegram token found")

    return token


def post_message(message, chat_id=None, token=None):
    """
    Send a message to a Telegram chat.

    :param message: The message to send to the Telegram chat.
    :param chat_id: (optional) The Telegram chat id.
    :param token:   (optional) The Telegram API token.
    :return:        Boolean if message was sent successfully.

    CLI Example:

    .. code-block:: bash

        salt '*' telegram.post_message message="Hello Telegram!"

    """
    if not chat_id:
        chat_id = _get_chat_id()

    if not token:
        token = _get_token()

    if not message:
        log.error("message is a required option.")

    return _post_message(message=message, chat_id=chat_id, token=token)


def _post_message(message, chat_id, token):
    """
    Send a message to a Telegram chat.

    :param chat_id:     The chat id.
    :param message:     The message to send to the telegram chat.
    :param token:       The Telegram API token.
    :return:            Boolean if message was sent successfully.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    parameters = dict()
    if chat_id:
        parameters["chat_id"] = chat_id
    if message:
        parameters["text"] = message

    try:
        response = requests.post(url, data=parameters, timeout=120)
        result = response.json()

        log.debug("Raw response of the telegram request is %s", response)

    except Exception:  # pylint: disable=broad-except
        log.exception("Sending telegram api request failed")
        return False

    # Check if the Telegram Bot API returned successfully.
    if not result.get("ok", False):
        log.debug(
            "Sending telegram api request failed due to error %s (%s)",
            result.get("error_code"),
            result.get("description"),
        )
        return False

    return True

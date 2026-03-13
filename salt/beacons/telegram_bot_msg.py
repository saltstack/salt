"""
Beacon to emit Telegram messages

Requires the python-telegram-bot library

"""

import asyncio
import inspect
import logging

import salt.utils.beacons

try:
    import telegram

    logging.getLogger("telegram").setLevel(logging.CRITICAL)
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

log = logging.getLogger(__name__)


__virtualname__ = "telegram_bot_msg"


async def _async_get_updates(token, **kwargs):
    """
    Asynchronous helper to get updates from Telegram Bot
    """
    async with telegram.Bot(token) as bot:
        return await bot.get_updates(**kwargs)


def _get_updates(token, **kwargs):
    """
    Synchronous wrapper for getting updates, handles both v13 and v20+
    """
    if HAS_TELEGRAM and inspect.iscoroutinefunction(telegram.Bot.get_updates):
        return asyncio.run(_async_get_updates(token, **kwargs))
    else:
        bot = telegram.Bot(token)
        return bot.get_updates(**kwargs)


def __virtual__():
    if HAS_TELEGRAM:
        return __virtualname__
    else:
        err_msg = "telegram library is missing."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg


def validate(config):
    """
    Validate the beacon configuration
    """
    if not isinstance(config, list):
        return False, "Configuration for telegram_bot_msg beacon must be a list."

    config = salt.utils.beacons.list_to_dict(config)

    if not all(
        config.get(required_config) for required_config in ["token", "accept_from"]
    ):
        return (
            False,
            "Not all required configuration for telegram_bot_msg are set.",
        )

    if not isinstance(config.get("accept_from"), list):
        return (
            False,
            "Configuration for telegram_bot_msg, "
            "accept_from must be a list of usernames.",
        )

    return True, "Valid beacon configuration."


def beacon(config):
    """
    Emit a dict with a key "msgs" whose value is a list of messages
    sent to the configured bot by one of the allowed usernames.

    .. code-block:: yaml

        beacons:
          telegram_bot_msg:
            - token: "<bot access token>"
            - accept_from:
              - "<valid username>"
            - interval: 10

    """

    config = salt.utils.beacons.list_to_dict(config)

    log.debug("telegram_bot_msg beacon starting")
    ret = []
    output = {}
    output["msgs"] = []

    updates = _get_updates(config["token"], limit=100, timeout=0)

    log.debug("Num updates: %d", len(updates))
    if not updates:
        log.debug("Telegram Bot beacon has no new messages")
        return ret

    latest_update_id = 0
    for update in updates:
        message = update.message

        if update.update_id > latest_update_id:
            latest_update_id = update.update_id

        if message.chat.username in config["accept_from"]:
            output["msgs"].append(message.to_dict())

    # mark in the server that previous messages are processed
    _get_updates(config["token"], offset=latest_update_id + 1)

    log.debug("Emitting %d messages.", len(output["msgs"]))
    if output["msgs"]:
        ret.append(output)
    return ret

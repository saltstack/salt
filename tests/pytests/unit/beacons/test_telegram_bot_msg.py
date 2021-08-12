# Python libs
import datetime
import logging
import time

import pytest

# Salt libs
from salt.beacons import telegram_bot_msg

# Salt testing libs
from tests.support.mock import MagicMock, patch

# Third-party libs
try:
    import telegram

    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(HAS_TELEGRAM is False, reason="telegram is not available"),
]


@pytest.fixture
def configure_loader_modules():
    return {telegram_bot_msg: {}}


def test_validate_empty_config(*args, **kwargs):
    ret = telegram_bot_msg.validate(None)
    assert ret == (False, "Configuration for telegram_bot_msg beacon must be a list.")


def test_validate_missing_accept_from_config(*args, **kwargs):
    ret = telegram_bot_msg.validate([{"token": "bcd"}])
    assert ret == (
        False,
        "Not all required configuration for telegram_bot_msg are set.",
    )


def test_validate_missing_token_config(*args, **kwargs):
    ret = telegram_bot_msg.validate([{"accept_from": []}])
    assert ret == (
        False,
        "Not all required configuration for telegram_bot_msg are set.",
    )


def test_validate_config_not_list_in_accept_from(*args, **kwargs):
    ret = telegram_bot_msg.validate([{"token": "bcd", "accept_from": {"nodict": "1"}}])
    assert ret == (
        False,
        "Configuration for telegram_bot_msg, "
        "accept_from must be a list of "
        "usernames.",
    )


def test_validate_valid_config(*args, **kwargs):
    ret = telegram_bot_msg.validate([{"token": "bcd", "accept_from": ["username"]}])
    assert ret == (True, "Valid beacon configuration.")


def test_call_no_updates():
    with patch("salt.beacons.telegram_bot_msg.telegram") as telegram_api:
        token = "abc"
        config = [{"token": token, "accept_from": ["tester"]}]
        inst = MagicMock(name="telegram.Bot()")
        telegram_api.Bot = MagicMock(name="telegram", return_value=inst)
        inst.get_updates.return_value = []

        ret = telegram_bot_msg.validate(config)
        assert ret == (True, "Valid beacon configuration.")

        ret = telegram_bot_msg.beacon(config)
        telegram_api.Bot.assert_called_once_with(token)
        assert ret == []


def test_call_telegram_return_no_updates_for_user():
    with patch("salt.beacons.telegram_bot_msg.telegram") as telegram_api:
        token = "abc"
        username = "tester"
        config = [{"token": token, "accept_from": [username]}]
        inst = MagicMock(name="telegram.Bot()")
        telegram_api.Bot = MagicMock(name="telegram", return_value=inst)

        log.debug("telegram %s", telegram)
        username = "different_user"
        user = telegram.user.User(id=1, first_name="", username=username, is_bot=True)
        chat = telegram.chat.Chat(1, "private", username=username)
        date = time.mktime(datetime.datetime(2016, 12, 18, 0, 0).timetuple())
        message = telegram.message.Message(
            message_id=1, from_user=user, date=date, chat=chat
        )
        update = telegram.update.Update(update_id=1, message=message)

        inst.get_updates.return_value = [update]

        ret = telegram_bot_msg.validate(config)
        assert ret == (True, "Valid beacon configuration.")

        ret = telegram_bot_msg.beacon(config)
        telegram_api.Bot.assert_called_once_with(token)
        assert ret == []


def test_call_telegram_returning_updates():
    with patch("salt.beacons.telegram_bot_msg.telegram") as telegram_api:
        token = "abc"
        username = "tester"
        config = [{"token": token, "accept_from": [username]}]
        inst = MagicMock(name="telegram.Bot()")
        telegram_api.Bot = MagicMock(name="telegram", return_value=inst)

        user = telegram.User(id=1, first_name="", username=username, is_bot=True)
        chat = telegram.Chat(1, "private", username=username)
        date = time.mktime(datetime.datetime(2016, 12, 18, 0, 0).timetuple())
        message = telegram.Message(message_id=1, from_user=user, date=date, chat=chat)
        update = telegram.update.Update(update_id=1, message=message)

        inst.get_updates.return_value = [update]

        ret = telegram_bot_msg.validate(config)
        assert ret == (True, "Valid beacon configuration.")

        ret = telegram_bot_msg.beacon(config)
        telegram_api.Bot.assert_called_once_with(token)
        assert ret
        assert ret[0]["msgs"][0] == message.to_dict()

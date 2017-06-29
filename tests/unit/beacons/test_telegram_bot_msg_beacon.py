# coding: utf-8

# Python libs
from __future__ import absolute_import
import datetime

# Salt libs
from salt.beacons import telegram_bot_msg

# Salt testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Third-party libs
try:
    import telegram
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False


@skipIf(not HAS_TELEGRAM, 'telegram is not available')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class TelegramBotMsgBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.telegram_bot
    '''
    def setup_loader_modules(self):
        return {telegram_bot_msg: {}}

    def test_validate_empty_config(self, *args, **kwargs):
        ret = telegram_bot_msg.__validate__(None)
        self.assertEqual(ret, (False, ('Configuration for telegram_bot_msg '
                                       'beacon must be a dictionary.')))

    def test_validate_missing_accept_from_config(self, *args, **kwargs):
        ret = telegram_bot_msg.__validate__({
            'token': 'bcd'
        })
        self.assertEqual(ret, (False, ('Not all required configuration for '
                                       'telegram_bot_msg are set.')))

    def test_validate_missing_token_config(self, *args, **kwargs):
        ret = telegram_bot_msg.__validate__({
            'accept_from': []
        })
        self.assertEqual(ret, (False, ('Not all required configuration for '
                                       'telegram_bot_msg are set.')))

    def test_validate_config_not_list_in_accept_from(self, *args, **kwargs):
        ret = telegram_bot_msg.__validate__({
            'token': 'bcd',
            'accept_from': {'nodict': "1"}
        })
        self.assertEqual(ret, (False, ('Configuration for telegram_bot_msg, '
                                       'accept_from must be a list of '
                                       'usernames.')))

    def test_validate_valid_config(self, *args, **kwargs):
        ret = telegram_bot_msg.__validate__({
            'token': 'bcd',
            'accept_from': [
                'username'
            ]
        })
        self.assertEqual(ret, (True, 'Valid beacon configuration.'))

    def test_call_no_updates(self):
        with patch("salt.beacons.telegram_bot_msg.telegram") as telegram_api:
            token = 'abc'
            config = {
                'token': token,
                'accept_from': ['tester']
            }
            inst = MagicMock(name='telegram.Bot()')
            telegram_api.Bot = MagicMock(name='telegram', return_value=inst)
            inst.get_updates.return_value = []

            ret = telegram_bot_msg.beacon(config)

            telegram_api.Bot.assert_called_once_with(token)
            self.assertEqual(ret, [])

    def test_call_telegram_return_no_updates_for_user(self):
        with patch("salt.beacons.telegram_bot_msg.telegram") as telegram_api:
            token = 'abc'
            username = 'tester'
            config = {
                'token': token,
                'accept_from': [username]
            }
            inst = MagicMock(name='telegram.Bot()')
            telegram_api.Bot = MagicMock(name='telegram', return_value=inst)

            username = 'different_user'
            user = telegram.User(id=1, first_name='', username=username)
            chat = telegram.Chat(1, 'private', username=username)
            date = datetime.datetime(2016, 12, 18, 0, 0)
            message = telegram.Message(1, user, date=date, chat=chat)
            update = telegram.update.Update(update_id=1, message=message)

            inst.get_updates.return_value = [update]

            ret = telegram_bot_msg.beacon(config)

            telegram_api.Bot.assert_called_once_with(token)
            self.assertEqual(ret, [])

    def test_call_telegram_returning_updates(self):
        with patch("salt.beacons.telegram_bot_msg.telegram") as telegram_api:
            token = 'abc'
            username = 'tester'
            config = {
                'token': token,
                'accept_from': [username]
            }
            inst = MagicMock(name='telegram.Bot()')
            telegram_api.Bot = MagicMock(name='telegram', return_value=inst)

            user = telegram.User(id=1, first_name='', username=username)
            chat = telegram.Chat(1, 'private', username=username)
            date = datetime.datetime(2016, 12, 18, 0, 0)
            message = telegram.Message(1, user, date=date, chat=chat)
            update = telegram.update.Update(update_id=1, message=message)

            inst.get_updates.return_value = [update]

            ret = telegram_bot_msg.beacon(config)

            telegram_api.Bot.assert_called_once_with(token)
            self.assertTrue(ret)
            self.assertEqual(ret[0]['msgs'][0], message.to_dict())

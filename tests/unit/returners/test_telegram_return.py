"""
    :codeauthor: :email:`Roald Nefs (info@roaldnefs.com)`

    tests.unit.returners.telegram_return_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import salt.returners.telegram_return as telegram
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class TelegramReturnerTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test Telegram Returner
    """

    def setup_loader_modules(self):
        return {telegram: {}}

    def test_returner(self):
        """
        Test to see if the Telegram returner sends a message
        """
        ret = {
            "id": "12345",
            "fun": "mytest.func",
            "fun_args": "myfunc args",
            "jid": "54321",
            "return": "The room is on fire as shes fixing her hair",
        }
        options = {"chat_id": "", "token": ""}

        with patch(
            "salt.returners.telegram_return._get_options",
            MagicMock(return_value=options),
        ), patch.dict(
            "salt.returners.telegram_return.__salt__",
            {"telegram.post_message": MagicMock(return_value=True)},
        ):
            self.assertTrue(telegram.returner(ret))

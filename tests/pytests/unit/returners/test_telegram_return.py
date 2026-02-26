"""
    Test Telegram Returner

    :codeauthor: :email:`Roald Nefs (info@roaldnefs.com)`
"""

import pytest

import salt.returners.telegram_return as telegram
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {telegram: {}}


def test_returner():
    """
    Test to see if the Telegram returner sends a message
    """
    ret: dict[str, str] = {
        "id": "12345",
        "fun": "mytest.func",
        "fun_args": "myfunc args",
        "jid": "54321",
        "return": "The room is on fire as shes fixing her hair",
    }
    options: dict[str, str] = {"chat_id": "", "token": ""}

    with (
        patch(
            "salt.returners.telegram_return._get_options",
            MagicMock(return_value=options),
        ),
        patch.dict(
            "salt.returners.telegram_return.__salt__",
            {"telegram.post_message": MagicMock(return_value=True)},
        ),
    ):
        assert telegram.returner(ret) is True


def test_returner_topics():
    """
    Test to see if the Telegram returner sends a message to specific topic
    """
    ret: dict[str, str] = {
        "id": "12345",
        "fun": "mytest.func",
        "fun_args": "myfunc args",
        "jid": "54321",
        "return": "The room is on fire as shes fixing her hair",
    }
    options: dict[str, str] = {"chat_id": "", "token": "", "thread_id": ""}

    with (
        patch(
            "salt.returners.telegram_return._get_options",
            MagicMock(return_value=options),
        ),
        patch.dict(
            "salt.returners.telegram_return.__salt__",
            {"telegram.post_message": MagicMock(return_value=True)},
        ),
    ):
        assert telegram.returner(ret) is True

import pytest
import salt.beacons.telegram_bot_msg as telegram_beacon
from tests.support.mock import MagicMock, patch


@pytest.fixture
def fake_robot():
    # Create must be true, because the import probably failed
    with patch("salt.beacons.telegram_bot_msg.telegram", create=True) as fake_telegram:
        fake_message = MagicMock()
        fake_message.chat.username = "good username"
        fake_message.to_dict.return_value = {"cool": "message, bro"}
        fake_telegram.Bot.return_value.get_updates.return_value = [
            MagicMock(message=fake_message, edited_message=None, update_id=1),
            MagicMock(message=None, edited_message=fake_message, update_id=2),
            MagicMock(message=None, edited_message=fake_message, update_id=3),
            MagicMock(message=fake_message, edited_message=None, update_id=4),
            MagicMock(message=fake_message, edited_message=None, update_id=5),
            MagicMock(message=fake_message, edited_message=None, update_id=6),
            MagicMock(message=None, edited_message=None, update_id=7),
        ]
        yield fake_telegram


def test_telegram_beacon_should_correctly_return_update_message_or_edited_message(
    fake_robot,
):
    expected_result = [
        {
            "msgs": [
                {"cool": "message, bro"},
                {"cool": "message, bro"},
                {"cool": "message, bro"},
                {"cool": "message, bro"},
                {"cool": "message, bro"},
                {"cool": "message, bro"},
            ]
        },
    ]

    result = telegram_beacon.beacon(
        config=[{"token": "back to brooklyn", "accept_from": "good username"}]
    )

    assert result == expected_result

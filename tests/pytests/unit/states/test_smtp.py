"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.smtp as smtp
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {smtp: {}}


def test_send_msg():
    """
    Test to send a message via SMTP
    """
    name = "This is a salt states module"

    comt = "Need to send message to admin@example.com: This is a salt states module"

    ret = {"name": name, "changes": {}, "result": None, "comment": comt}

    with patch.dict(smtp.__opts__, {"test": True}):
        assert ret == smtp.send_msg(
            name,
            "admin@example.com",
            "Message from Salt",
            "admin@example.com",
            "my-smtp-account",
        )

    comt = "Sent message to admin@example.com: This is a salt states module"

    with patch.dict(smtp.__opts__, {"test": False}):
        mock = MagicMock(return_value=True)
        with patch.dict(smtp.__salt__, {"smtp.send_msg": mock}):
            ret["comment"] = comt
            ret["result"] = True
            assert ret == smtp.send_msg(
                name,
                "admin@example.com",
                "Message from Salt",
                "admin@example.com",
                "my-smtp-account",
            )

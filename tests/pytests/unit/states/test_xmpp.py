"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest

import salt.states.xmpp as xmpp
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {xmpp: {}}


def test_send_msg():
    """
    Test to send a message to an XMPP user
    """
    ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}
    with patch.dict(xmpp.__opts__, {"test": True}):
        ret.update({"comment": "Need to send message to myaccount: salt"})
        assert xmpp.send_msg("salt", "myaccount", "salt@saltstack.com") == ret

    with patch.dict(xmpp.__opts__, {"test": False}):
        mock = MagicMock(return_value=True)
        with patch.dict(
            xmpp.__salt__, {"xmpp.send_msg": mock, "xmpp.send_msg_multi": mock}
        ):
            ret.update({"result": True, "comment": "Sent message to myaccount: salt"})
            assert xmpp.send_msg("salt", "myaccount", "salt@saltstack.com") == ret

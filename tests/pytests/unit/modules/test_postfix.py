"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import pytest

import salt.modules.postfix as postfix
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {postfix: {}}


def test_show_master():
    """
    Test for return a dict of active config values
    """
    with patch.object(postfix, "_parse_master", return_value=({"A": "a"}, ["b"])):
        assert postfix.show_master("path") == {"A": "a"}


def test_set_master():
    """
    Test for set a single config value in the master.cf file
    """
    with patch.object(postfix, "_parse_master", return_value=({"A": "a"}, ["b"])):
        with patch.object(postfix, "_write_conf", return_value=None):
            assert postfix.set_master("a", "b")


def test_show_main():
    """
    Test for return a dict of active config values
    """
    with patch.object(postfix, "_parse_main", return_value=({"A": "a"}, ["b"])):
        assert postfix.show_main("path") == {"A": "a"}


def test_set_main():
    """
    Test for set a single config value in the master.cf file
    """
    with patch.object(postfix, "_parse_main", return_value=({"A": "a"}, ["b"])):
        with patch.object(postfix, "_write_conf", return_value=None):
            assert postfix.set_main("key", "value")


def test_show_queue():
    """
    Test for show contents of the mail queue
    """
    with patch.dict(postfix.__salt__, {"cmd.run": MagicMock(return_value="A\nB")}):
        assert postfix.show_queue() == []

    # Test if get an extra newline in the output
    with patch.dict(postfix.__salt__, {"cmd.run": MagicMock(return_value="A\nB\n")}):
        assert postfix.show_queue() == []


def test_delete():
    """
    Test for delete message(s) from the mail queue
    """
    with patch.object(postfix, "show_queue", return_value={}):
        assert postfix.delete("queue_id") == {
            "result": False,
            "message": "No message in queue with ID queue_id",
        }

    with patch.dict(
        postfix.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        assert postfix.delete("ALL") == {
            "result": True,
            "message": "Successfully removed all messages",
        }


def test_hold():
    """
    Test for set held message(s) in the mail queue to unheld
    """
    with patch.object(postfix, "show_queue", return_value={}):
        assert postfix.hold("queue_id") == {
            "result": False,
            "message": "No message in queue with ID queue_id",
        }

    with patch.dict(
        postfix.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        assert postfix.hold("ALL") == {
            "result": True,
            "message": "Successfully placed all messages on hold",
        }


def test_unhold():
    """
    Test for put message(s) on hold from the mail queue
    """
    with patch.object(postfix, "show_queue", return_value={}):
        assert postfix.unhold("queue_id") == {
            "result": False,
            "message": "No message in queue with ID queue_id",
        }

    with patch.dict(
        postfix.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        assert postfix.unhold("ALL") == {
            "result": True,
            "message": "Successfully set all message as unheld",
        }


def test_requeue():
    """
    Test for requeue message(s) in the mail queue
    """
    with patch.object(postfix, "show_queue", return_value={}):
        assert postfix.requeue("queue_id") == {
            "result": False,
            "message": "No message in queue with ID queue_id",
        }

    with patch.dict(
        postfix.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        assert postfix.requeue("ALL") == {
            "result": True,
            "message": "Successfully requeued all messages",
        }

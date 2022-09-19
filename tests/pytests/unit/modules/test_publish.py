"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import pytest

import salt.modules.publish as publish
from salt.exceptions import SaltReqTimeoutError
from tests.support.mock import MagicMock, patch


class SAuth:
    """
    Mock SAuth class
    """

    def __init__(self, __opts__):
        self.tok = None

    def gen_token(self, tok):
        """
        Mock gen_token method
        """
        self.tok = tok
        return "salt_tok"


class Channel:
    """
    Mock Channel class
    """

    flag = None

    def __init__(self):
        self.tok = None
        self.load = None

    def factory(self, tok):
        """
        Mock factory method
        """
        self.tok = tok
        return Channel()

    def send(self, load):
        """
        Mock send method
        """
        self.load = load
        if self.flag == 1:
            raise SaltReqTimeoutError
        return True

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def configure_loader_modules():
    return {publish: {}}


def test_publish():
    """
    Test if it publish a command from the minion out to other minions.
    """
    assert publish.publish("os:Fedora", "publish.salt") == {}


def test_full_data():
    """
    Test if it return the full data about the publication
    """
    assert publish.publish("*", "publish.salt") == {}


def test_runner():
    """
    Test if it execute a runner on the master and return the data
    from the runner function
    """
    ret = "No access to master. If using salt-call with --local, please remove."
    assert publish.runner("manage.down") == ret
    mock = MagicMock(return_value=True)
    mock_id = MagicMock(return_value="salt_id")
    with patch("salt.crypt.SAuth", return_value=SAuth(publish.__opts__)):
        with patch("salt.channel.client.ReqChannel", Channel()):
            with patch.dict(publish.__opts__, {"master_uri": mock, "id": mock_id}):
                Channel.flag = 0
                assert publish.runner("manage.down")
                Channel.flag = 1
                assert (
                    publish.runner("manage.down")
                    == "'manage.down' runner publish timed out"
                )

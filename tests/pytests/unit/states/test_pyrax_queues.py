"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.pyrax_queues as pyrax_queues
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pyrax_queues: {}}


def test_present():
    """
    Test to ensure the RackSpace queue exists.
    """
    name = "myqueue"
    provider = "my-pyrax"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock_dct = MagicMock(
        side_effect=[
            {provider: {"salt": True}},
            {provider: {"salt": False}},
            {provider: {"salt": False}},
            False,
        ]
    )
    with patch.dict(pyrax_queues.__salt__, {"cloud.action": mock_dct}):
        comt = "{} present.".format(name)
        ret.update({"comment": comt})
        assert pyrax_queues.present(name, provider) == ret

        with patch.dict(pyrax_queues.__opts__, {"test": True}):
            comt = "Rackspace queue myqueue is set to be created."
            ret.update({"comment": comt, "result": None})
            assert pyrax_queues.present(name, provider) == ret

        with patch.dict(pyrax_queues.__opts__, {"test": False}):
            comt = "Failed to create myqueue Rackspace queue."
            ret.update({"comment": comt, "result": False})
            assert pyrax_queues.present(name, provider) == ret


def test_absent():
    """
    Test to ensure the named Rackspace queue is deleted.
    """
    name = "myqueue"
    provider = "my-pyrax"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock_dct = MagicMock(
        side_effect=[{provider: {"salt": False}}, {provider: {"salt": True}}]
    )
    with patch.dict(pyrax_queues.__salt__, {"cloud.action": mock_dct}):
        comt = "myqueue does not exist."
        ret.update({"comment": comt})
        assert pyrax_queues.absent(name, provider) == ret

        with patch.dict(pyrax_queues.__opts__, {"test": True}):
            comt = "Rackspace queue myqueue is set to be removed."
            ret.update({"comment": comt, "result": None})
            assert pyrax_queues.absent(name, provider) == ret

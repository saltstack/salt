"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.zk_concurrency as zk_concurrency
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {zk_concurrency: {}}


def test_lock():
    """
    Test to block state execution until you are able to get the lock
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    with patch.dict(zk_concurrency.__opts__, {"test": True}):
        ret.update({"comment": "Attempt to acquire lock", "result": None})
        assert zk_concurrency.lock("salt", "dude") == ret

    with patch.dict(zk_concurrency.__opts__, {"test": False}):
        mock = MagicMock(return_value=True)
        with patch.dict(zk_concurrency.__salt__, {"zk_concurrency.lock": mock}):
            ret.update({"comment": "lock acquired", "result": True})
            assert zk_concurrency.lock("salt", "dude", "stack") == ret


def test_unlock():
    """
    Test to remove lease from semaphore
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    with patch.dict(zk_concurrency.__opts__, {"test": True}):
        ret.update({"comment": "Released lock if it is here", "result": None})
        assert zk_concurrency.unlock("salt") == ret

    with patch.dict(zk_concurrency.__opts__, {"test": False}):
        mock = MagicMock(return_value=True)
        with patch.dict(zk_concurrency.__salt__, {"zk_concurrency.unlock": mock}):
            ret.update({"comment": "", "result": True})
            assert zk_concurrency.unlock("salt", identifier="stack") == ret


def test_min_party():
    """
    Test to ensure min party of nodes and the blocking behavior
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}

    with patch.dict(zk_concurrency.__opts__, {"test": True}):
        ret.update({"comment": "Attempt to ensure min_party", "result": None})
        assert zk_concurrency.min_party("salt", "dude", 1) == ret

    with patch.dict(zk_concurrency.__opts__, {"test": False}):
        mock = MagicMock(return_value=["1", "2", "3"])
        with patch.dict(
            zk_concurrency.__salt__, {"zk_concurrency.party_members": mock}
        ):
            ret.update({"comment": "Currently 3 nodes, which is >= 2", "result": True})
            assert zk_concurrency.min_party("salt", "dude", 2) == ret
            ret.update(
                {
                    "comment": "Blocked until 2 nodes were available. "
                    + "Unblocked after 3 nodes became available",
                    "result": True,
                }
            )
            assert zk_concurrency.min_party("salt", "dude", 2, True) == ret
            ret.update({"comment": "Currently 3 nodes, which is < 4", "result": False})
            assert zk_concurrency.min_party("salt", "dude", 4) == ret

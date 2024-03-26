import pytest

import salt.states.group as group
from tests.support.mock import MagicMock, patch

__context__ = {}


def ping(): ...


@pytest.fixture
def configure_loader_modules():
    return {group: {"__salt__": {"test.ping": ping}, "__opts__": {"test": False}}}


def test_present_with_non_unique_gid():
    with patch(
        "salt.states.group._changes", MagicMock(side_effect=[False, {}, False])
    ), patch.dict(
        group.__salt__,
        {"group.getent": MagicMock(side_effect=[[], [{"name": "salt", "gid": 1}]])},
    ), patch.dict(
        group.__salt__, {"group.add": MagicMock(return_value=True)}
    ), patch.dict(
        group.__salt__, {"group.info": MagicMock(return_value={"things": "stuff"})}
    ):
        ret = group.present("salt", gid=1, non_unique=True)
        assert ret == {
            "changes": {"things": "stuff"},
            "comment": "New group salt created",
            "name": "salt",
            "result": True,
        }
        ret = group.present("salt", gid=1, non_unique=False)
        assert ret == {
            "changes": {},
            "comment": "Group salt is not present but gid 1 is already taken by group salt",
            "name": "salt",
            "result": False,
        }


def test_present_with_existing_group_and_non_unique_gid():
    with patch(
        "salt.states.group._changes",
        MagicMock(side_effect=[{"gid": 1}, {}, {"gid": 1}, {"gid": 1}]),
    ), patch.dict(
        group.__salt__,
        {
            "group.getent": MagicMock(
                side_effect=[[{"name": "salt", "gid": 1}], [{"name": "salt", "gid": 1}]]
            )
        },
    ), patch.dict(
        group.__salt__, {"group.add": MagicMock(return_value=True)}
    ), patch.dict(
        group.__salt__, {"group.chgid": MagicMock(return_value=True)}
    ), patch.dict(
        group.__salt__, {"group.info": MagicMock(return_value={"things": "stuff"})}
    ):
        ret = group.present("salt", gid=1, non_unique=True)
        assert ret == {
            "changes": {"Final": "All changes applied successfully"},
            "comment": "The following group attributes are set to be changed:\ngid: 1\n",
            "name": "salt",
            "result": True,
        }
        ret = group.present("salt", gid=1, non_unique=False)
        assert ret == {
            "changes": {"Failed": {"gid": 1}},
            "comment": "The following group attributes are set to be changed:\n"
            "gid: 1\n"
            "Some changes could not be applied",
            "name": "salt",
            "result": False,
        }

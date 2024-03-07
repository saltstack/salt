import pytest

import salt.modules.test as testmod
import salt.states.group as group
import salt.utils.platform
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():

    return {
        testmod: {},
        group: {
            "__salt__": {"test.ping": testmod.ping},
            "__opts__": {"test": False},
        },
    }


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


def test_present_with_local():
    group_add_mock = MagicMock(return_value=True)
    group_info_mock = MagicMock(return_value={"things": "stuff"})
    with patch(
        "salt.states.group._changes", MagicMock(side_effect=[False, {}, False])
    ) as changes_mock, patch.dict(
        group.__salt__,
        {
            "group.getent": MagicMock(
                side_effect=[[{"name": "salt", "gid": 1}], [{"name": "salt", "gid": 1}]]
            )
        },
    ), patch.dict(
        group.__salt__, {"group.add": group_add_mock}
    ), patch.dict(
        group.__salt__, {"group.chgid": MagicMock(return_value=True)}
    ), patch.dict(
        group.__salt__, {"group.info": group_info_mock}
    ):
        ret = group.present("salt", gid=1, non_unique=True, local=True)
        assert ret["result"]
        assert changes_mock.call_args_list == [
            call("salt", 1, None, None, None, local=True),
            call("salt", 1, None, None, None, local=True),
        ]
        if salt.utils.platform.is_windows():
            group_info_mock.assert_called_once_with("salt")
            group_add_mock.assert_called_once_with(
                "salt", gid=1, system=False, non_unique=True
            )
        else:
            group_info_mock.assert_called_once_with("salt", root="/")
            group_add_mock.assert_called_once_with(
                "salt", gid=1, system=False, local=True, non_unique=True
            )


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


def test_absent_with_local():
    group_delete_mock = MagicMock(return_value=True)
    group_info_mock = MagicMock(return_value={"things": "stuff"})
    with patch.dict(group.__salt__, {"group.delete": group_delete_mock}), patch.dict(
        group.__salt__, {"group.info": group_info_mock}
    ):
        ret = group.absent("salt", local=True)
        assert ret == {
            "changes": {"salt": ""},
            "comment": "Removed group salt",
            "name": "salt",
            "result": True,
        }
        if salt.utils.platform.is_windows():
            group_info_mock.assert_called_once_with("salt")
            group_delete_mock.assert_called_once_with("salt")
        else:
            group_info_mock.assert_called_once_with("salt", root="/")
            group_delete_mock.assert_called_once_with("salt", local=True)

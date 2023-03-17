"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.states.incron
"""

import pytest

import salt.states.incron as incron
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {incron: {}}


def test_present():
    """
    Test to verifies that the specified incron job is present
    for the specified user.
    """
    name = "salt"
    path = "/home/user"
    mask = "IN_MODIFY"
    cmd = 'echo "$$ $@"'

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    comt4 = "Incron {} for user root failed to commit with error \nabsent".format(name)
    mock_dict = MagicMock(
        return_value={"crons": [{"path": path, "cmd": cmd, "mask": mask}]}
    )
    mock = MagicMock(side_effect=["present", "new", "updated", "absent"])
    with patch.dict(
        incron.__salt__, {"incron.list_tab": mock_dict, "incron.set_job": mock}
    ):
        with patch.dict(incron.__opts__, {"test": True}):
            comt = "Incron {} is set to be added".format(name)
            ret.update({"comment": comt})
            assert incron.present(name, path, mask, cmd) == ret

        with patch.dict(incron.__opts__, {"test": False}):
            comt = "Incron {} already present".format(name)
            ret.update({"comment": comt, "result": True})
            assert incron.present(name, path, mask, cmd) == ret

            comt = "Incron {} added to root's incrontab".format(name)
            ret.update({"comment": comt, "changes": {"root": "salt"}})
            assert incron.present(name, path, mask, cmd) == ret

            comt = "Incron {} updated".format(name)
            ret.update({"comment": comt})
            assert incron.present(name, path, mask, cmd) == ret

            ret.update({"comment": comt4, "result": False, "changes": {}})
            assert incron.present(name, path, mask, cmd) == ret


def test_absent():
    """
    Test to verifies that the specified incron job is absent
    for the specified user.
    """
    name = "salt"
    path = "/home/user"
    mask = "IN_MODIFY"
    cmd = 'echo "$$ $@"'

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    comt4 = "Incron {} for user root failed to commit with error new".format(name)
    mock_dict = MagicMock(
        return_value={"crons": [{"path": path, "cmd": cmd, "mask": mask}]}
    )
    mock = MagicMock(side_effect=["absent", "removed", "new"])
    with patch.dict(
        incron.__salt__, {"incron.list_tab": mock_dict, "incron.rm_job": mock}
    ):
        with patch.dict(incron.__opts__, {"test": True}):
            comt = "Incron {} is absent".format(name)
            ret.update({"comment": comt})
            assert incron.absent(name, path, mask, cmd) == ret

        with patch.dict(incron.__opts__, {"test": False}):
            comt = "Incron {} already absent".format(name)
            ret.update({"comment": comt, "result": True})
            assert incron.absent(name, path, mask, cmd) == ret

            comt = "Incron {} removed from root's crontab".format(name)
            ret.update({"comment": comt, "changes": {"root": "salt"}})
            assert incron.absent(name, path, mask, cmd) == ret

            ret.update({"comment": comt4, "result": False, "changes": {}})
            assert incron.absent(name, path, mask, cmd) == ret

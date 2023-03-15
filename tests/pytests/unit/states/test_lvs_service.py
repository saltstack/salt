"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.lvs_service as lvs_service
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {lvs_service: {}}


def test_present():
    """
    Test to ensure that the named service is present.
    """
    name = "lvsrs"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock_check = MagicMock(
        side_effect=[
            True,
            True,
            True,
            False,
            True,
            False,
            True,
            False,
            False,
            False,
            False,
        ]
    )
    mock_edit = MagicMock(side_effect=[True, False])
    mock_add = MagicMock(side_effect=[True, False])
    with patch.dict(
        lvs_service.__salt__,
        {
            "lvs.check_service": mock_check,
            "lvs.edit_service": mock_edit,
            "lvs.add_service": mock_add,
        },
    ):
        with patch.dict(lvs_service.__opts__, {"test": True}):
            comt = "LVS Service lvsrs is present"
            ret.update({"comment": comt})
            assert lvs_service.present(name) == ret

            comt = "LVS Service lvsrs is present but some options should update"
            ret.update({"comment": comt, "result": None})
            assert lvs_service.present(name) == ret

        with patch.dict(lvs_service.__opts__, {"test": False}):
            comt = "LVS Service lvsrs has been updated"
            ret.update(
                {"comment": comt, "result": True, "changes": {"lvsrs": "Update"}}
            )
            assert lvs_service.present(name) == ret

            comt = "LVS Service lvsrs update failed"
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert lvs_service.present(name) == ret

        with patch.dict(lvs_service.__opts__, {"test": True}):
            comt = "LVS Service lvsrs is not present and needs to be created"
            ret.update({"comment": comt, "result": None})
            assert lvs_service.present(name) == ret

        with patch.dict(lvs_service.__opts__, {"test": False}):
            comt = "LVS Service lvsrs has been created"
            ret.update(
                {"comment": comt, "result": True, "changes": {"lvsrs": "Present"}}
            )
            assert lvs_service.present(name) == ret

            comt = "LVS Service lvsrs create failed(False)"
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert lvs_service.present(name) == ret


def test_absent():
    """
    Test to ensure the LVS Real Server in specified service is absent.
    """
    name = "lvsrs"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock_check = MagicMock(side_effect=[True, True, True, False])
    mock_delete = MagicMock(side_effect=[True, False])
    with patch.dict(
        lvs_service.__salt__,
        {"lvs.check_service": mock_check, "lvs.delete_service": mock_delete},
    ):
        with patch.dict(lvs_service.__opts__, {"test": True}):
            comt = "LVS Service lvsrs is present and needs to be removed"
            ret.update({"comment": comt})
            assert lvs_service.absent(name) == ret

        with patch.dict(lvs_service.__opts__, {"test": False}):
            comt = "LVS Service lvsrs has been removed"
            ret.update(
                {"comment": comt, "result": True, "changes": {"lvsrs": "Absent"}}
            )
            assert lvs_service.absent(name) == ret

            comt = "LVS Service lvsrs removed failed(False)"
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert lvs_service.absent(name) == ret

        comt = "LVS Service lvsrs is not present, so it cannot be removed"
        ret.update({"comment": comt, "result": True})
        assert lvs_service.absent(name) == ret

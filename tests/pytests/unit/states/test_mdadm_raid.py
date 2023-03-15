"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest

import salt.states.mdadm_raid as mdadm
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {mdadm: {}}


def test_present():
    """
    Test to verify that the raid is present
    """
    ret = [
        {
            "changes": {},
            "comment": "Raid salt already present.",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {},
            "comment": (
                "Devices are a mix of RAID constituents with multiple MD_UUIDs:"
                " ['6be5fc45:05802bba:1c2d6722:666f0e03',"
                " 'ffffffff:ffffffff:ffffffff:ffffffff']."
            ),
            "name": "salt",
            "result": False,
        },
        {
            "changes": {},
            "comment": "Raid will be created with: True",
            "name": "salt",
            "result": None,
        },
        {
            "changes": {},
            "comment": "Raid salt failed to be created.",
            "name": "salt",
            "result": False,
        },
        {
            "changes": {"uuid": "6be5fc45:05802bba:1c2d6722:666f0e03"},
            "comment": "Raid salt created.",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {
                "added": ["dev1"],
                "uuid": "6be5fc45:05802bba:1c2d6722:666f0e03",
            },
            "comment": "Raid salt assembled. Added new device dev1 to salt.\n",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {"added": ["dev1"]},
            "comment": "Raid salt already present. Added new device dev1 to salt.\n",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {},
            "comment": "Raid salt failed to be assembled.",
            "name": "salt",
            "result": False,
        },
    ]

    mock_raid_list_exists = MagicMock(
        return_value={"salt": {"uuid": "6be5fc45:05802bba:1c2d6722:666f0e03"}}
    )
    mock_raid_list_missing = MagicMock(return_value={})

    mock_file_access_ok = MagicMock(return_value=True)

    mock_raid_examine_ok = MagicMock(
        return_value={"MD_UUID": "6be5fc45:05802bba:1c2d6722:666f0e03"}
    )
    mock_raid_examine_missing = MagicMock(return_value={})

    mock_raid_create_success = MagicMock(return_value=True)
    mock_raid_create_fail = MagicMock(return_value=False)

    mock_raid_assemble_success = MagicMock(return_value=True)
    mock_raid_assemble_fail = MagicMock(return_value=False)

    mock_raid_add_success = MagicMock(return_value=True)

    mock_raid_save_config = MagicMock(return_value=True)

    with patch.dict(
        mdadm.__salt__,
        {
            "raid.list": mock_raid_list_exists,
            "file.access": mock_file_access_ok,
            "raid.examine": mock_raid_examine_ok,
        },
    ):
        with patch.dict(mdadm.__opts__, {"test": False}):
            assert mdadm.present("salt", 5, "dev0") == ret[0]

    mock_raid_examine_mixed = MagicMock(
        side_effect=[
            {"MD_UUID": "6be5fc45:05802bba:1c2d6722:666f0e03"},
            {"MD_UUID": "ffffffff:ffffffff:ffffffff:ffffffff"},
        ]
    )
    with patch.dict(
        mdadm.__salt__,
        {
            "raid.list": mock_raid_list_missing,
            "file.access": mock_file_access_ok,
            "raid.examine": mock_raid_examine_mixed,
        },
    ):
        with patch.dict(mdadm.__opts__, {"test": False}):
            assert mdadm.present("salt", 5, ["dev0", "dev1"]) == ret[1]

    with patch.dict(
        mdadm.__salt__,
        {
            "raid.list": mock_raid_list_missing,
            "file.access": mock_file_access_ok,
            "raid.examine": mock_raid_examine_missing,
            "raid.create": mock_raid_create_success,
        },
    ):
        with patch.dict(mdadm.__opts__, {"test": True}):
            assert mdadm.present("salt", 5, "dev0") == ret[2]

    with patch.dict(
        mdadm.__salt__,
        {
            "raid.list": mock_raid_list_missing,
            "file.access": mock_file_access_ok,
            "raid.examine": mock_raid_examine_missing,
            "raid.create": mock_raid_create_fail,
        },
    ):
        with patch.dict(mdadm.__opts__, {"test": False}):
            assert mdadm.present("salt", 5, "dev0") == ret[3]

    mock_raid_list_create = MagicMock(
        side_effect=[{}, {"salt": {"uuid": "6be5fc45:05802bba:1c2d6722:666f0e03"}}]
    )
    with patch.dict(
        mdadm.__salt__,
        {
            "raid.list": mock_raid_list_create,
            "file.access": mock_file_access_ok,
            "raid.examine": mock_raid_examine_missing,
            "raid.create": mock_raid_create_success,
            "raid.save_config": mock_raid_save_config,
        },
    ):
        with patch.dict(mdadm.__opts__, {"test": False}):
            assert mdadm.present("salt", 5, "dev0") == ret[4]

    mock_raid_examine_replaced = MagicMock(
        side_effect=[{"MD_UUID": "6be5fc45:05802bba:1c2d6722:666f0e03"}, {}]
    )
    mock_raid_list_create = MagicMock(
        side_effect=[{}, {"salt": {"uuid": "6be5fc45:05802bba:1c2d6722:666f0e03"}}]
    )
    with patch.dict(
        mdadm.__salt__,
        {
            "raid.list": mock_raid_list_create,
            "file.access": mock_file_access_ok,
            "raid.examine": mock_raid_examine_replaced,
            "raid.assemble": mock_raid_assemble_success,
            "raid.add": mock_raid_add_success,
            "raid.save_config": mock_raid_save_config,
        },
    ):
        with patch.dict(mdadm.__opts__, {"test": False}):
            assert mdadm.present("salt", 5, ["dev0", "dev1"]) == ret[5]

    mock_raid_examine_replaced = MagicMock(
        side_effect=[{"MD_UUID": "6be5fc45:05802bba:1c2d6722:666f0e03"}, {}]
    )
    with patch.dict(
        mdadm.__salt__,
        {
            "raid.list": mock_raid_list_exists,
            "file.access": mock_file_access_ok,
            "raid.examine": mock_raid_examine_replaced,
            "raid.add": mock_raid_add_success,
            "raid.save_config": mock_raid_save_config,
        },
    ):
        with patch.dict(mdadm.__opts__, {"test": False}):
            assert mdadm.present("salt", 5, ["dev0", "dev1"]) == ret[6]

    mock_raid_examine_replaced = MagicMock(
        side_effect=[{"MD_UUID": "6be5fc45:05802bba:1c2d6722:666f0e03"}, {}]
    )
    with patch.dict(
        mdadm.__salt__,
        {
            "raid.list": mock_raid_list_missing,
            "file.access": mock_file_access_ok,
            "raid.examine": mock_raid_examine_replaced,
            "raid.assemble": mock_raid_assemble_fail,
        },
    ):
        with patch.dict(mdadm.__opts__, {"test": False}):
            assert mdadm.present("salt", 5, ["dev0", "dev1"]) == ret[7]


def test_absent():
    """
    Test to verify that the raid is absent
    """
    ret = [
        {
            "changes": {},
            "comment": "Raid salt already absent",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {},
            "comment": "Raid saltstack is set to be destroyed",
            "name": "saltstack",
            "result": None,
        },
        {
            "changes": {},
            "comment": "Raid saltstack has been destroyed",
            "name": "saltstack",
            "result": True,
        },
    ]

    mock = MagicMock(return_value=["saltstack"])
    with patch.dict(mdadm.__salt__, {"raid.list": mock}):
        assert mdadm.absent("salt") == ret[0]

        with patch.dict(mdadm.__opts__, {"test": True}):
            assert mdadm.absent("saltstack") == ret[1]

        with patch.dict(mdadm.__opts__, {"test": False}):
            mock = MagicMock(return_value=True)
            with patch.dict(mdadm.__salt__, {"raid.destroy": mock}):
                assert mdadm.absent("saltstack") == ret[2]

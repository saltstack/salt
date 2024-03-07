"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.cloud as cloud
import salt.utils.cloud
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {cloud: {}}


def test_present():
    """
    Test to spin up a single instance on a cloud provider, using salt-cloud.
    """
    name = "mycloud"
    cloud_provider = "my_cloud_provider"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, False])
    mock_bool = MagicMock(side_effect=[True, False, False])
    mock_dict = MagicMock(return_value={"cloud": "saltcloud"})
    with patch.dict(
        cloud.__salt__,
        {
            "cmd.retcode": mock,
            "cloud.has_instance": mock_bool,
            "cloud.create": mock_dict,
        },
    ):
        comt = "onlyif condition is false"
        ret.update({"comment": comt})
        assert cloud.present(name, cloud_provider, onlyif=False) == ret

        assert cloud.present(name, cloud_provider, onlyif="") == ret

        comt = "unless condition is true"
        ret.update({"comment": comt})
        assert cloud.present(name, cloud_provider, unless=True) == ret

        assert cloud.present(name, cloud_provider, unless="") == ret

        comt = f"Already present instance {name}"
        ret.update({"comment": comt})
        assert cloud.present(name, cloud_provider) == ret

        with patch.dict(cloud.__opts__, {"test": True}):
            comt = f"Instance {name} needs to be created"
            ret.update({"comment": comt, "result": None})
            assert cloud.present(name, cloud_provider) == ret

        with patch.dict(cloud.__opts__, {"test": False}):
            comt = (
                "Created instance mycloud using provider "
                "my_cloud_provider and the following options: {}"
            )
            ret.update(
                {"comment": comt, "result": True, "changes": {"cloud": "saltcloud"}}
            )
            assert cloud.present(name, cloud_provider) == ret


def test_absent():
    """
    Test to ensure that no instances with the specified names exist.
    """
    name = "mycloud"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, False])
    mock_bool = MagicMock(side_effect=[False, True, True])
    mock_dict = MagicMock(return_value={"cloud": "saltcloud"})
    with patch.dict(
        cloud.__salt__,
        {
            "cmd.retcode": mock,
            "cloud.has_instance": mock_bool,
            "cloud.destroy": mock_dict,
        },
    ):
        comt = "onlyif condition is false"
        ret.update({"comment": comt})
        assert cloud.absent(name, onlyif=False) == ret

        assert cloud.absent(name, onlyif="") == ret

        comt = "unless condition is true"
        ret.update({"comment": comt})
        assert cloud.absent(name, unless=True) == ret

        assert cloud.absent(name, unless="") == ret

        comt = f"Already absent instance {name}"
        ret.update({"comment": comt})
        assert cloud.absent(name) == ret

        with patch.dict(cloud.__opts__, {"test": True}):
            comt = f"Instance {name} needs to be destroyed"
            ret.update({"comment": comt, "result": None})
            assert cloud.absent(name) == ret

        with patch.dict(cloud.__opts__, {"test": False}):
            comt = ("Destroyed instance {}").format(name)
            ret.update(
                {"comment": comt, "result": True, "changes": {"cloud": "saltcloud"}}
            )
            assert cloud.absent(name) == ret


def test_profile():
    """
    Test to create a single instance on a cloud provider,
    using a salt-cloud profile.
    """
    name = "mycloud"
    profile = "myprofile"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, False])
    mock_dict = MagicMock(
        side_effect=[
            {"cloud": "saltcloud"},
            {"Not Actioned": True},
            {"Not Actioned": True},
            {"Not Found": True, "Not Actioned/Not Running": True},
        ]
    )
    mock_d = MagicMock(return_value={})
    with patch.dict(
        cloud.__salt__,
        {"cmd.retcode": mock, "cloud.profile": mock_d, "cloud.action": mock_dict},
    ):
        comt = "onlyif condition is false"
        ret.update({"comment": comt})
        assert cloud.profile(name, profile, onlyif=False) == ret

        assert cloud.profile(name, profile, onlyif="") == ret

        comt = "unless condition is true"
        ret.update({"comment": comt})
        assert cloud.profile(name, profile, unless=True) == ret

        assert cloud.profile(name, profile, unless="") == ret

        comt = f"Already present instance {name}"
        ret.update({"comment": comt})
        assert cloud.profile(name, profile) == ret

        with patch.dict(cloud.__opts__, {"test": True}):
            comt = f"Instance {name} needs to be created"
            ret.update({"comment": comt, "result": None})
            assert cloud.profile(name, profile) == ret

        with patch.dict(cloud.__opts__, {"test": False}):
            comt = f"Failed to create instance {name} using profile {profile}"
            ret.update({"comment": comt, "result": False})
            assert cloud.profile(name, profile) == ret

        with patch.dict(cloud.__opts__, {"test": False}):
            comt = f"Failed to create instance {name} using profile {profile}"
            ret.update({"comment": comt, "result": False})
            assert cloud.profile(name, profile) == ret


def test_volume_present():
    """
    Test to check that a block volume exists.
    """
    name = "mycloud"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock = MagicMock(return_value=name)
    mock_lst = MagicMock(side_effect=[[name], [], []])
    with patch.dict(
        cloud.__salt__, {"cloud.volume_list": mock_lst, "cloud.volume_create": mock}
    ):
        with patch.object(salt.utils.cloud, "check_name", MagicMock(return_value=True)):
            comt = "Invalid characters in name."
            ret.update({"comment": comt})
            assert cloud.volume_present(name) == ret

        comt = f"Volume exists: {name}"
        ret.update({"comment": comt, "result": True})
        assert cloud.volume_present(name) == ret

        with patch.dict(cloud.__opts__, {"test": True}):
            comt = f"Volume {name} will be created."
            ret.update({"comment": comt, "result": None})
            assert cloud.volume_present(name) == ret

        with patch.dict(cloud.__opts__, {"test": False}):
            comt = f"Volume {name} was created"
            ret.update(
                {
                    "comment": comt,
                    "result": True,
                    "changes": {"old": None, "new": name},
                }
            )
            assert cloud.volume_present(name) == ret


def test_volume_absent():
    """
    Test to check that a block volume exists.
    """
    name = "mycloud"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock = MagicMock(return_value=False)
    mock_lst = MagicMock(side_effect=[[], [name], [name]])
    with patch.dict(
        cloud.__salt__, {"cloud.volume_list": mock_lst, "cloud.volume_delete": mock}
    ):
        with patch.object(salt.utils.cloud, "check_name", MagicMock(return_value=True)):
            comt = "Invalid characters in name."
            ret.update({"comment": comt})
            assert cloud.volume_absent(name) == ret

        comt = "Volume is absent."
        ret.update({"comment": comt, "result": True})
        assert cloud.volume_absent(name) == ret

        with patch.dict(cloud.__opts__, {"test": True}):
            comt = f"Volume {name} will be deleted."
            ret.update({"comment": comt, "result": None})
            assert cloud.volume_absent(name) == ret

        with patch.dict(cloud.__opts__, {"test": False}):
            comt = f"Volume {name} failed to delete."
            ret.update({"comment": comt, "result": False})
            assert cloud.volume_absent(name) == ret


def test_volume_attached():
    """
    Test to check if a block volume is attached.
    """
    name = "mycloud"
    server_name = "mycloud_server"
    disk_name = "trogdor"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock = MagicMock(return_value=False)
    mock_dict = MagicMock(
        side_effect=[
            {name: {"name": disk_name, "attachments": True}},
            {},
            {name: {"name": disk_name, "attachments": False}},
            {name: {"name": disk_name, "attachments": False}},
            {name: {"name": disk_name, "attachments": False}},
        ]
    )
    with patch.dict(
        cloud.__salt__, {"cloud.volume_list": mock_dict, "cloud.action": mock}
    ):
        with patch.object(
            salt.utils.cloud,
            "check_name",
            MagicMock(side_effect=[True, False, True]),
        ):
            comt = "Invalid characters in name."
            ret.update({"comment": comt})
            assert cloud.volume_attached(name, server_name) == ret

            ret.update({"name": server_name})
            assert cloud.volume_attached(name, server_name) == ret

        comt = f"Volume {disk_name} is already attached: True"
        ret.update({"comment": comt, "result": True})
        assert cloud.volume_attached(name, server_name) == ret

        comt = f"Volume {name} does not exist"
        ret.update({"comment": comt, "result": False})
        assert cloud.volume_attached(name, server_name) == ret

        comt = f"Server {server_name} does not exist"
        ret.update({"comment": comt, "result": False})
        assert cloud.volume_attached(name, server_name) == ret

        mock = MagicMock(return_value=True)
        with patch.dict(
            cloud.__salt__, {"cloud.action": mock, "cloud.volume_attach": mock}
        ):
            with patch.dict(cloud.__opts__, {"test": True}):
                comt = f"Volume {name} will be will be attached."
                ret.update({"comment": comt, "result": None})
                assert cloud.volume_attached(name, server_name) == ret

            with patch.dict(cloud.__opts__, {"test": False}):
                comt = f"Volume {name} was created"
                ret.update(
                    {
                        "comment": comt,
                        "result": True,
                        "changes": {
                            "new": True,
                            "old": {"name": disk_name, "attachments": False},
                        },
                    }
                )
                assert cloud.volume_attached(name, server_name) == ret


def test_volume_detached():
    """
    Test to check if a block volume is detached.
    """
    name = "mycloud"
    server_name = "mycloud_server"
    disk_name = "trogdor"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock = MagicMock(return_value=False)
    mock_dict = MagicMock(
        side_effect=[
            {name: {"name": disk_name, "attachments": False}},
            {},
            {name: {"name": disk_name, "attachments": True}},
            {name: {"name": disk_name, "attachments": True}},
            {name: {"name": disk_name, "attachments": True}},
        ]
    )
    with patch.dict(
        cloud.__salt__, {"cloud.volume_list": mock_dict, "cloud.action": mock}
    ):
        with patch.object(
            salt.utils.cloud,
            "check_name",
            MagicMock(side_effect=[True, False, True]),
        ):
            comt = "Invalid characters in name."
            ret.update({"comment": comt})
            assert cloud.volume_detached(name, server_name) == ret

            ret.update({"name": server_name})
            assert cloud.volume_detached(name, server_name) == ret

        comt = f"Volume {disk_name} is not currently attached to anything."
        ret.update({"comment": comt, "result": True})
        assert cloud.volume_detached(name, server_name) == ret

        comt = f"Volume {name} does not exist"
        ret.update({"comment": comt})
        assert cloud.volume_detached(name, server_name) == ret

        comt = f"Server {server_name} does not exist"
        ret.update({"comment": comt})
        assert cloud.volume_detached(name, server_name) == ret

        mock = MagicMock(return_value=True)
        with patch.dict(
            cloud.__salt__, {"cloud.action": mock, "cloud.volume_detach": mock}
        ):
            with patch.dict(cloud.__opts__, {"test": True}):
                comt = f"Volume {name} will be will be detached."
                ret.update({"comment": comt, "result": None})
                assert cloud.volume_detached(name, server_name) == ret

            with patch.dict(cloud.__opts__, {"test": False}):
                comt = f"Volume {name} was created"
                ret.update(
                    {
                        "comment": comt,
                        "result": True,
                        "changes": {
                            "new": True,
                            "old": {"name": disk_name, "attachments": True},
                        },
                    }
                )
                assert cloud.volume_detached(name, server_name) == ret

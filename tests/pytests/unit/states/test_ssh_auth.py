"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.ssh_auth as ssh_auth
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {ssh_auth: {}}


def test_present():
    """
    Test to verifies that the specified SSH key
    is present for the specified user.
    """
    name = "sshkeys"
    user = "root"
    source = "salt://ssh_keys/id_rsa.pub"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(return_value="exists")
    mock_data = MagicMock(side_effect=["replace", "new"])
    with patch.dict(
        ssh_auth.__salt__, {"ssh.check_key": mock, "ssh.set_auth_key": mock_data}
    ):
        with patch.dict(ssh_auth.__opts__, {"test": True}):
            comt = "The authorized host key sshkeys is already present for user root"
            ret.update({"comment": comt})
            assert ssh_auth.present(name, user, source) == ret

        with patch.dict(ssh_auth.__opts__, {"test": False}):
            comt = "The authorized host key sshkeys for user root was updated"
            ret.update({"comment": comt, "changes": {name: "Updated"}})
            assert ssh_auth.present(name, user, source) == ret

            comt = "The authorized host key sshkeys for user root was added"
            ret.update({"comment": comt, "changes": {name: "New"}})
            assert ssh_auth.present(name, user, source) == ret


def test_absent():
    """
    Test to verifies that the specified SSH key is absent.
    """
    name = "sshkeys"
    user = "root"
    source = "salt://ssh_keys/id_rsa.pub"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    mock = MagicMock(
        side_effect=["User authorized keys file not present", "Key removed"]
    )
    mock_up = MagicMock(side_effect=["update", "updated"])
    with patch.dict(
        ssh_auth.__salt__, {"ssh.rm_auth_key": mock, "ssh.check_key": mock_up}
    ):
        with patch.dict(ssh_auth.__opts__, {"test": True}):
            comt = "Key sshkeys for user root is set for removal"
            ret.update({"comment": comt})
            assert ssh_auth.absent(name, user, source) == ret

            comt = "Key is already absent"
            ret.update({"comment": comt, "result": True})
            assert ssh_auth.absent(name, user, source) == ret

        with patch.dict(ssh_auth.__opts__, {"test": False}):
            comt = "User authorized keys file not present"
            ret.update({"comment": comt, "result": False})
            assert ssh_auth.absent(name, user, source) == ret

            comt = "Key removed"
            ret.update({"comment": comt, "result": True, "changes": {name: "Removed"}})
            assert ssh_auth.absent(name, user, source) == ret


def test_manage():
    """
    Test to verifies that the specified SSH key is absent.
    """
    user = "root"
    ret = {"name": "", "changes": {}, "result": None, "comment": ""}

    mock_rm = MagicMock(
        side_effect=["User authorized keys file not present", "Key removed"]
    )
    mock_up = MagicMock(side_effect=["update", "updated"])
    mock_set = MagicMock(side_effect=["replace", "new"])
    mock_keys = MagicMock(
        return_value={
            "somekey": {
                "enc": "ssh-rsa",
                "comment": "user@host",
                "options": [],
                "fingerprint": "b7",
            }
        }
    )
    with patch.dict(
        ssh_auth.__salt__,
        {
            "ssh.rm_auth_key": mock_rm,
            "ssh.set_auth_key": mock_set,
            "ssh.check_key": mock_up,
            "ssh.auth_keys": mock_keys,
        },
    ):
        with patch("salt.states.ssh_auth.present") as call_mocked_present:
            mock_present = {"comment": "", "changes": {}, "result": None}
            call_mocked_present.return_value = mock_present
            with patch.dict(ssh_auth.__opts__, {"test": True}):
                assert ssh_auth.manage("sshid", ["somekey"], user) == ret

                comt = "somekey Key set for removal"
                ret.update({"comment": comt})
                assert ssh_auth.manage("sshid", [], user) == ret

        with patch("salt.states.ssh_auth.present") as call_mocked_present:
            mock_present = {"comment": "", "changes": {}, "result": True}
            call_mocked_present.return_value = mock_present
            with patch.dict(ssh_auth.__opts__, {"test": False}):
                ret = {"name": "", "changes": {}, "result": True, "comment": ""}
                assert ssh_auth.manage("sshid", ["somekey"], user) == ret

                with patch("salt.states.ssh_auth.absent") as call_mocked_absent:
                    mock_absent = {"comment": "Key removed"}
                    call_mocked_absent.return_value = mock_absent
                    ret.update(
                        {
                            "comment": "",
                            "result": True,
                            "changes": {"somekey": "Key removed"},
                        }
                    )
                    assert ssh_auth.manage("sshid", ["addkey"], user) == ret

        # add a key
        with patch("salt.states.ssh_auth.present") as call_mocked_present:
            mock_present = {
                "comment": (
                    "The authorized host key newkey for user {} was added".format(user)
                ),
                "changes": {"newkey": "New"},
                "result": True,
            }
            call_mocked_present.return_value = mock_present
            with patch.dict(ssh_auth.__opts__, {"test": False}):
                ret = {
                    "name": "",
                    "changes": {"newkey": "New"},
                    "result": True,
                    "comment": "",
                }
                assert ssh_auth.manage("sshid", ["newkey", "somekey"], user) == ret

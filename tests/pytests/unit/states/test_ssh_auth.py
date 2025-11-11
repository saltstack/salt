"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.ssh_auth as ssh_auth
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {ssh_auth: {"__env__": "base"}}


@pytest.fixture()
def enc_types():
    # This list is from sshd manual page of openssh 8.7
    return [
        "sk-ecdsa-sha2-nistp256@openssh.com",
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "sk-ssh-ed25519@openssh.com",
        "ssh-ed25519",
        "ssh-dss",
        "ssh-rsa",
    ]


def test__present_test(enc_types):
    """
    Test to verify if many encryption key types are accepted by ssh_auth._present_test
    """
    user = "user"
    key = "1ABCDXXXXXXXXXXXXXXXXXXXXXXXXXXXX="
    comment = "user@example.internal"
    name_list = []
    expected_calls = []
    for enc in enc_types:
        name_list.append(f"{enc} {key} {comment}")
        expected_calls.append(
            call(
                user,
                key,
                enc,
                comment,
                [],
                config=".ssh/authorized_keys",
                fingerprint_hash_type=None,
            )
        )

    mock_check_key = MagicMock(return_value="update")

    with patch.dict(ssh_auth.__salt__, {"ssh.check_key": mock_check_key}):
        with patch.dict(ssh_auth.__opts__, {"test": True}):
            for name in name_list:
                ret = None, f"Key {key} for user {user} is set to be updated"
                assert (
                    ssh_auth._present_test(
                        user, name, enc, comment, [], "", ".ssh/authorized_keys", None
                    )
                    == ret
                )
            mock_check_key.assert_has_calls(expected_calls)


def test__absent_test(enc_types):
    """
    Test to verify if many encryption key types are accepted by ssh_auth._absent_test
    """
    user = "user"
    key = "1ABCDXXXXXXXXXXXXXXXXXXXXXXXXXXXX="
    comment = "user@example.internal"
    name_list = []
    expected_calls = []
    for enc in enc_types:
        name_list.append(f"{enc} {key} {comment}")
        expected_calls.append(
            call(
                user,
                key,
                enc,
                comment,
                [],
                config=".ssh/authorized_keys",
                fingerprint_hash_type=None,
            )
        )

    mock_check_key = MagicMock(return_value="update")

    with patch.dict(ssh_auth.__salt__, {"ssh.check_key": mock_check_key}):
        with patch.dict(ssh_auth.__opts__, {"test": True}):
            for name in name_list:
                ret = None, f"Key {key} for user {user} is set for removal"
                assert (
                    ssh_auth._absent_test(
                        user, name, enc, comment, [], "", ".ssh/authorized_keys", None
                    )
                    == ret
                )
            mock_check_key.assert_has_calls(expected_calls)


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


def test_present_with_source():
    """
    Test to check if ssh.set_auth_key_from_file is called with the correct parameters
    """
    user = "user"
    source = "salt://fakefile"
    config = ".ssh/authorized_keys"

    mock_cp_get_url = MagicMock(return_value=True)
    mock_auth_key_from_file = MagicMock(return_value="new")

    with patch.dict(
        ssh_auth.__salt__,
        {
            "cp.get_url": mock_cp_get_url,
            "ssh.set_auth_key_from_file": mock_auth_key_from_file,
        },
    ):
        with patch.dict(ssh_auth.__opts__, {"test": False}):
            name = "Call Without Options"
            ret = {
                "name": name,
                "changes": {name: "New"},
                "result": True,
                "comment": f"The authorized host key {name} for user {user} was added",
            }
            assert ssh_auth.present(name, user, source=source) == ret
            mock_auth_key_from_file.assert_called_with(
                "user",
                "salt://fakefile",
                config=".ssh/authorized_keys",
                saltenv="base",
                fingerprint_hash_type=None,
                options=None,
            )
            name = "Call With Options"
            ret = {
                "name": name,
                "changes": {name: "New"},
                "result": True,
                "comment": f"The authorized host key {name} for user {user} was added",
            }
            assert (
                ssh_auth.present(name, user, source=source, options=["no-pty"]) == ret
            )
            mock_auth_key_from_file.assert_called_with(
                "user",
                "salt://fakefile",
                config=".ssh/authorized_keys",
                saltenv="base",
                fingerprint_hash_type=None,
                options=["no-pty"],
            )


def test_present_different_key_types_are_accepted(enc_types):
    """
    Test to verify if many encryption key types are accepted by ssh_auth.present
    """
    user = "user"
    key = "1ABCDXXXXXXXXXXXXXXXXXXXXXXXXXXXX="
    comment = "user@example.internal"
    name_list = []
    expected_calls = []
    for enc in enc_types:
        name_list.append(f"{enc} {key} {comment}")
        expected_calls.append(
            call(
                user,
                key,
                enc,
                comment,
                [],
                "",
                ".ssh/authorized_keys",
                None,
            )
        )

    with patch.object(
        ssh_auth, "_present_test", return_value=[None, "Key is to be added"]
    ) as mock__present_test:
        # it's tested with `test: True` because this already tests the fullkey regexp
        with patch.dict(ssh_auth.__opts__, {"test": True}):
            for name in name_list:
                ret = {
                    "name": name,
                    "changes": {},
                    "result": None,
                    "comment": "Key is to be added",
                }
                assert ssh_auth.present(name, user) == ret
            mock__present_test.assert_has_calls(expected_calls)


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


def test_absent_with_source():
    """
    Test to check if ssh.rm_auth_key_from_file is called with the correct parameters
    """
    user = "user"
    source = "salt://fakefile"
    config = ".ssh/authorized_keys"

    mock_cp_get_url = MagicMock(return_value=True)
    mock_auth_key_from_file = MagicMock(return_value="Key removed")

    with patch.dict(
        ssh_auth.__salt__,
        {
            "cp.get_url": mock_cp_get_url,
            "ssh.rm_auth_key_from_file": mock_auth_key_from_file,
        },
    ):
        with patch.dict(ssh_auth.__opts__, {"test": False}):
            name = "Call Absent With Source"
            ret = {
                "name": name,
                "changes": {name: "Removed"},
                "result": True,
                "comment": "Key removed",
            }
            assert ssh_auth.absent(name, user, source=source) == ret
            mock_auth_key_from_file.assert_called_with(
                "user",
                "salt://fakefile",
                ".ssh/authorized_keys",
                saltenv="base",
                fingerprint_hash_type=None,
            )


def test_absent_with_different_key_types_are_accepted(enc_types):
    """
    Test to verify if many encription key types are accepted
    """
    user = "user"
    key = "1ABCDXXXXXXXXXXXXXXXXXXXXXXXXXXXX="
    comment = "user@example.internal"
    name_list = []
    expected_calls = []
    for enc in enc_types:
        name_list.append(f"{enc} {key} {comment}")
        expected_calls.append(
            call(
                user,
                key,
                config=".ssh/authorized_keys",
                fingerprint_hash_type=None,
            )
        )

    mock_rm_test = MagicMock(return_value="Key removed")

    with patch.dict(ssh_auth.__salt__, {"ssh.rm_auth_key": mock_rm_test}):
        # it's tested with `test: False` because the fullkey regexp is only in the actual execution
        with patch.dict(ssh_auth.__opts__, {"test": False}):
            for name in name_list:
                ret = {
                    "name": name,
                    "changes": {key: "Removed"},
                    "result": True,
                    "comment": "Key removed",
                }
                assert ssh_auth.absent(name, user) == ret
            mock_rm_test.assert_has_calls(expected_calls)


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
                    f"The authorized host key newkey for user {user} was added"
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

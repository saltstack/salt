import pytest

import salt.client.ssh.wrapper as wrap


def test_parse_ret_permission_denied_scp():
    """
    Ensure that permission denied errors are raised when scp fails to copy
    a file to a target because of an authentication failure.
    """
    stdout = "\rroot@192.168.1.187's password: \n\rroot@192.168.1.187's password: \n\rroot@192.168.1.187's password: \n"
    stderr = "Permission denied, please try again.\nPermission denied, please try again.\nroot@192.168.1.187: Permission denied (publickey,gssapi-keyex,gssapi-with-micimport pudb; pu.dbassword).\nscp: Connection closed\n"
    retcode = 255

    with pytest.raises(wrap.SSHPermissionDeniedError) as exc:
        wrap.parse_ret(stdout, stderr, retcode)
    ret = exc.value.to_ret()
    assert "_error" in ret
    assert ret["_error"] == "Permission denied"
    assert "stdout" in ret
    assert "stderr" in ret
    assert "Permission denied (publickey" in ret["stderr"]
    assert "retcode" in ret
    assert ret["retcode"] == 255


def test_parse_ret_permission_denied_because_of_permissions():
    """
    Ensure that permission denied errors are NOT raised when scp fails
    to copy a file to a target due to missing permissions of the user account.
    The PermissionDeniedError should be exclusive to authentication failures and
    not apply to authorization ones.
    """
    stdout = ""
    stderr = 'scp: dest open "/tmp/preflight.sh": Permission denied\nscp: failed to upload file /etc/salt/preflight.sh to /tmp/preflight.sh\n'
    retcode = 1

    try:
        wrap.parse_ret(stdout, stderr, retcode)
    except wrap.SSHPermissionDeniedError:
        pytest.fail("This should not have resulted in an SSHPermissionDeniedError")
    except wrap.SSHCommandExecutionError:
        pass

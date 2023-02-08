import pytest


def test_salt_call_local(salt_call_cli):
    """
    Test salt-call --local test.ping
    """
    ret = salt_call_cli.run("--local", "test.ping")
    assert ret.data is True
    assert ret.returncode == 0


def test_salt_call(salt_call_cli):
    """
    Test salt-call test.ping
    """
    ret = salt_call_cli.run("test.ping")
    assert ret.data is True
    assert ret.returncode == 0


def test_sls(salt_call_cli):
    """
    Test calling a sls file
    """
    ret = salt_call_cli.run("state.apply", "test")
    assert ret.data, ret
    sls_ret = ret.data[next(iter(ret.data))]
    assert sls_ret["changes"]["testing"]["new"] == "Something pretended to change"
    assert ret.returncode == 0


def test_salt_call_local_sys_doc_none(salt_call_cli):
    """
    Test salt-call --local sys.doc none
    """
    ret = salt_call_cli.run("--local", "sys.doc", "none")
    assert not ret.data
    assert ret.returncode == 0


def test_salt_call_local_sys_doc_aliases(salt_call_cli):
    """
    Test salt-call --local sys.doc aliases
    """
    ret = salt_call_cli.run("--local", "sys.doc", "aliases.list_aliases")
    assert "aliases.list_aliases" in ret.data
    assert ret.returncode == 0


@pytest.mark.skip_on_windows()
def test_salt_call_cmd_run_id_runas(salt_call_cli, test_account, caplog):
    """
    Test salt-call --local cmd_run id with runas
    """
    ret = salt_call_cli.run("--local", "cmd.run", "id", runas=test_account.username)
    assert "Environment could not be retrieved for user" not in caplog.text
    assert str(test_account.uid) in ret.stdout
    assert str(test_account.gid) in ret.stdout

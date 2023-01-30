import os.path

import pytest


def test_salt_call_local(install_salt):
    """
    Test salt-call --local test.ping
    """
    test_bin = os.path.join(*install_salt.binary_paths["call"])
    ret = install_salt.proc.run(test_bin, "--local", "test.ping")
    assert "True" in ret.stdout
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


def test_salt_call_local_sys_doc_none(install_salt):
    """
    Test salt-call --local sys.doc none
    """
    test_bin = os.path.join(*install_salt.binary_paths["call"])
    ret = install_salt.proc.run(test_bin, "--local", "sys.doc", "none")
    assert "local:\n    ----------\n" == ret.stdout
    assert ret.returncode == 0


def test_salt_call_local_sys_doc_aliases(install_salt):
    """
    Test salt-call --local sys.doc aliases
    """
    test_bin = os.path.join(*install_salt.binary_paths["call"])
    ret = install_salt.proc.run(test_bin, "--local", "sys.doc", "aliases.list_aliases")
    assert "aliases.list_aliases" in ret.stdout
    assert ret.returncode == 0


@pytest.mark.skip_on_windows()
def test_salt_call_cmd_run_id_runas(install_salt, test_account, caplog):
    """
    Test salt-call --local cmd_run id with runas
    """
    test_bin = os.path.join(*install_salt.binary_paths["call"])
    ret = install_salt.proc.run(test_bin, "--local", "id", runas=test_account.username)
    assert "Environment could not be retrieved for user" not in caplog.text
    assert str(test_account.uid) in ret.stdout
    assert str(test_account.gid) in ret.stdout

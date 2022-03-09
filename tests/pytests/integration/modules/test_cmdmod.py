import pytest


@pytest.fixture(scope="module")
def non_root_account():
    with pytest.helpers.create_account() as account:
        yield account


@pytest.mark.skip_if_not_root
def test_exec_code_all(salt_call_cli, non_root_account):
    ret = salt_call_cli.run(
        "cmd.exec_code_all", "bash", "echo good", runas=non_root_account.username
    )
    assert ret.exitcode == 0

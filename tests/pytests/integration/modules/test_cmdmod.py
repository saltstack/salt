import pytest

import salt.utils.platform

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def non_root_account():
    with pytest.helpers.create_account() as account:
        yield account


@pytest.fixture
def shell():
    if salt.utils.platform.is_windows():
        return "cmd"
    else:
        return "bash"


@pytest.mark.skip_if_not_root
def test_exec_code_all(salt_call_cli, non_root_account, shell):
    ret = salt_call_cli.run(
        "cmd.exec_code_all", shell, "echo good", runas=non_root_account.username
    )
    assert ret.returncode == 0


@pytest.mark.skip_on_windows(reason="No vt on Windows")
def test_long_stdout(salt_cli, salt_minion):
    echo_str = "salt" * 1000
    ret = salt_cli.run(
        "cmd.run", f"echo {echo_str}", use_vt=True, minion_tgt=salt_minion.id
    )
    assert ret.returncode == 0
    assert len(ret.data.strip()) == len(echo_str)

import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


def test_state_with_import(salt_ssh_cli, state_tree):
    """
    verify salt-ssh can use imported map files in states
    """
    ret = salt_ssh_cli.run("state.sls", "test")
    assert ret.returncode == 0
    assert ret.data


def test_state_with_import_from_dir(salt_ssh_cli, nested_state_tree):
    """
    verify salt-ssh can use imported map files in states
    """
    ret = salt_ssh_cli.run(
        "--extra-filerefs=salt://foo/map.jinja", "state.apply", "foo"
    )
    assert ret.returncode == 0
    assert ret.data


def test_state_low(salt_ssh_cli):
    """
    test state.low with salt-ssh
    """
    ret = salt_ssh_cli.run(
        "state.low", '{"state": "cmd", "fun": "run", "name": "echo blah"}'
    )
    assert ret.data["cmd_|-echo blah_|-echo blah_|-run"]["changes"]["stdout"] == "blah"


def test_state_high(salt_ssh_cli):
    """
    test state.high with salt-ssh
    """
    ret = salt_ssh_cli.run("state.high", '{"echo blah": {"cmd": ["run"]}}')
    assert ret.data["cmd_|-echo blah_|-echo blah_|-run"]["changes"]["stdout"] == "blah"


def test_state_test(salt_ssh_cli, state_tree):
    ret = salt_ssh_cli.run("state.test", "test")
    assert ret.returncode == 0
    assert ret.data
    assert (
        ret.data["test_|-Ok with def_|-Ok with def_|-succeed_with_changes"]["result"]
        is None
    )

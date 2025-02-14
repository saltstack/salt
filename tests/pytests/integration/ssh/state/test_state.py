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


@pytest.mark.parametrize(
    "ssh_cmd",
    [
        "state.sls",
        "state.highstate",
        "state.apply",
        "state.show_top",
        "state.show_highstate",
        "state.show_low_sls",
        "state.show_lowstate",
        "state.sls_id",
        "state.show_sls",
        "state.top",
    ],
)
def test_state_with_import_dir(salt_ssh_cli, state_tree_dir, ssh_cmd):
    """
    verify salt-ssh can use imported map files in states
    when the map files are in another directory outside of
    sls files importing them.
    """
    if ssh_cmd in ("state.sls", "state.show_low_sls", "state.show_sls"):
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd, "test")
    elif ssh_cmd == "state.top":
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd, "top.sls")
    elif ssh_cmd == "state.sls_id":
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd, "Ok with def", "test")
    else:
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd)
    assert ret.returncode == 0
    if ssh_cmd == "state.show_top":
        assert ret.data == {"base": ["test", "master_tops_test"]} or {"base": ["test"]}
    elif ssh_cmd in ("state.show_highstate", "state.show_sls"):
        assert ret.data == {
            "Ok with def": {
                "__sls__": "test",
                "__env__": "base",
                "test": ["succeed_without_changes", {"order": 10000}],
            }
        }
    elif ssh_cmd in ("state.show_low_sls", "state.show_lowstate", "state.show_sls"):
        assert ret.data == [
            {
                "state": "test",
                "name": "Ok with def",
                "__sls__": "test",
                "__env__": "base",
                "__id__": "Ok with def",
                "order": 10000,
                "fun": "succeed_without_changes",
            }
        ]
    else:
        assert ret.data["test_|-Ok with def_|-Ok with def_|-succeed_without_changes"][
            "result"
        ]
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

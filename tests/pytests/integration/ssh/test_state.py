import pathlib
import shutil
import threading
import time

import pytest

from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]

SSH_SLS = "ssh_state_tests"
SSH_SLS_ID = "ssh-file-test"
SSH_SLS_FILE = pathlib.Path("/tmp/salt_test_file")


@pytest.fixture(autouse=True)
def cleanup_thin_dir(salt_ssh_cli):
    """
    Ensure the thin_dir and any files created by these tests are removed.
    """
    try:
        yield
    finally:
        ret = salt_ssh_cli.run("config.get", "thin_dir")
        if ret.returncode == 0 and ret.data:
            shutil.rmtree(ret.data, ignore_errors=True)
        for path in SSH_SLS_FILE.parent.glob(f"{SSH_SLS_FILE.name}*"):
            path.unlink(missing_ok=True)


def _assert_state_dict(ret):
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    return ret.data


def test_state_apply(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.apply", SSH_SLS)
    data = _assert_state_dict(ret)
    assert all(item.get("__sls__") == SSH_SLS for item in data.values())

    exists = salt_ssh_cli.run("file.file_exists", str(SSH_SLS_FILE))
    assert exists.returncode == 0
    assert exists.data is True


def test_state_sls_id_test_mode(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.sls_id", SSH_SLS_ID, SSH_SLS, "test=True")
    data = _assert_state_dict(ret)
    comment = next(iter(data.values())).get("comment", "")
    assert "No changes made" in comment


def test_state_sls_id(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.sls_id", SSH_SLS_ID, SSH_SLS)
    data = _assert_state_dict(ret)
    ids = {item.get("__id__") for item in data.values()}
    assert ids == {SSH_SLS_ID}

    exists = salt_ssh_cli.run("file.file_exists", str(SSH_SLS_FILE))
    assert exists.returncode == 0
    assert exists.data is True


def test_state_sls_wrong_id(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.sls_id", "doesnotexist", SSH_SLS)
    assert "No matches for ID" in ret.stdout


def test_state_sls_id_with_pillar(salt_ssh_cli):
    ret = salt_ssh_cli.run(
        "state.sls_id",
        SSH_SLS_ID,
        SSH_SLS,
        pillar='{"test_file_suffix": "_pillar"}',
    )
    _assert_state_dict(ret)

    pillar_file = SSH_SLS_FILE.with_name(SSH_SLS_FILE.name + "_pillar")
    exists = salt_ssh_cli.run("file.file_exists", str(pillar_file))
    assert exists.returncode == 0
    assert exists.data is True


def test_state_show_sls(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.show_sls", SSH_SLS)
    data = _assert_state_dict(ret)
    assert all(item.get("__sls__") == SSH_SLS for item in data.values())


def test_state_sls_exists(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.sls_exists", SSH_SLS)
    assert ret.returncode == 0
    assert ret.data is True


def test_state_show_top(salt_ssh_cli, base_env_state_tree_root_dir):
    top_sls = """
    base:
      '*':
        - core
    """
    core_state = """
    {}/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
    """.format(
        RUNTIME_VARS.TMP
    )
    with pytest.helpers.temp_file(
        "top.sls", top_sls, base_env_state_tree_root_dir
    ), pytest.helpers.temp_file("core.sls", core_state, base_env_state_tree_root_dir):
        ret = salt_ssh_cli.run("state.show_top")
        assert ret.returncode == 0
        assert ret.data == {"base": ["core", "master_tops_test"]}


def test_state_single(salt_ssh_cli):
    ret = salt_ssh_cli.run("state.single", "test.succeed_with_changes", "name=itworked")
    data = _assert_state_dict(ret)
    state_res = next(iter(data.values()))
    assert state_res["name"] == "itworked"
    assert state_res["result"] is True
    assert state_res["comment"] == "Success!"


def test_state_show_highstate(salt_ssh_cli, base_env_state_tree_root_dir):
    top_sls = """
    base:
      '*':
        - core
    """
    core_state = """
    {}/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
    """.format(
        RUNTIME_VARS.TMP
    )
    with pytest.helpers.temp_file(
        "top.sls", top_sls, base_env_state_tree_root_dir
    ), pytest.helpers.temp_file("core.sls", core_state, base_env_state_tree_root_dir):
        ret = salt_ssh_cli.run("state.show_highstate")
        data = _assert_state_dict(ret)
        dest = f"{RUNTIME_VARS.TMP}/testfile"
        assert dest in data
        assert data[dest]["__env__"] == "base"


def test_state_high(salt_ssh_cli):
    ret = salt_ssh_cli.run(
        "state.high", '{"itworked": {"test": ["succeed_with_changes"]}}'
    )
    data = _assert_state_dict(ret)
    state_res = next(iter(data.values()))
    assert state_res["name"] == "itworked"
    assert state_res["result"] is True
    assert state_res["comment"] == "Success!"


def test_state_show_lowstate(salt_ssh_cli, base_env_state_tree_root_dir):
    top_sls = """
    base:
      '*':
        - core
    """
    core_state = """
    {}/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
    """.format(
        RUNTIME_VARS.TMP
    )
    with pytest.helpers.temp_file(
        "top.sls", top_sls, base_env_state_tree_root_dir
    ), pytest.helpers.temp_file("core.sls", core_state, base_env_state_tree_root_dir):
        ret = salt_ssh_cli.run("state.show_lowstate")
        assert ret.returncode == 0
        assert isinstance(ret.data, list)
        assert ret.data
        assert isinstance(ret.data[0], dict)


def test_state_low(salt_ssh_cli):
    ret = salt_ssh_cli.run(
        "state.low",
        '{"state": "test", "fun": "succeed_with_changes", "name": "itworked"}',
    )
    data = _assert_state_dict(ret)
    state_res = next(iter(data.values()))
    assert state_res["name"] == "itworked"
    assert state_res["result"] is True
    assert state_res["comment"] == "Success!"


def test_state_request_check_clear(salt_ssh_cli):
    request = salt_ssh_cli.run("state.request", SSH_SLS)
    _assert_state_dict(request)

    check = salt_ssh_cli.run("state.check_request")
    assert check.returncode == 0
    assert check.data

    clear = salt_ssh_cli.run("state.clear_request")
    assert clear.returncode == 0

    check_empty = salt_ssh_cli.run("state.check_request")
    assert check_empty.returncode == 0
    assert not check_empty.data


def test_state_run_request(salt_ssh_cli):
    request = salt_ssh_cli.run("state.request", SSH_SLS)
    _assert_state_dict(request)

    run = salt_ssh_cli.run("state.run_request")
    _assert_state_dict(run)

    exists = salt_ssh_cli.run("file.file_exists", str(SSH_SLS_FILE))
    assert exists.returncode == 0
    assert exists.data is True


def test_state_running(
    salt_master, salt_ssh_cli, salt_ssh_roster_file, sshd_config_dir
):
    results = []
    background_cli = salt_master.salt_ssh_cli(
        timeout=180,
        roster_file=salt_ssh_roster_file,
        target_host="localhost",
        client_key=str(sshd_config_dir / "client_key"),
    )

    def _run_state():
        results.append(background_cli.run("state.sls", "running"))

    thread = threading.Thread(target=_run_state)
    thread.start()

    expected = 'The function "state.pkg" is running as'
    try:
        end_time = time.time() + 30
        while time.time() < end_time:
            ret = salt_ssh_cli.run("state.running")
            if isinstance(ret.data, list):
                output = " ".join(ret.data)
            else:
                output = " ".join(str(ret.data).splitlines())
            if expected in output:
                break
            time.sleep(1)
        else:
            if results and "Failed to return clean data" in str(results[0].data):
                pytest.skip("Background state run failed, skipping")
            pytest.fail(f"Did not find '{expected}' in state.running output")
    finally:
        thread.join(timeout=120)

    end_time = time.time() + 120
    while time.time() < end_time:
        ret = salt_ssh_cli.run("state.running")
        if isinstance(ret.data, list):
            output = " ".join(ret.data)
        else:
            output = " ".join(str(ret.data).splitlines())
        if expected not in output:
            break
        time.sleep(1)
    else:
        pytest.fail("state.pkg is still reported as running")

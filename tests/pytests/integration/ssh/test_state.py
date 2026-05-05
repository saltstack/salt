import pathlib
import shutil
import textwrap
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
        # Retry to handle a potential race where the master_tops extension
        # module hasn't been fully loaded yet when the first call is made.
        # 60s wins on slow ARM64 / FIPS runners where the master takes
        # longer to discover ``master_tops_test`` from extension_modules.
        ret = None
        for _ in range(20):
            ret = salt_ssh_cli.run("state.show_top")
            if ret.returncode == 0 and ret.data == {
                "base": ["core", "master_tops_test"]
            }:
                break
            time.sleep(3)
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


@pytest.mark.timeout(300, func_only=True)
def test_state_running(
    salt_master,
    salt_ssh_cli,
    salt_ssh_roster_file,
    sshd_config_dir,
    base_env_state_tree_root_dir,
    tmp_path,
):
    """
    Validate that ``state.running`` reports the salt-ssh ``state.pkg``
    function while a background ``state.sls`` invocation is mid-flight,
    and stops reporting it once the background run finishes.

    The race that previously caused this to flake: the foreground polled
    ``state.running`` blindly, hoping to land inside the (variable-length)
    salt-ssh setup + sleep window. To make it deterministic, the SLS now
    writes a ``started`` marker file before the sleep step. The test
    blocks on that marker before polling, so by the time we look,
    ``state.pkg`` is guaranteed to be live in the remote ``proc/`` cache.
    """
    started_marker = tmp_path / "state_running_started.marker"
    if started_marker.exists():
        started_marker.unlink()

    sls_name = "running_signaled"
    sls_contents = textwrap.dedent(
        f"""
        sync_marker:
          file.managed:
            - name: {started_marker.as_posix()}
            - contents: started

        sleep_running:
          module.run:
            - name: test.sleep
            - length: 60
        """
    ).lstrip()

    background_cli = salt_master.salt_ssh_cli(
        timeout=180,
        roster_file=salt_ssh_roster_file,
        target_host="localhost",
        client_key=str(sshd_config_dir / "client_key"),
    )

    results = []

    def _run_state():
        results.append(background_cli.run("state.sls", sls_name))

    expected = 'The function "state.pkg" is running as'

    with pytest.helpers.temp_file(
        f"{sls_name}.sls", sls_contents, base_env_state_tree_root_dir
    ):
        thread = threading.Thread(target=_run_state)
        thread.start()
        try:
            # Wait deterministically for the background SLS to reach the
            # ``test.sleep`` step. salt-ssh thin / venv setup time is
            # bounded by ``timeout=180`` on ``background_cli``; if we do
            # not see the marker by then either salt-ssh failed entirely
            # or the runner is too slow for the test to be meaningful.
            marker_deadline = time.time() + 180
            while time.time() < marker_deadline:
                if started_marker.exists():
                    break
                if not thread.is_alive():
                    # salt-ssh exited without writing the marker; fall
                    # through to the existing ``Failed to return clean
                    # data`` recovery path below.
                    break
                time.sleep(0.5)

            if not started_marker.exists():
                if results and "Failed to return clean data" in str(results[0].data):
                    pytest.skip("Background state run failed, skipping")
                pytest.fail(
                    "Background state.sls did not reach test.sleep step; "
                    "marker file was never written"
                )

            # The marker exists, so salt-ssh is currently mid-execution
            # and ``state.pkg`` should be visible in ``state.running``
            # output until the 60s sleep finishes. A small retry budget
            # absorbs the latency of a single salt-ssh round trip.
            end_time = time.time() + 30
            while time.time() < end_time:
                ret = salt_ssh_cli.run("state.running")
                output = (
                    " ".join(ret.data) if isinstance(ret.data, list) else str(ret.data)
                )
                if expected in output:
                    break
                time.sleep(1)
            else:
                pytest.fail(f"Did not find '{expected}' in state.running output")
        finally:
            thread.join(timeout=180)

        # Wait for state.pkg to drop out of state.running output now that
        # the background run has finished.
        end_time = time.time() + 60
        while time.time() < end_time:
            ret = salt_ssh_cli.run("state.running")
            output = " ".join(ret.data) if isinstance(ret.data, list) else str(ret.data)
            if expected not in output:
                break
            time.sleep(1)
        else:
            pytest.fail("state.pkg is still reported as running")

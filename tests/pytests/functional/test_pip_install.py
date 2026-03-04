import subprocess
import time

import pytest


@pytest.fixture
def salt_master(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    master_config = config_dir / "master"
    # Using current user to avoid 'user salt not available' errors
    import getpass

    user = getpass.getuser()
    master_config.write_text(
        f"user: {user}\nroot_dir: {tmp_path}\npki_dir: {tmp_path}/pki/master\ncachedir: {tmp_path}/cache/master\nsock_dir: {tmp_path}/sock/master\n"
    )

    # Start master
    proc = subprocess.Popen(
        ["salt-master", "-c", str(config_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture
def salt_minion(tmp_path):
    config_dir = tmp_path / "config_minion"
    config_dir.mkdir()
    minion_config = config_dir / "minion"
    import getpass

    user = getpass.getuser()
    minion_config.write_text(
        f"user: {user}\nmaster: 127.0.0.1\nid: test-minion\nroot_dir: {tmp_path}\npki_dir: {tmp_path}/pki/minion\ncachedir: {tmp_path}/cache/minion\nsock_dir: {tmp_path}/sock/minion\n"
    )

    # Start minion
    proc = subprocess.Popen(
        ["salt-minion", "-c", str(config_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc
    proc.terminate()
    proc.wait()


def test_master_minion_start(salt_master, salt_minion, tmp_path):
    # Give them a few seconds to start
    time.sleep(10)

    # Check if they are still running
    assert salt_master.poll() is None, f"Master exited with {salt_master.returncode}"
    assert salt_minion.poll() is None, f"Minion exited with {salt_minion.returncode}"

    # Simple check for salt-call
    import getpass

    user = getpass.getuser()
    ret = subprocess.run(
        ["salt-call", "--local", "-c", str(tmp_path / "config_minion"), "test.ping"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "True" in ret.stdout

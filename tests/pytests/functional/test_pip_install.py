import getpass
import subprocess
import time
from pathlib import Path

import pytest

try:
    import virtualenv

    HAS_VIRTUALENV = True
except ImportError:
    HAS_VIRTUALENV = False

pytestmark = [
    pytest.mark.skipif(HAS_VIRTUALENV is False, reason="virtualenv is not installed"),
]


@pytest.fixture(scope="module")
def test_venv(tmp_path_factory):
    venv_dir = tmp_path_factory.mktemp("venv")
    virtualenv.cli_run([str(venv_dir)])
    python_bin = venv_dir / "bin" / "python"
    # Install the current salt package
    # We use the root of the repo which is 3 levels up from this file's directory
    repo_root = Path(__file__).resolve().parents[3]
    subprocess.run(
        [
            str(python_bin),
            "-m",
            "pip",
            "install",
            str(repo_root),
        ],
        check=True,
    )
    return venv_dir


@pytest.fixture
def salt_master(test_venv, tmp_path):
    config_dir = tmp_path / "config_master"
    config_dir.mkdir()
    master_config = config_dir / "master"
    user = getpass.getuser()
    master_config.write_text(
        f"user: {user}\nroot_dir: {tmp_path}\npki_dir: {tmp_path}/pki/master\ncachedir: {tmp_path}/cache/master\nsock_dir: {tmp_path}/sock/master\n"
    )

    master_bin = test_venv / "bin" / "salt-master"
    proc = subprocess.Popen(
        [str(master_bin), "-c", str(config_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def salt_minion(test_venv, tmp_path):
    config_dir = tmp_path / "config_minion"
    config_dir.mkdir()
    minion_config = config_dir / "minion"
    user = getpass.getuser()
    minion_config.write_text(
        f"user: {user}\nmaster: 127.0.0.1\nid: test-minion\nroot_dir: {tmp_path}\npki_dir: {tmp_path}/pki/minion\ncachedir: {tmp_path}/cache/minion\nsock_dir: {tmp_path}/sock/minion\n"
    )

    minion_bin = test_venv / "bin" / "salt-minion"
    proc = subprocess.Popen(
        [str(minion_bin), "-c", str(config_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_master_minion_start(test_venv, salt_master, salt_minion, tmp_path):
    # Give them a few seconds to start
    time.sleep(10)

    # Check if they are still running
    assert salt_master.poll() is None, f"Master exited with {salt_master.returncode}"
    assert salt_minion.poll() is None, f"Minion exited with {salt_minion.returncode}"

    # Simple check for salt-call
    call_bin = test_venv / "bin" / "salt-call"
    ret = subprocess.run(
        [str(call_bin), "--local", "-c", str(tmp_path / "config_minion"), "test.ping"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "True" in ret.stdout

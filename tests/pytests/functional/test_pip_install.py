import getpass
import importlib.util
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

log = logging.getLogger(__name__)

HAS_VIRTUALENV = importlib.util.find_spec("virtualenv") is not None

pytestmark = [
    pytest.mark.skipif(HAS_VIRTUALENV is False, reason="virtualenv is not installed"),
    # ``virtualenv.cli_run`` builds a venv off of the onedir's Python, then
    # uses pip's vendored urllib3 to install Salt. urllib3 calls
    # ``SSLContext(ssl_version)`` with a deprecated protocol enum which
    # fails as ``LIBRARY_HAS_NO_CIPHERS`` against an OpenSSL configured for
    # FIPS, so the venv's pip cannot run on FIPS-enabled platforms.
    pytest.mark.skip_on_fips_enabled_platform,
]


if shutil.which("gcc") is None and shutil.which("cc") is None:
    pytestmark.append(
        pytest.mark.skip(reason="A C compiler is required to build some dependencies")
    )


@pytest.fixture(scope="module")
def test_venv(tmp_path_factory):
    venv_dir = tmp_path_factory.mktemp("venv")
    # Run virtualenv as a subprocess so we can bound it with a timeout and
    # see its stdout in the CI log.  ``virtualenv.cli_run`` runs in-process
    # and during pip/setuptools bootstrap can stall on PyPI for arbitrary
    # time -- a recent CI run sat idle 2h49m past this point until the
    # workflow timeout fired.
    log.info("Creating test venv at %s", venv_dir)
    subprocess.run(
        [sys.executable, "-m", "virtualenv", str(venv_dir)],
        check=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
        timeout=300,
    )
    python_bin = venv_dir / "bin" / "python"
    repo_root = Path(__file__).resolve().parents[3]
    log.info("pip-installing salt from %s into %s", repo_root, venv_dir)
    subprocess.run(
        [
            str(python_bin),
            "-m",
            "pip",
            "install",
            str(repo_root),
        ],
        check=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
        timeout=600,
    )
    log.info("pip-install done")
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

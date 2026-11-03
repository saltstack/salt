import contextlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from collections.abc import Iterator

import pytest
from saltfactories.utils import random_string

import salt.utils.files
import salt.utils.user
from tests.conftest import FIPS_TESTRUN


@pytest.fixture(scope="module")
def salt_call_wrapper(tmp_path_factory):
    # Create a wrapper script for salt-call
    wrapper_path = tmp_path_factory.mktemp("wrapper") / "salt-call-wrapper"
    salt_root = os.getcwd()

    with salt.utils.files.fopen(wrapper_path, "w") as f:
        f.write(
            f"""#!{sys.executable}
import sys
sys.path.insert(0, "{salt_root}")
from salt.scripts import salt_call
if __name__ == '__main__':
    salt_call()
"""
        )
    os.chmod(wrapper_path, 0o755)
    return str(wrapper_path)


@pytest.fixture(scope="module")
def non_root_minion(salt_master, salt_factories):
    # Configure minion with a non-root user
    # We use 'nobody' which is a standard low-privilege user on most systems
    # If 'nobody' doesn't exist, we'll try to find another non-root user
    import pwd

    # Try to find a suitable non-root user
    non_root_user = None
    for candidate in ["nobody", "daemon", "bin"]:
        try:
            pwd.getpwnam(candidate)
            non_root_user = candidate
            break
        except KeyError:
            continue

    if not non_root_user:
        pytest.skip("No suitable non-root user found for testing")

    config_overrides = {
        "user": non_root_user,
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": ("PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"),
    }

    factory = salt_master.salt_minion_daemon(
        random_string("non-root-minion-"),
        overrides=config_overrides,
    )
    try:
        with factory.started():
            yield factory
    finally:
        # ``factory.started()`` stops the minion daemon but leaves the
        # minion's accepted key under ``{master_pki_dir}/minions/<id>``.
        # The subsequent ``test_salt_key.py::test_list_*`` tests in the same
        # session enumerate PKI keys and fail their expected-list assertions
        # when this stale key is present.  Delete it explicitly.
        # ``salt_master.salt_key_cli`` is a *factory* method on the saltfactories
        # ``SaltMaster``, not an attribute -- it must be called to obtain a
        # runnable ``SaltKey`` CLI factory.
        salt_master.salt_key_cli().run("-d", factory.id, "-y")


@pytest.mark.skipif(shutil.which("sudo") is None, reason="sudo is not available")
def test_salt_call_preserves_ownership(non_root_minion, salt_call_wrapper):
    """
    Test that running salt-call as root (via sudo) for a non-root minion
    does not change ownership of files in the cache directory to root.
    """
    # Get the minion's config directory
    config_dir = non_root_minion.config_dir

    # Run a simple salt-call command as root
    # We point it to the minion's config directory
    cmd = ["sudo", salt_call_wrapper, "--local", "-c", str(config_dir), "test.ping"]

    subprocess.run(cmd, check=True)

    # Now check ownership of files in the minion's cache directory
    # The cache directory is typically under the root_dir defined in config
    # salt-factories sets root_dir to a temp dir.

    # We can get the cachedir from the minion config
    cachedir = non_root_minion.config["cachedir"]

    # Verify cachedir exists
    assert os.path.exists(cachedir)

    # Walk through the cachedir and check ownership
    # All files should be owned by the current user (os.getuid()), NOT root (0)

    files_checked = 0
    for root, dirs, files in os.walk(cachedir):
        for name in files:
            path = os.path.join(root, name)
            stat = os.stat(path)

            # Check ownership
            # We expect it to be owned by current_user (uid), not root (0)
            if stat.st_uid == 0:
                pytest.fail(
                    f"File {path} is owned by root! salt-call failed to drop privileges correctly."
                )

            files_checked += 1

    # Ensure we actually checked some files (cache shouldn't be empty after running a command)
    # salt-call usually populates grains/minion_id/etc in cache
    assert files_checked > 0, "No files found in cache directory to check"


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows
@pytest.mark.skipif(shutil.which("sudo") is None, reason="sudo is not available")
def test_salt_call_runas_ignores_inherited_login_name(salt_minion, salt_call_wrapper):
    """Ensure sudo salt-call switches UIDs when the runas user matches the user invoking sudo
    """
    with pytest.helpers.create_account() as account:
        salt_call_args = [
            "--local",
            "--out=json",
            "-c",
            str(salt_minion.config_dir),
            "cmd.run",
            "id",
            f"runas={account.username}",
        ]
        allowed_command = [salt_call_wrapper, *salt_call_args]
        with temporary_sudoers_rule(account.username, allowed_command):
            command = [
                "sudo",
                "-n",
                "-u",
                account.username,
                "sudo",
                "-n",
                *allowed_command,
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=True)

        actual_uid = json.loads(result.stdout)["local"]
        assert actual_uid.startswith(f"uid={account.info.uid}(")


@contextlib.contextmanager
def temporary_sudoers_rule(username: str, command: list[str]) -> Iterator[None]:
    """Allow one user to run a specific command as root during a test.
    """
    sudoers_rule = f"{username} ALL=(root) NOPASSWD: {' '.join(command)}\n"
    sudoers_path = pathlib.Path("/etc/sudoers.d") / f"salt-runas-{username}"
    fd = os.open(sudoers_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        with os.fdopen(fd, "w") as policy_file:
            policy_file.write(sudoers_rule)
        sudoers_path.chmod(0o440)
        yield
    finally:
        sudoers_path.unlink()

import os
import shutil
import subprocess
import sys

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
    with factory.started():
        yield factory


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

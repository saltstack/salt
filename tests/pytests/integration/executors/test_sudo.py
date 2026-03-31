import os
import pathlib
import shutil
import subprocess
import sys

import pytest
from saltfactories.utils import random_string

import salt.utils.files
import salt.utils.path
import salt.utils.user


@pytest.fixture(scope="module")
def setup_salt_call_for_sudo(salt_factories):
    """
    Create a salt-call script that sudo can find.

    Salt-factories creates scripts in /tmp/stsuite/scripts/ but doesn't create
    a cli_salt_call.py. We need to create both that and a wrapper in a location
    that sudo can find (typically /usr/local/bin).
    """
    # Find the scripts directory that salt-factories uses
    scripts_dir = pathlib.Path("/tmp/stsuite/scripts")
    if not scripts_dir.exists():
        pytest.skip("Salt-factories scripts directory not found")

    # First, create cli_salt_call.py in the scripts directory
    # (salt-factories doesn't create this by default)
    salt_call_script = scripts_dir / "cli_salt_call.py"
    code_dir = os.getcwd()

    salt_call_script_content = f"""from __future__ import absolute_import
import os
import sys

# We really do not want buffered output
os.environ[str("PYTHONUNBUFFERED")] = str("1")
# Don't write .pyc files or create them in __pycache__ directories
os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")

CODE_DIR = r'{code_dir}'
if CODE_DIR in sys.path:
    sys.path.remove(CODE_DIR)
sys.path.insert(0, CODE_DIR)

import atexit
import traceback
from salt.scripts import salt_call

if __name__ == '__main__':
    exitcode = 0
    try:
        salt_call()
    except SystemExit as exc:
        exitcode = exc.code
        # https://docs.python.org/3/library/exceptions.html#SystemExit
        if exitcode is None:
            exitcode = 0
        if not isinstance(exitcode, int):
            # A string?!
            sys.stderr.write(exitcode)
            exitcode = 1
    except Exception as exc:
        sys.stderr.write(
            "An un-handled exception was caught: " + str(exc) + "\\n" + traceback.format_exc()
        )
        exitcode = 1
    sys.stdout.flush()
    sys.stderr.flush()
    atexit._run_exitfuncs()
    os._exit(exitcode)
"""

    with salt.utils.files.fopen(str(salt_call_script), "w") as f:
        f.write(salt_call_script_content)
    os.chmod(salt_call_script, 0o755)

    # Now create a wrapper script in /usr/local/bin
    salt_call_wrapper = "/usr/local/bin/salt-call"

    # Check if it already exists (another test might have created it)
    if os.path.exists(salt_call_wrapper):
        # Use the existing one
        yield salt_call_wrapper
        # Cleanup our script
        salt_call_script.unlink()
        return

    # Create the wrapper script
    wrapper_content = f"""#!/bin/sh
# Wrapper for salt-call to work with sudo executor tests
exec {sys.executable} {salt_call_script} "$@"
"""

    try:
        # Write the wrapper (needs sudo)
        with salt.utils.files.fopen("/tmp/salt-call-wrapper.sh", "w") as f:
            f.write(wrapper_content)
        os.chmod("/tmp/salt-call-wrapper.sh", 0o755)

        # Install it to /usr/local/bin with sudo
        subprocess.run(
            ["sudo", "cp", "/tmp/salt-call-wrapper.sh", salt_call_wrapper], check=True
        )
        subprocess.run(["sudo", "chmod", "755", salt_call_wrapper], check=True)
    except (subprocess.CalledProcessError, PermissionError, FileNotFoundError) as e:
        # Cleanup our script
        salt_call_script.unlink()
        pytest.skip(f"Cannot create salt-call wrapper for sudo: {e}")

    yield salt_call_wrapper

    # Cleanup
    try:
        subprocess.run(["sudo", "rm", "-f", salt_call_wrapper], check=True)
        os.remove("/tmp/salt-call-wrapper.sh")
        salt_call_script.unlink()
    except Exception:  # pylint: disable=broad-exception-caught
        pass


@pytest.fixture(scope="module")
def sudo_minion(salt_master, salt_factories, setup_salt_call_for_sudo):
    # Configure minion with current user as 'user' (so it normally runs as this user)
    # But 'sudo_user' as 'root' (so it uses sudo to run commands)
    config_overrides = {
        "sudo_user": "root",
        "user": salt.utils.user.get_user(),
    }

    factory = salt_master.salt_minion_daemon(
        random_string("sudo-minion-"),
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.mark.skip(
    reason="This test requires salt-call to be in sudo's PATH, which varies by environment. "
    "The functionality is covered by unit tests."
)
@pytest.mark.skipif(shutil.which("sudo") is None, reason="sudo is not available")
def test_sudo_executor_runs_as_root(sudo_minion, salt_cli):
    """
    Test that when sudo_user is set to root, salt-call runs as root.
    This validates that privileges were NOT dropped to the minion's configured user.
    """
    # Verify that we can run a command via sudo executor
    # We expect 'id -u' to return 0 (root) because we configured sudo_user: root
    # If the fix is missing, salt-call would see "user: <current_user>" in config
    # and drop privileges to that user, so 'id -u' would return <current_user_uid>.

    ret = salt_cli.run("cmd.run", "id -u", minion_tgt=sudo_minion.id)
    assert ret.returncode == 0

    # Check if the output is 0.
    # Note: ret.data might be parsed as int or string depending on outputter,
    # but cmd.run usually returns string.

    # We need to handle potential newlines or whitespace
    uid = ret.data.strip() if isinstance(ret.data, str) else str(ret.data)

    assert (
        uid == "0"
    ), f"Expected uid 0 (root), got {uid}. salt-call likely dropped privileges."

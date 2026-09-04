import os
import shutil
import subprocess
import sys

import pytest

import salt.utils.files
import salt.utils.user
import salt.version


@pytest.fixture(scope="module")
def salt_pip_wrapper(tmp_path_factory):
    # Create a wrapper script for salt-pip
    wrapper_path = tmp_path_factory.mktemp("wrapper") / "salt-pip-wrapper"
    salt_root = os.getcwd()

    # Fake onedir structure
    fake_onedir = tmp_path_factory.mktemp("onedir")
    extras_dir = (
        fake_onedir / f"extras-{sys.version_info.major}.{sys.version_info.minor}"
    )
    extras_dir.mkdir()

    with salt.utils.files.fopen(wrapper_path, "w") as f:
        f.write(
            f"""#!{sys.executable}
import sys
import os
from unittest.mock import patch

# Inject salt path
sys.path.insert(0, "{salt_root}")

import salt.scripts

# Fake RELENV
class MockPath:
    def __init__(self, path):
        self.path = path
    def __truediv__(self, other):
        return MockPath(os.path.join(self.path, other))
    def __str__(self):
        return self.path

def main():
    with patch("salt.scripts._get_onedir_env_path", return_value=MockPath("{fake_onedir}")):
        salt.scripts.salt_pip()

if __name__ == '__main__':
    main()
"""
        )
    os.chmod(wrapper_path, 0o755)
    return str(wrapper_path), extras_dir


@pytest.mark.skipif(shutil.which("sudo") is None, reason="sudo is not available")
def test_salt_pip_installs_as_user(salt_pip_wrapper, tmp_path):
    wrapper_path, extras_dir = salt_pip_wrapper

    # Create a config file that sets 'user' to the current non-root user
    current_user = salt.utils.user.get_user()
    config_dir = tmp_path / "conf"
    config_dir.mkdir()
    config_file = config_dir / "minion"
    with salt.utils.files.fopen(config_file, "w") as f:
        f.write(f"user: {current_user}\n")

    pkg_dir = tmp_path / "dummypkg"
    pkg_dir.mkdir()
    with salt.utils.files.fopen(pkg_dir / "setup.py", "w") as f:
        f.write("from setuptools import setup; setup(name='dummypkg', version='0.1')")

    # Pass absolute path to config file
    config_path = str(config_file)

    cmd = [
        "sudo",
        "env",
        f"SALT_MINION_CONFIG={config_path}",
        wrapper_path,
        "install",
        str(pkg_dir),
        "--no-deps",
    ]

    subprocess.run(cmd, check=True)

    found_files = False
    for root, dirs, files in os.walk(extras_dir):
        for name in files:
            found_files = True
            path = os.path.join(root, name)
            stat = os.stat(path)

            # Check ownership
            assert (
                stat.st_uid == os.getuid()
            ), f"File {path} is owned by {stat.st_uid}, expected {os.getuid()}"

    assert found_files, "No files were installed into extras dir"

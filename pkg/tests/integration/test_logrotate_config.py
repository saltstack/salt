"""
Tests for logrotate config
"""

from pathlib import Path

import pytest

pytestmark = [pytest.mark.skip_on_windows, pytest.mark.skip_on_darwin]


@pytest.fixture
def logrotate_config_file(salt_call_cli):
    """
    Fixture for logrotate config file path
    """
    logrotate_dir = Path("/etc/logrotate.d")

    os_family = salt_call_cli.run("grains.get", "os_family")
    assert os_family.returncode == 0

    if os_family.data == "RedHat":
        return logrotate_dir / "salt"
    elif os_family.data == "Debian":
        return logrotate_dir / "salt-common"


def test_logrotate_config(logrotate_config_file):
    """
    Test that logrotate config has been installed in correctly
    """
    assert logrotate_config_file.is_file()
    assert logrotate_config_file.owner() == "root"
    assert logrotate_config_file.group() == "root"


def test_issue_65231_etc_logrotate_salt_dir_removed():
    """
    Test that /etc/logrotate.d/salt is not a directory
    """
    path = Path("/etc/logrotate.d/salt")
    if path.exists():
        assert path.is_dir() is False

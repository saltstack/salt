"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.grub_legacy
"""

import errno

import pytest

import salt.modules.grub_legacy as grub_legacy
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {grub_legacy: {}}


def test_version():
    """
    Test for Return server version from grub --version
    """
    mock = MagicMock(return_value="out")
    with patch.dict(grub_legacy.__salt__, {"cmd.run": mock}):
        assert grub_legacy.version() == "out"


def test_conf():
    """
    Test for Parse GRUB conf file
    """
    file_data = IOError(errno.EACCES, "Permission denied")
    with patch("salt.utils.files.fopen", mock_open(read_data=file_data)), patch.object(
        grub_legacy, "_detect_conf", return_value="A"
    ):
        pytest.raises(CommandExecutionError, grub_legacy.conf)

    file_data = salt.utils.stringutils.to_str("\n".join(["#", "A B C D,E,F G H"]))
    with patch("salt.utils.files.fopen", mock_open(read_data=file_data)), patch.object(
        grub_legacy, "_detect_conf", return_value="A"
    ):
        conf = grub_legacy.conf()
        assert conf == {"A": "B C D,E,F G H", "stanzas": []}, conf

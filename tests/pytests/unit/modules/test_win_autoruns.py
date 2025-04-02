"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.win_autoruns as win_autoruns
from tests.support.mock import MagicMock, patch


@pytest.fixture
def define_key():
    return [
        "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
        "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /reg:64",
        "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
    ]


@pytest.fixture
def configure_loader_modules():
    return {win_autoruns: {}}


def test_list(define_key):
    """
    Test if it enables win_autoruns the service on the server
    """
    with patch("os.listdir", MagicMock(return_value=[])):
        ret = {
            define_key[0]: ["SALT"],
            define_key[1]: ["SALT"],
            define_key[2]: ["SALT"],
        }
        mock = MagicMock(return_value="Windows 7")
        with patch.dict(win_autoruns.__grains__, {"osfullname": mock}):
            mock = MagicMock(return_value="SALT")
            with patch.dict(win_autoruns.__salt__, {"cmd.run": mock}):
                assert win_autoruns.list_() == ret

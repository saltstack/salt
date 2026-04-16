"""
:codeauthor: SaltStack
"""

import pytest
import salt.modules.efi as efi
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        efi: {
            "__grains__": {"kernel": "Linux"},
            "__salt__": {
                "cmd.run_stdout": MagicMock(),
                "cmd.retcode": MagicMock(),
            },
        }
    }


def test_virtual_linux():
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/efibootmgr")):
        assert efi.__virtual__() == "efi"


def test_virtual_non_linux():
    with patch("salt.modules.efi.__grains__", {"kernel": "Windows"}):
        assert efi.__virtual__() == (False, "efi module only supports Linux")


def test_list_entries():
    mock_out = "\n".join(
        [
            "BootCurrent: 0001",
            "Timeout: 1 seconds",
            "BootOrder: 0001,0002",
            "Boot0001* debian\t"
            "HD(1,GPT,00000000-0000-0000-0000-000000000000,0x800,0x100000)"
            "/File(\\EFI\\DEBIAN\\SHIMX64.EFI)",
        ]
    )
    with patch(
        "salt.modules.efi.__salt__",
        {"cmd.run_stdout": MagicMock(return_value=mock_out)},
    ):
        entries = efi.list_entries()
        assert "0001" in entries
        assert entries["0001"]["label"] == "debian"


def test_get_bootorder():
    mock_out = "BootCurrent: 0001\nBootOrder: 0001,0002"
    with patch(
        "salt.modules.efi.__salt__",
        {"cmd.run_stdout": MagicMock(return_value=mock_out)},
    ):
        assert efi.get_bootorder() == ["0001", "0002"]


def test_add_entry():
    with patch("salt.modules.efi.__salt__", {"cmd.retcode": MagicMock(return_value=0)}):
        assert efi.add_entry("Debian", "\\EFI\\debian\\grub.efi") is True


def test_remove_entry():
    with patch("salt.modules.efi.__salt__", {"cmd.retcode": MagicMock(return_value=0)}):
        assert efi.remove_entry("0001") is True


def test_set_bootorder():
    with patch("salt.modules.efi.__salt__", {"cmd.retcode": MagicMock(return_value=0)}):
        assert efi.set_bootorder(["0001", "0002"]) is True

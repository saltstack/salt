import pytest
import salt.states.efi as efi
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        efi: {
            "__salt__": {
                "efi.list_entries": MagicMock(),
                "efi.add_entry": MagicMock(),
                "efi.remove_entry": MagicMock(),
                "efi.get_bootorder": MagicMock(),
                "efi.set_bootorder": MagicMock(),
            },
            "__opts__": {"test": False},
        }
    }


def test_present_new_entry():
    with patch(
        "salt.states.efi.__salt__",
        {
            "efi.list_entries": MagicMock(return_value={}),
            "efi.add_entry": MagicMock(return_value=True),
            "efi.get_bootorder": MagicMock(return_value=["0001"]),
            "efi.set_bootorder": MagicMock(return_value=True),
        },
    ):
        ret = efi.present("Debian", "\\EFI\\debian\\grub.efi", index=0)
        assert ret["result"] is True
        assert "new" in ret["changes"]


def test_present_already_exists():
    with patch(
        "salt.states.efi.__salt__",
        {
            "efi.list_entries": MagicMock(return_value={"0001": {"label": "Debian"}}),
        },
    ):
        ret = efi.present("Debian", "\\EFI\\debian\\grub.efi")
        assert ret["result"] is True
        assert "already present" in ret["comment"]


def test_present_already_exists_update_order():
    # Mocking: Entry exists, boot order needs change, set_bootorder succeeds
    with patch(
        "salt.states.efi.__salt__",
        {
            "efi.list_entries": MagicMock(return_value={"0001": {"label": "Debian"}}),
            # Current order: ["0002", "0001"]. Desired index=0 means ["0001", "0002"]
            "efi.get_bootorder": MagicMock(
                side_effect=[["0002", "0001"], ["0002", "0001"]]
            ),
            "efi.set_bootorder": MagicMock(return_value=True),
        },
    ):
        ret = efi.present("Debian", "\\EFI\\debian\\grub.efi", index=0)
        assert ret["result"] is True
        assert "bootorder" in ret["changes"]
        assert "Boot order updated" in ret["comment"]


def test_absent_existing_entry():
    with patch(
        "salt.states.efi.__salt__",
        {
            "efi.list_entries": MagicMock(return_value={"0001": {"label": "Debian"}}),
            "efi.remove_entry": MagicMock(return_value=True),
        },
    ):
        ret = efi.absent("Debian")
        assert ret["result"] is True
        assert "removed" in ret["comment"]
        assert "old" in ret["changes"]


def test_absent_already_absent():
    with patch(
        "salt.states.efi.__salt__",
        {
            "efi.list_entries": MagicMock(return_value={}),
        },
    ):
        ret = efi.absent("Debian")
        assert ret["result"] is True
        assert "already absent" in ret["comment"]


def test_order_set():
    with patch(
        "salt.states.efi.__salt__",
        {
            "efi.get_bootorder": MagicMock(return_value=["0002", "0001"]),
            "efi.set_bootorder": MagicMock(return_value=True),
        },
    ):
        ret = efi.order_set("set_order", ["0001", "0002"])
        assert ret["result"] is True
        assert "old" in ret["changes"]
        assert "new" in ret["changes"]


def test_order_set_already_correct():
    with patch(
        "salt.states.efi.__salt__",
        {
            "efi.get_bootorder": MagicMock(return_value=["0001", "0002"]),
        },
    ):
        ret = efi.order_set("set_order", ["0001", "0002"])
        assert ret["result"] is True
        assert "already set" in ret["comment"]

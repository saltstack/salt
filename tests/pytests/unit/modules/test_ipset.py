"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""
import pytest
import salt.modules.ipset as ipset
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    with patch.object(ipset, "_ipset_cmd", return_value="ipset"):
        yield {ipset: {}}


def test_version():
    """
    Test for Return version from ipset --version
    """
    with patch.object(ipset, "_ipset_cmd", return_value="A"):
        mock = MagicMock(return_value="A\nB\nC")
        with patch.dict(ipset.__salt__, {"cmd.run": mock}):
            assert ipset.version() == "B"


def test_new_set():
    """
    Test for Create new custom set
    """
    assert ipset.new_set() == "Error: Set Name needs to be specified"

    assert ipset.new_set("s") == "Error: Set Type needs to be specified"

    assert ipset.new_set("s", "d") == "Error: Set Type is invalid"

    assert ipset.new_set("s", "bitmap:ip") == "Error: range is a required argument"

    mock = MagicMock(return_value=False)
    with patch.dict(ipset.__salt__, {"cmd.run": mock}):
        assert ipset.new_set("s", "bitmap:ip", range="range")


def test_delete_set():
    """
    Test for Delete ipset set.
    """
    assert ipset.delete_set() == "Error: Set needs to be specified"

    with patch.object(ipset, "_ipset_cmd", return_value="A"):
        mock = MagicMock(return_value=True)
        with patch.dict(ipset.__salt__, {"cmd.run": mock}):
            assert ipset.delete_set("set", "family")


def test_rename_set():
    """
    Test for Delete ipset set.
    """
    assert ipset.rename_set() == "Error: Set needs to be specified"

    assert ipset.rename_set("s") == "Error: New name for set needs to be specified"

    with patch.object(ipset, "_find_set_type", return_value=False):
        assert ipset.rename_set("s", "d") == "Error: Set does not exist"

    with patch.object(ipset, "_find_set_type", return_value=True):
        assert ipset.rename_set("s", "d") == "Error: New Set already exists"

    with patch.object(ipset, "_find_set_type", side_effect=[True, False]):
        with patch.object(ipset, "_ipset_cmd", return_value="A"):
            mock = MagicMock(return_value=True)
            with patch.dict(ipset.__salt__, {"cmd.run": mock}):
                assert ipset.rename_set("set", "new_set")


def test_list_sets():
    """
    Test for List all ipset sets.
    """
    with patch.object(ipset, "_ipset_cmd", return_value="A"):
        mock = MagicMock(return_value="A:a")
        with patch.dict(ipset.__salt__, {"cmd.run": mock}):
            assert ipset.list_sets() == [{"A": ""}]


def test_check_set():
    """
    Test for Check that given ipset set exists.
    """
    assert ipset.check_set() == "Error: Set needs to be specified"

    with patch.object(ipset, "_find_set_info", side_effect=[False, True]):
        assert not ipset.check_set("set")
        assert ipset.check_set("set")


def test_add():
    """
    Test for Append an entry to the specified set.
    """
    assert ipset.add() == "Error: Set needs to be specified"

    assert ipset.add("set") == "Error: Entry needs to be specified"

    with patch.object(ipset, "_find_set_info", return_value=None):
        assert ipset.add("set", "entry") == "Error: Set set does not exist"

    mock = MagicMock(return_value={"Type": "type", "Header": "Header"})
    with patch.object(ipset, "_find_set_info", mock):
        assert (
            ipset.add("set", "entry", timeout=0)
            == "Error: Set set not created with timeout support"
        )

        assert (
            ipset.add("set", "entry", packets=0)
            == "Error: Set set not created with counters support"
        )

        assert (
            ipset.add("set", "entry", comment=0)
            == "Error: Set set not created with comment support"
        )

    mock = MagicMock(return_value={"Type": "bitmap:ip", "Header": "Header"})
    with patch.object(ipset, "_find_set_info", mock):
        with patch.object(ipset, "_find_set_members", return_value="entry"):
            assert (
                ipset.add("set", "entry")
                == "Warn: Entry entry already exists in set set"
            )

        with patch.object(ipset, "_find_set_members", return_value="A"):
            mock = MagicMock(return_value="")
            with patch.dict(ipset.__salt__, {"cmd.run": mock}):
                assert ipset.add("set", "entry") == "Success"

            mock = MagicMock(return_value="out")
            with patch.dict(ipset.__salt__, {"cmd.run": mock}):
                assert ipset.add("set", "entry") == "Error: out"


def test_delete():
    """
    Test for Delete an entry from the specified set.
    """
    assert ipset.delete() == "Error: Set needs to be specified"

    assert ipset.delete("s") == "Error: Entry needs to be specified"

    with patch.object(ipset, "_find_set_type", return_value=None):
        assert ipset.delete("set", "entry") == "Error: Set set does not exist"

    with patch.object(ipset, "_find_set_type", return_value=True):
        with patch.object(ipset, "_ipset_cmd", return_value="A"):
            mock = MagicMock(side_effect=["", "A"])
            with patch.dict(ipset.__salt__, {"cmd.run": mock}):
                assert ipset.delete("set", "entry") == "Success"
                assert ipset.delete("set", "entry") == "Error: A"


def test_check():
    """
    Test for Check that an entry exists in the specified set.
    """
    assert ipset.check() == "Error: Set needs to be specified"

    assert ipset.check("s") == "Error: Entry needs to be specified"

    with patch.object(ipset, "_find_set_type", return_value=None):
        assert ipset.check("set", "entry") == "Error: Set set does not exist"

    with patch.object(ipset, "_find_set_type", return_value="hash:ip"):
        with patch.object(
            ipset,
            "_find_set_members",
            side_effect=[
                "entry",
                "",
                ["192.168.0.4", "192.168.0.5"],
                ["192.168.0.3"],
                ["192.168.0.6"],
                ["192.168.0.4", "192.168.0.5"],
                ["192.168.0.3"],
                ["192.168.0.6"],
            ],
        ):
            assert ipset.check("set", "entry")
            assert not ipset.check("set", "entry")
            assert ipset.check("set", "192.168.0.4/31")
            assert not ipset.check("set", "192.168.0.4/31")
            assert not ipset.check("set", "192.168.0.4/31")
            assert ipset.check("set", "192.168.0.4-192.168.0.5")
            assert not ipset.check("set", "192.168.0.4-192.168.0.5")
            assert not ipset.check("set", "192.168.0.4-192.168.0.5")

    with patch.object(ipset, "_find_set_type", return_value="hash:net"):
        with patch.object(
            ipset,
            "_find_set_members",
            side_effect=[
                "entry",
                "",
                "192.168.0.4/31",
                "192.168.0.4/30",
                "192.168.0.4/31",
                "192.168.0.4/30",
            ],
        ):
            assert ipset.check("set", "entry")
            assert not ipset.check("set", "entry")
            assert ipset.check("set", "192.168.0.4/31")
            assert not ipset.check("set", "192.168.0.4/31")
            assert ipset.check("set", "192.168.0.4-192.168.0.5")
            assert not ipset.check("set", "192.168.0.4-192.168.0.5")


def test_test():
    """
    Test for Test if an entry is in the specified set.
    """
    assert ipset.test() == "Error: Set needs to be specified"

    assert ipset.test("s") == "Error: Entry needs to be specified"

    with patch.object(ipset, "_find_set_type", return_value=None):
        assert ipset.test("set", "entry") == "Error: Set set does not exist"

    with patch.object(ipset, "_find_set_type", return_value=True):
        mock = MagicMock(side_effect=[{"retcode": 1}, {"retcode": -1}])
        with patch.dict(ipset.__salt__, {"cmd.run_all": mock}):
            assert not ipset.test("set", "entry")
            assert ipset.test("set", "entry")


def test_flush():
    """
    Test for Flush entries in the specified set
    """
    mock = MagicMock(side_effect=["", "A"])
    with patch.dict(ipset.__salt__, {"cmd.run": mock}):
        assert ipset.flush("set")
        assert not ipset.flush("set")

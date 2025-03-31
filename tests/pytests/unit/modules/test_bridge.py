"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import pytest

import salt.modules.bridge as bridge
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {bridge: {}}


def test_show():
    """
    Test for Returns bridges interfaces
    along with enslaved physical interfaces
    """
    mock = MagicMock(return_value=True)
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.show("br")


def test_list_():
    """
    Test for Returns the machine's bridges list
    """
    mock = MagicMock(return_value=None)
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.list_() is None

    mock = MagicMock(return_value=["A", "B"])
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.list_() == ["A", "B"]


def test_interfaces():
    """
    Test for Returns interfaces attached to a bridge
    """
    assert bridge.interfaces() is None

    mock = MagicMock(return_value={"interfaces": "A"})
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.interfaces("br") == "A"


def test_find_interfaces():
    """
    Test for Returns the bridge to which the interfaces are bond to
    """
    mock = MagicMock(return_value=None)
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.find_interfaces() is None

    mock = MagicMock(return_value={"interfaces": "A"})
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.find_interfaces() == {}


def test_add():
    """
    Test for Creates a bridge
    """
    mock = MagicMock(return_value="A")
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.add() == "A"


def test_delete():
    """
    Test for Deletes a bridge
    """
    mock = MagicMock(return_value="A")
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.delete() == "A"


def test_addif():
    """
    Test for Adds an interface to a bridge
    """
    mock = MagicMock(return_value="A")
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.addif() == "A"


def test_delif():
    """
    Test for Removes an interface from a bridge
    """
    mock = MagicMock(return_value="A")
    with patch.object(bridge, "_os_dispatch", mock):
        assert bridge.delif() == "A"


def test_stp():
    """
    Test for Sets Spanning Tree Protocol state for a bridge
    """
    with patch.dict(bridge.__grains__, {"kernel": "Linux"}):
        mock = MagicMock(return_value="Linux")
        with patch.object(bridge, "_os_dispatch", mock):
            assert bridge.stp() == "Linux"

    with patch.dict(bridge.__grains__, {"kernel": "FreeBSD"}):
        mock = MagicMock(return_value="FreeBSD")
        with patch.object(bridge, "_os_dispatch", mock):
            assert bridge.stp() == "FreeBSD"

    with patch.dict(bridge.__grains__, {"kernel": None}):
        assert not bridge.stp()

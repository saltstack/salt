"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    TestCase for salt.modules.znc
"""

import pytest

import salt.modules.znc as znc
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {znc: {}}


# 'buildmod' function tests: 1


def test_buildmod():
    """
    Tests build module using znc-buildmod
    """
    with patch("os.path.exists", MagicMock(return_value=False)):
        assert (
            znc.buildmod("modules.cpp")
            == "Error: The file (modules.cpp) does not exist."
        )


def test_buildmod_module():
    """
    Tests build module using znc-buildmod
    """
    mock = MagicMock(return_value="SALT")
    with patch.dict(znc.__salt__, {"cmd.run": mock}), patch(
        "os.path.exists", MagicMock(return_value=True)
    ):
        assert znc.buildmod("modules.cpp") == "SALT"


# 'dumpconf' function tests: 1


def test_dumpconf():
    """
    Tests write the active configuration state to config file
    """
    mock = MagicMock(return_value="SALT")
    with patch.dict(znc.__salt__, {"ps.pkill": mock}), patch.object(
        znc, "signal", MagicMock()
    ):
        assert znc.dumpconf() == "SALT"


# 'rehashconf' function tests: 1


def test_rehashconf():
    """
    Tests rehash the active configuration state from config file
    """
    mock = MagicMock(return_value="SALT")
    with patch.dict(znc.__salt__, {"ps.pkill": mock}), patch.object(
        znc, "signal", MagicMock()
    ):
        assert znc.rehashconf() == "SALT"


# 'version' function tests: 1


def test_version():
    """
    Tests return server version from znc --version
    """
    mock = MagicMock(return_value="ZNC 1.2 - http://znc.in")
    with patch.dict(znc.__salt__, {"cmd.run": mock}):
        assert znc.version() == "ZNC 1.2"

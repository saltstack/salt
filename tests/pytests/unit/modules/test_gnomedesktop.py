"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.gnomedesktop
"""

import pytest

import salt.modules.gnomedesktop as gnomedesktop
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {gnomedesktop: {}}


def test_ping():
    """
    Test for A test to ensure the GNOME module is loaded
    """
    assert gnomedesktop.ping()


def test_getidledelay():
    """
    Test for Return the current idle delay setting in seconds
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        with patch.object(gsettings_mock, "_get", return_value=True):
            assert gnomedesktop.getIdleDelay()


def test_setidledelay():
    """
    Test for Set the current idle delay setting in seconds
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        with patch.object(gsettings_mock, "_set", return_value=True):
            assert gnomedesktop.setIdleDelay(5)


def test_getclockformat():
    """
    Test for Return the current clock format, either 12h or 24h format.
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        with patch.object(gsettings_mock, "_get", return_value=True):
            assert gnomedesktop.getClockFormat()


def test_setclockformat():
    """
    Test for Set the clock format, either 12h or 24h format..
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        with patch.object(gsettings_mock, "_set", return_value=True):
            assert gnomedesktop.setClockFormat("12h")

        assert not gnomedesktop.setClockFormat("a")


def test_getclockshowdate():
    """
    Test for Return the current setting, if the date is shown in the clock
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        with patch.object(gsettings_mock, "_get", return_value=True):
            assert gnomedesktop.getClockShowDate()


def test_setclockshowdate():
    """
    Test for Set whether the date is visible in the clock
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        assert not gnomedesktop.setClockShowDate("kvalue")

        with patch.object(gsettings_mock, "_get", return_value=True):
            assert gnomedesktop.setClockShowDate(True)


def test_getidleactivation():
    """
    Test for Get whether the idle activation is enabled
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        with patch.object(gsettings_mock, "_get", return_value=True):
            assert gnomedesktop.getIdleActivation()


def test_setidleactivation():
    """
    Test for Set whether the idle activation is enabled
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        assert not gnomedesktop.setIdleActivation("kvalue")

        with patch.object(gsettings_mock, "_set", return_value=True):
            assert gnomedesktop.setIdleActivation(True)


def test_get():
    """
    Test for Get key in a particular GNOME schema
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        with patch.object(gsettings_mock, "_get", return_value=True):
            assert gnomedesktop.get()


def test_set_():
    """
    Test for Set key in a particular GNOME schema.
    """
    with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
        with patch.object(gsettings_mock, "_get", return_value=True):
            assert gnomedesktop.set_()

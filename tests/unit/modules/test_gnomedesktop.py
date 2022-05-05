"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import salt.modules.gnomedesktop as gnomedesktop
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class GnomedesktopTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.gnomedesktop
    """

    def setup_loader_modules(self):
        return {gnomedesktop: {}}

    def test_ping(self):
        """
        Test for A test to ensure the GNOME module is loaded
        """
        self.assertTrue(gnomedesktop.ping())

    def test_getidledelay(self):
        """
        Test for Return the current idle delay setting in seconds
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            with patch.object(gsettings_mock, "_get", return_value=True):
                self.assertTrue(gnomedesktop.getIdleDelay())

    def test_setidledelay(self):
        """
        Test for Set the current idle delay setting in seconds
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            with patch.object(gsettings_mock, "_set", return_value=True):
                self.assertTrue(gnomedesktop.setIdleDelay(5))

    def test_getclockformat(self):
        """
        Test for Return the current clock format, either 12h or 24h format.
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            with patch.object(gsettings_mock, "_get", return_value=True):
                self.assertTrue(gnomedesktop.getClockFormat())

    def test_setclockformat(self):
        """
        Test for Set the clock format, either 12h or 24h format..
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            with patch.object(gsettings_mock, "_set", return_value=True):
                self.assertTrue(gnomedesktop.setClockFormat("12h"))

            self.assertFalse(gnomedesktop.setClockFormat("a"))

    def test_getclockshowdate(self):
        """
        Test for Return the current setting, if the date is shown in the clock
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            with patch.object(gsettings_mock, "_get", return_value=True):
                self.assertTrue(gnomedesktop.getClockShowDate())

    def test_setclockshowdate(self):
        """
        Test for Set whether the date is visible in the clock
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            self.assertFalse(gnomedesktop.setClockShowDate("kvalue"))

            with patch.object(gsettings_mock, "_get", return_value=True):
                self.assertTrue(gnomedesktop.setClockShowDate(True))

    def test_getidleactivation(self):
        """
        Test for Get whether the idle activation is enabled
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            with patch.object(gsettings_mock, "_get", return_value=True):
                self.assertTrue(gnomedesktop.getIdleActivation())

    def test_setidleactivation(self):
        """
        Test for Set whether the idle activation is enabled
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            self.assertFalse(gnomedesktop.setIdleActivation("kvalue"))

            with patch.object(gsettings_mock, "_set", return_value=True):
                self.assertTrue(gnomedesktop.setIdleActivation(True))

    def test_get(self):
        """
        Test for Get key in a particular GNOME schema
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            with patch.object(gsettings_mock, "_get", return_value=True):
                self.assertTrue(gnomedesktop.get())

    def test_set_(self):
        """
        Test for Set key in a particular GNOME schema.
        """
        with patch("salt.modules.gnomedesktop._GSettings") as gsettings_mock:
            with patch.object(gsettings_mock, "_get", return_value=True):
                self.assertTrue(gnomedesktop.set_())

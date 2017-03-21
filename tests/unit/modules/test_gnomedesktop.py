# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.gnomedesktop as gnomedesktop


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GnomedesktopTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.gnomedesktop
    '''
    loader_module = gnomedesktop

    def test_ping(self):
        '''
        Test for A test to ensure the GNOME module is loaded
        '''
        self.assertTrue(gnomedesktop.ping())

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_getidledelay(self, gsettings_mock):
        '''
        Test for Return the current idle delay setting in seconds
        '''
        with patch.object(gsettings_mock, '_get', return_value=True):
            self.assertTrue(gnomedesktop.getIdleDelay())

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_setidledelay(self, gsettings_mock):
        '''
        Test for Set the current idle delay setting in seconds
        '''
        with patch.object(gsettings_mock, '_set', return_value=True):
            self.assertTrue(gnomedesktop.setIdleDelay(5))

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_getclockformat(self, gsettings_mock):
        '''
        Test for Return the current clock format, either 12h or 24h format.
        '''
        with patch.object(gsettings_mock, '_get', return_value=True):
            self.assertTrue(gnomedesktop.getClockFormat())

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_setclockformat(self, gsettings_mock):
        '''
        Test for Set the clock format, either 12h or 24h format..
        '''
        with patch.object(gsettings_mock, '_set', return_value=True):
            self.assertTrue(gnomedesktop.setClockFormat('12h'))

        self.assertFalse(gnomedesktop.setClockFormat('a'))

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_getclockshowdate(self, gsettings_mock):
        '''
        Test for Return the current setting, if the date is shown in the clock
        '''
        with patch.object(gsettings_mock, '_get', return_value=True):
            self.assertTrue(gnomedesktop.getClockShowDate())

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_setclockshowdate(self, gsettings_mock):
        '''
        Test for Set whether the date is visible in the clock
        '''
        self.assertFalse(gnomedesktop.setClockShowDate('kvalue'))

        with patch.object(gsettings_mock, '_get', return_value=True):
            self.assertTrue(gnomedesktop.setClockShowDate(True))

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_getidleactivation(self, gsettings_mock):
        '''
        Test for Get whether the idle activation is enabled
        '''
        with patch.object(gsettings_mock, '_get', return_value=True):
            self.assertTrue(gnomedesktop.getIdleActivation())

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_setidleactivation(self, gsettings_mock):
        '''
        Test for Set whether the idle activation is enabled
        '''
        self.assertFalse(gnomedesktop.setIdleActivation('kvalue'))

        with patch.object(gsettings_mock, '_set', return_value=True):
            self.assertTrue(gnomedesktop.setIdleActivation(True))

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_get(self, gsettings_mock):
        '''
        Test for Get key in a particular GNOME schema
        '''
        with patch.object(gsettings_mock, '_get', return_value=True):
            self.assertTrue(gnomedesktop.get())

    @patch('salt.modules.gnomedesktop._GSettings')
    def test_set_(self, gsettings_mock):
        '''
        Test for Set key in a particular GNOME schema.
        '''
        with patch.object(gsettings_mock, '_get', return_value=True):
            self.assertTrue(gnomedesktop.set_())

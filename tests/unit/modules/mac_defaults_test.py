# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import mac_defaults as macdefaults

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch
)

ensure_in_syspath('../../')

macdefaults.__salt__ = {}


class MacDefaultsTestCase(TestCase):

    def test_write_default(self):
        '''
            Test writing a default setting
        '''
        mock = MagicMock()
        with patch.dict(macdefaults.__salt__, {'cmd.run_all': mock}):
            macdefaults.write('com.apple.CrashReporter', 'DialogType', 'Server')
            mock.assert_called_once_with('defaults write "com.apple.CrashReporter" "DialogType" -string "Server"',
                                         runas=None)

    def test_write_with_user(self):
        '''
            Test writing a default setting with a specific user
        '''
        mock = MagicMock()
        with patch.dict(macdefaults.__salt__, {'cmd.run_all': mock}):
            macdefaults.write('com.apple.CrashReporter', 'DialogType', 'Server', user="frank")
            mock.assert_called_once_with('defaults write "com.apple.CrashReporter" "DialogType" -string "Server"',
                                         runas="frank")

    def test_write_default_boolean(self):
        '''
            Test writing a default setting
        '''
        mock = MagicMock()
        with patch.dict(macdefaults.__salt__, {'cmd.run_all': mock}):
            macdefaults.write('com.apple.CrashReporter', 'Crash', True, type="boolean")
            mock.assert_called_once_with('defaults write "com.apple.CrashReporter" "Crash" -boolean "TRUE"',
                                         runas=None)

    def test_read_default(self):
        '''
            Test reading a default setting
        '''
        mock = MagicMock()
        with patch.dict(macdefaults.__salt__, {'cmd.run': mock}):
            macdefaults.read('com.apple.CrashReporter', 'Crash')
            mock.assert_called_once_with('defaults read "com.apple.CrashReporter" "Crash"', runas=None)

    def test_read_default_with_user(self):
        '''
            Test reading a default setting as a specific user
        '''
        mock = MagicMock()
        with patch.dict(macdefaults.__salt__, {'cmd.run': mock}):
            macdefaults.read('com.apple.CrashReporter', 'Crash', user="frank")
            mock.assert_called_once_with('defaults read "com.apple.CrashReporter" "Crash"', runas="frank")


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacDefaultsTestCase, needs_daemon=False)

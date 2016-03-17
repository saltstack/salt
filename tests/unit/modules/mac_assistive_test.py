# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import mac_assistive as assistive

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch
)

ensure_in_syspath('../../')

assistive.__salt__ = {}


class AssistiveTestCase(TestCase):

    def test_install_assistive_bundle(self):
        '''
            Test installing a bundle ID as being allowed to run with assistive access
        '''
        mock = MagicMock()
        with patch.dict(assistive.__salt__, {'cmd.run': mock}):
            assistive.install('com.apple.Chess')
            mock.assert_called_once_with('sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" '
                                         '"INSERT or REPLACE INTO access '
                                         'VALUES(\'kTCCServiceAccessibility\',\'com.apple.Chess\',0,1,1,NULL)"')

    def test_install_assistive_bundle_disable(self):
        '''
            Test installing a bundle ID as being allowed to run with assistive access
        '''
        mock = MagicMock()
        with patch.dict(assistive.__salt__, {'cmd.run': mock}):
            assistive.install('com.apple.Chess', False)
            mock.assert_called_once_with('sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" '
                                         '"INSERT or REPLACE INTO access '
                                         'VALUES(\'kTCCServiceAccessibility\',\'com.apple.Chess\',0,0,1,NULL)"')

    def test_install_assistive_command(self):
        '''
            Test installing a command as being allowed to run with assistive access
        '''
        mock = MagicMock()
        with patch.dict(assistive.__salt__, {'cmd.run': mock}):
            assistive.install('/usr/bin/osascript')
            mock.assert_called_once_with('sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" '
                                         '"INSERT or REPLACE INTO access '
                                         'VALUES(\'kTCCServiceAccessibility\',\'/usr/bin/osascript\',1,1,1,NULL)"')

    def test_installed_bundle(self):
        '''
            Test checking to see if a bundle id is installed as being able to use assistive access
        '''
        mock = MagicMock(return_value="kTCCServiceAccessibility|/bin/bash|1|1|1|\n"
                                      "kTCCServiceAccessibility|com.apple.Chess|0|1|1|")
        with patch.dict(assistive.__salt__, {'cmd.run': mock}):
            out = assistive.installed('com.apple.Chess')
            mock.assert_called_once_with('sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db"'
                                         ' "SELECT * FROM access"')

            self.assertEqual(out, True)

    def test_installed_bundle_not(self):
        '''
            Test checking to see if a bundle id is installed as being able to use assistive access
        '''
        mock = MagicMock(return_value="kTCCServiceAccessibility|/bin/bash|1|1|1|\n"
                                      "kTCCServiceAccessibility|com.apple.Safari|0|1|1|")
        with patch.dict(assistive.__salt__, {'cmd.run': mock}):
            out = assistive.installed('com.apple.Chess')
            mock.assert_called_once_with('sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db"'
                                         ' "SELECT * FROM access"')

            self.assertEqual(out, False)

    @patch("salt.modules.mac_assistive._get_assistive_access")
    def test_enable_assistive(self, get_assistive_mock):
        '''
            Test enabling a bundle ID as being allowed to run with assistive access
        '''
        get_assistive_mock.return_value = [("com.apple.Chess", '1')]
        mock = MagicMock()

        with patch.dict(assistive.__salt__, {'cmd.run': mock}):
            assistive.enable('com.apple.Chess')
            mock.assert_called_once_with('sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" '
                                         '"UPDATE access SET allowed=\'1\' WHERE client=\'com.apple.Chess\'"')
            get_assistive_mock.assert_called_once_with()

    @patch("salt.modules.mac_assistive._get_assistive_access")
    def test_disable_assistive(self, get_assistive_mock):
        '''
            Test dsiabling a bundle ID as being allowed to run with assistive access
        '''
        get_assistive_mock.return_value = [("com.apple.Chess", '1')]
        mock = MagicMock()

        with patch.dict(assistive.__salt__, {'cmd.run': mock}):
            assistive.enable('com.apple.Chess', False)
            mock.assert_called_once_with('sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" '
                                         '"UPDATE access SET allowed=\'0\' WHERE client=\'com.apple.Chess\'"')
            get_assistive_mock.assert_called_once_with()

    @patch("salt.modules.mac_assistive._get_assistive_access")
    def test_enabled_assistive(self, get_assistive_mock):
        '''
            Test if a bundle ID is enabled for assistive access
        '''
        get_assistive_mock.return_value = [("com.apple.Chess", '1')]

        out = assistive.enabled('com.apple.Chess')
        get_assistive_mock.assert_called_once_with()
        self.assertTrue(out)

    def test_get_assistive_access(self):
        '''
            Test if a bundle ID is enabled for assistive access
        '''
        expected = [('/bin/bash', '1'), ('/usr/bin/osascript', '1')]
        mock = MagicMock(return_value="kTCCServiceAccessibility|/bin/bash|1|1|1|\n"
                                      "kTCCServiceAccessibility|/usr/bin/osascript|1|1|1|")

        with patch.dict(assistive.__salt__, {'cmd.run': mock}):
            out = assistive._get_assistive_access()
            mock.assert_called_once_with('sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" '
                                         '"SELECT * FROM access"')
            self.assertEqual(out, expected)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AssistiveTestCase, needs_daemon=False)

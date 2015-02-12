# -*- coding: utf-8 -*-

# Import python libs
import os

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestWhich(integration.TestCase):
    '''
    Tests salt.utils.which function to ensure that it returns True as
    expected.
    '''

    # The mock patch bellow will make sure that ALL calls to the which function
    # returns None
    @patch('salt.utils.which', lambda exe: None)
    def test_missing_binary_in_linux(self):
        self.assertTrue(
            salt.utils.which('this-binary-does-not-exist') is None
        )

    # The mock patch bellow will make sure that ALL calls to the which function
    # return whatever is sent to it
    @patch('salt.utils.which', lambda exe: exe)
    def test_existing_binary_in_linux(self):
        self.assertTrue(salt.utils.which('this-binary-exists-under-linux'))

    # The mock patch bellow, since we're not providing the return value, we
    # will be able to tweak it within the test case. The testcase MUST accept
    # an arguemnt which is the MagicMock'ed object
    @patch('os.access')
    def test_existing_binary_in_windows(self, osaccess):
        # We define the side_effect attribute on the mocked object in order to
        # specify which calls return which values. First call to os.access
        # returns X, the second Y, the third Z, etc...
        osaccess.side_effect = [
            # The first os.access should return False(the abspath one)
            False,
            # The second, iterating through $PATH, should also return False,
            # still checking for Linux
            False,
            # Lastly return True, this is the windows check.
            True
        ]
        # Let's patch os.environ to provide a custom PATH variable
        with patch.dict(os.environ, {'PATH': '/bin'}):
            # Let's also patch is_windows to return True
            with patch('salt.utils.is_windows', lambda: True):
                with patch('os.path.isfile', lambda x: True):
                    self.assertEqual(
                        salt.utils.which('this-binary-exists-under-windows'),
                        # The returned path should return the .exe suffix
                        '/bin/this-binary-exists-under-windows.EXE'
                    )

    @patch('os.access')
    def test_missing_binary_in_windows(self, osaccess):
        osaccess.side_effect = [
            # The first os.access should return False(the abspath one)
            False,
            # The second, iterating through $PATH, should also return False,
            # still checking for Linux
            False,
            # Lastly return True, this is the windows check.
            True
        ]
        # Let's patch os.environ to provide a custom PATH variable
        with patch.dict(os.environ, {'PATH': '/bin'}):
            # Let's also patch is_widows to return True
            with patch('salt.utils.is_windows', lambda: True):
                self.assertEqual(
                    # Since we're passing the .exe suffix, the last True above
                    # will not matter. The result will be None
                    salt.utils.which('this-binary-is-missing-in-windows.exe'),
                    None
                )

    # The mock patch bellow, since we're not providing the return value, we
    # will be able to tweak it within the test case. The testcase MUST accept
    # an arguemnt which is the MagicMock'ed object
    @patch('os.access')
    def test_existing_binary_in_windows_pathext(self, osaccess):
        # We define the side_effect attribute on the mocked object in order to
        # specify which calls return which values. First call to os.access
        # returns X, the second Y, the third Z, etc...
        osaccess.side_effect = [
            # The first os.access should return False(the abspath one)
            False,
            # The second, iterating through $PATH, should also return False,
            # still checking for Linux
            False,
            # We will now also return False 3 times so we get a .CMD back from
            # the function, see PATHEXT below.
            # Lastly return True, this is the windows check.
            False, False, False,
            True
        ]
        # Let's patch os.environ to provide a custom PATH variable
        with patch.dict(os.environ, {'PATH': '/bin',
                                     'PATHEXT': '.COM;.EXE;.BAT;.CMD;.VBS;'
                                     '.VBE;.JS;.JSE;.WSF;.WSH;.MSC;.PY'}):
            # Let's also patch is_windows to return True
            with patch('salt.utils.is_windows', lambda: True):
                with patch('os.path.isfile', lambda x: True):
                    self.assertEqual(
                        salt.utils.which('this-binary-exists-under-windows'),
                        # The returned path should return the .exe suffix
                        '/bin/this-binary-exists-under-windows.CMD'
                    )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestWhich, needs_daemon=False)

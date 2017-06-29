# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch

# Import salt libs
import salt.utils


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestWhich(TestCase):
    '''
    Tests salt.utils.which function to ensure that it returns True as
    expected.
    '''

    # The mock patch below will make sure that ALL calls to the which function
    # returns None
    def test_missing_binary_in_linux(self):
        with patch('salt.utils.which', lambda exe: None):
            self.assertTrue(
                salt.utils.which('this-binary-does-not-exist') is None
            )

    # The mock patch below will make sure that ALL calls to the which function
    # return whatever is sent to it
    def test_existing_binary_in_linux(self):
        with patch('salt.utils.which', lambda exe: exe):
            self.assertTrue(salt.utils.which('this-binary-exists-under-linux'))

    def test_existing_binary_in_windows(self):
        with patch('os.access') as osaccess:
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

    def test_missing_binary_in_windows(self):
        with patch('os.access') as osaccess:
            osaccess.side_effect = [
                # The first os.access should return False(the abspath one)
                False,
                # The second, iterating through $PATH, should also return False,
                # still checking for Linux
                # which() will add 4 extra paths to the given one, os.access will
                # be called 5 times
                False, False, False, False, False
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

    def test_existing_binary_in_windows_pathext(self):
        with patch('os.access') as osaccess:
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

# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import composer
from salt.exceptions import CommandExecutionError


# Globals
composer.__grains__ = {}
composer.__salt__ = {}
composer.__context__ = {}
composer.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ComposerTestCase(TestCase):
    '''
    Test cases for salt.modules.composer
    '''
    def test_install(self):
        '''
        Test for Install composer dependencies for a directory.
        '''
        mock = MagicMock(return_value=False)
        msg = "'composer.install' is not available. Couldn't find 'composer'."
        with patch.object(composer, '_valid_composer', mock):
            self.assertEqual(composer.install('dir'), msg)

        mock = MagicMock(return_value=True)
        msg = "'dir' is required for 'composer.install'"
        with patch.object(composer, '_valid_composer', mock):
            self.assertEqual(composer.install(None), msg)

        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value={'retcode': 1, 'stderr': 'A'})
            with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                self.assertRaises(CommandExecutionError, composer.install, 'd')

        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value={'retcode': 0, 'stderr': 'A'})
            with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                self.assertTrue(composer.install('dir', None, None, None, None,
                                                 None, None, None, None, None,
                                                 True))

        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value={'retcode': 0, 'stderr': 'A',
                                           'stdout': 'B'})
            with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                self.assertEqual(composer.install('dir'), 'B')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ComposerTestCase, needs_daemon=False)

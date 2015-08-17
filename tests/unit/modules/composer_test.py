# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

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
from salt.exceptions import CommandExecutionError, CommandNotFoundError, SaltInvocationError


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

        # Test _valid_composer=False throws exception
        mock = MagicMock(return_value=False)
        with patch.object(composer, '_valid_composer', mock):
            self.assertRaises(CommandNotFoundError, composer.install, 'd')

        # Test no directory specified throws exception
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            self.assertRaises(SaltInvocationError, composer.install, None)

        # Test `composer install` exit status != 0 throws exception
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value={'retcode': 1, 'stderr': 'A'})
            with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                self.assertRaises(CommandExecutionError, composer.install, 'd')

        # Test success with quiet=True returns True
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value={'retcode': 0, 'stderr': 'A'})
            with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                self.assertTrue(composer.install('dir', None, None, None, None,
                                                 None, None, None, None, None,
                                                 True))

        # Test success with quiet=False returns object
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            rval = {'retcode': 0, 'stderr': 'A', 'stdout': 'B'}
            mock = MagicMock(return_value=rval)
            with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                self.assertEqual(composer.install('dir'), rval)

    def test_update(self):
        '''
        Test for Update composer dependencies for a directory.
        '''

        # Test _valid_composer=False throws exception
        mock = MagicMock(return_value=False)
        with patch.object(composer, '_valid_composer', mock):
            self.assertRaises(CommandNotFoundError, composer.update, 'd')

        # Test no directory specified throws exception
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value=True)
            with patch.object(composer, 'did_composer_install', mock):
                self.assertRaises(SaltInvocationError, composer.update, None)

        # Test update with error exit status throws exception
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value=True)
            with patch.object(composer, 'did_composer_install', mock):
                mock = MagicMock(return_value={'retcode': 1, 'stderr': 'A'})
                with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                    self.assertRaises(CommandExecutionError, composer.update, 'd')

        # Test update with existing vendor directory and quiet=True
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value=True)
            with patch.object(composer, 'did_composer_install', mock):
                mock = MagicMock(return_value={'retcode': 0, 'stderr': 'A'})
                with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                    self.assertTrue(composer.update('dir', None, None, None, None,
                                                    None, None, None, None, None,
                                                    True))

        # Test update with no vendor directory and quiet=True
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value=False)
            with patch.object(composer, 'did_composer_install', mock):
                mock = MagicMock(return_value={'retcode': 0, 'stderr': 'A'})
                with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                    self.assertTrue(composer.update('dir', None, None, None, None,
                                                    None, None, None, None, None,
                                                    True))

        # Test update with existing vendor directory
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value=True)
            with patch.object(composer, 'did_composer_install', mock):
                rval = {'retcode': 0, 'stderr': 'A', 'stdout': 'B'}
                mock = MagicMock(return_value=rval)
                with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                    self.assertEqual(composer.update('dir'), rval)

        # Test update with no vendor directory
        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value=False)
            with patch.object(composer, 'did_composer_install', mock):
                rval = {'retcode': 0, 'stderr': 'A', 'stdout': 'B'}
                mock = MagicMock(return_value=rval)
                with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                    self.assertEqual(composer.update('dir'), rval)

    def test_selfupdate(self):
        '''
        Test for Composer selfupdate
        '''
        mock = MagicMock(return_value=False)
        with patch.object(composer, '_valid_composer', mock):
            self.assertRaises(CommandNotFoundError, composer.selfupdate)

        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value={'retcode': 1, 'stderr': 'A'})
            with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                self.assertRaises(CommandExecutionError, composer.selfupdate)

        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            mock = MagicMock(return_value={'retcode': 0, 'stderr': 'A'})
            with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                self.assertTrue(composer.selfupdate(quiet=True))

        mock = MagicMock(return_value=True)
        with patch.object(composer, '_valid_composer', mock):
            rval = {'retcode': 0, 'stderr': 'A', 'stdout': 'B'}
            mock = MagicMock(return_value=rval)
            with patch.dict(composer.__salt__, {'cmd.run_all': mock}):
                self.assertEqual(composer.selfupdate(), rval)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ComposerTestCase, needs_daemon=False)

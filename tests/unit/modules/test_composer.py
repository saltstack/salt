# -*- coding: utf-8 -*-
"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.composer as composer
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    SaltInvocationError,
)

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ComposerTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.composer
    """

    def setup_loader_modules(self):
        return {composer: {}}

    def test_install(self):
        """
        Test for Install composer dependencies for a directory.
        """

        # Test _valid_composer=False throws exception
        mock = MagicMock(return_value=False)
        with patch.object(composer, "_valid_composer", mock):
            self.assertRaises(CommandNotFoundError, composer.install, "d")

        # Test no directory specified throws exception
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            self.assertRaises(SaltInvocationError, composer.install, None)

        # Test `composer install` exit status != 0 throws exception
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value={"retcode": 1, "stderr": "A"})
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                self.assertRaises(CommandExecutionError, composer.install, "d")

        # Test success with quiet=True returns True
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value={"retcode": 0, "stderr": "A"})
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                self.assertTrue(
                    composer.install(
                        "dir",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        True,
                    )
                )

        # Test success with quiet=False returns object
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            rval = {"retcode": 0, "stderr": "A", "stdout": "B"}
            mock = MagicMock(return_value=rval)
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                self.assertEqual(composer.install("dir"), rval)

    def test_update(self):
        """
        Test for Update composer dependencies for a directory.
        """

        # Test _valid_composer=False throws exception
        mock = MagicMock(return_value=False)
        with patch.object(composer, "_valid_composer", mock):
            self.assertRaises(CommandNotFoundError, composer.update, "d")

        # Test no directory specified throws exception
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value=True)
            with patch.object(composer, "did_composer_install", mock):
                self.assertRaises(SaltInvocationError, composer.update, None)

        # Test update with error exit status throws exception
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value=True)
            with patch.object(composer, "did_composer_install", mock):
                mock = MagicMock(return_value={"retcode": 1, "stderr": "A"})
                with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                    self.assertRaises(CommandExecutionError, composer.update, "d")

        # Test update with existing vendor directory and quiet=True
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value=True)
            with patch.object(composer, "did_composer_install", mock):
                mock = MagicMock(return_value={"retcode": 0, "stderr": "A"})
                with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                    self.assertTrue(
                        composer.update(
                            "dir",
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            True,
                        )
                    )

        # Test update with no vendor directory and quiet=True
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value=False)
            with patch.object(composer, "did_composer_install", mock):
                mock = MagicMock(return_value={"retcode": 0, "stderr": "A"})
                with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                    self.assertTrue(
                        composer.update(
                            "dir",
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            True,
                        )
                    )

        # Test update with existing vendor directory
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value=True)
            with patch.object(composer, "did_composer_install", mock):
                rval = {"retcode": 0, "stderr": "A", "stdout": "B"}
                mock = MagicMock(return_value=rval)
                with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                    self.assertEqual(composer.update("dir"), rval)

        # Test update with no vendor directory
        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value=False)
            with patch.object(composer, "did_composer_install", mock):
                rval = {"retcode": 0, "stderr": "A", "stdout": "B"}
                mock = MagicMock(return_value=rval)
                with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                    self.assertEqual(composer.update("dir"), rval)

    def test_selfupdate(self):
        """
        Test for Composer selfupdate
        """
        mock = MagicMock(return_value=False)
        with patch.object(composer, "_valid_composer", mock):
            self.assertRaises(CommandNotFoundError, composer.selfupdate)

        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value={"retcode": 1, "stderr": "A"})
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                self.assertRaises(CommandExecutionError, composer.selfupdate)

        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            mock = MagicMock(return_value={"retcode": 0, "stderr": "A"})
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                self.assertTrue(composer.selfupdate(quiet=True))

        mock = MagicMock(return_value=True)
        with patch.object(composer, "_valid_composer", mock):
            rval = {"retcode": 0, "stderr": "A", "stdout": "B"}
            mock = MagicMock(return_value=rval)
            with patch.dict(composer.__salt__, {"cmd.run_all": mock}):
                self.assertEqual(composer.selfupdate(), rval)

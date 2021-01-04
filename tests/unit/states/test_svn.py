"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import os

import salt.states.svn as svn
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SvnTestCase(TestCase, LoaderModuleMockMixin):
    """
        Validate the svn state
    """

    def setup_loader_modules(self):
        return {svn: {}}

    def test_latest(self):
        """
            Checkout or update the working directory to
            the latest revision from the remote repository.
        """
        mock = MagicMock(return_value=True)
        with patch.object(svn, "_fail", mock):
            self.assertTrue(svn.latest("salt"))

        mock = MagicMock(side_effect=[True, False, False, False])
        with patch.object(os.path, "exists", mock):
            mock = MagicMock(return_value=False)
            with patch.object(os.path, "isdir", mock):
                with patch.object(svn, "_fail", mock):
                    self.assertFalse(svn.latest("salt", "c://salt"))

            with patch.dict(svn.__opts__, {"test": True}):
                mock = MagicMock(return_value=["salt"])
                with patch.object(svn, "_neutral_test", mock):
                    self.assertListEqual(svn.latest("salt", "c://salt"), ["salt"])

                mock = MagicMock(side_effect=[False, True])
                with patch.object(os.path, "exists", mock):
                    mock = MagicMock(return_value=True)
                    info_mock = MagicMock(return_value=[{"Revision": "mocked"}])
                    with patch.dict(
                        svn.__salt__, {"svn.diff": mock, "svn.info": info_mock}
                    ):
                        mock = MagicMock(return_value=["Dude"])
                        with patch.object(svn, "_neutral_test", mock):
                            self.assertListEqual(
                                svn.latest("salt", "c://salt"), ["Dude"]
                            )

            with patch.dict(svn.__opts__, {"test": False}):
                mock = MagicMock(return_value=[{"Revision": "a"}])
                with patch.dict(svn.__salt__, {"svn.info": mock}):
                    mock = MagicMock(return_value=True)
                    with patch.dict(svn.__salt__, {"svn.update": mock}):
                        self.assertDictEqual(
                            svn.latest("salt", "c://salt"),
                            {
                                "changes": {},
                                "comment": True,
                                "name": "salt",
                                "result": True,
                            },
                        )

    def test_latest_trust_failures(self):
        """
            Test that checks that the trust_failures option is handled
            correctly when running svn.latest in test mode. This tests for the
            bug reported as #59069.
        """
        os_path_exists_mock = MagicMock(side_effect=[False, True])
        svn_info_mock = MagicMock(return_value=[{"Revision": "42"}])
        svn_diff_mock = MagicMock()
        svn_neutral_test_mock = MagicMock()
        with patch.object(os.path, "exists", os_path_exists_mock), patch.dict(
            svn.__opts__, {"test": True}
        ), patch.dict(
            svn.__salt__, {"svn.diff": svn_diff_mock, "svn.info": svn_info_mock}
        ), patch.object(
            svn, "_neutral_test", svn_neutral_test_mock
        ):
            svn.latest("salt", "/my/test/dir", trust_failures="unknown-ca")
            svn_diff_mock.assert_called_with(
                "/my/test",
                "/my/test/dir",
                None,
                None,
                None,
                "-r",
                "42:HEAD",
                "--trust-server-cert-failures",
                "unknown-ca",
            )

    def test_export(self):
        """
            Test to export a file or directory from an SVN repository
        """
        mock = MagicMock(return_value=True)
        with patch.object(svn, "_fail", mock):
            self.assertTrue(svn.export("salt"))

        mock = MagicMock(side_effect=[True, False, False, False])
        with patch.object(os.path, "exists", mock):
            mock = MagicMock(return_value=False)
            with patch.object(os.path, "isdir", mock):
                with patch.object(svn, "_fail", mock):
                    self.assertFalse(svn.export("salt", "c://salt"))

            with patch.dict(svn.__opts__, {"test": True}):
                mock = MagicMock(return_value=["salt"])
                with patch.object(svn, "_neutral_test", mock):
                    self.assertListEqual(svn.export("salt", "c://salt"), ["salt"])

                mock = MagicMock(side_effect=[False, True])
                with patch.object(os.path, "exists", mock):
                    mock = MagicMock(return_value=True)
                    with patch.dict(svn.__salt__, {"svn.list": mock}):
                        mock = MagicMock(return_value=["Dude"])
                        with patch.object(svn, "_neutral_test", mock):
                            self.assertListEqual(
                                svn.export("salt", "c://salt"), ["Dude"]
                            )

            with patch.dict(svn.__opts__, {"test": False}):
                mock = MagicMock(return_value=True)
                with patch.dict(svn.__salt__, {"svn.export": mock}):
                    self.assertDictEqual(
                        svn.export("salt", "c://salt"),
                        {
                            "changes": {
                                "new": "salt",
                                "comment": "salt was Exported to c://salt",
                            },
                            "comment": True,
                            "name": "salt",
                            "result": True,
                        },
                    )

    def test_dirty(self):
        """
            Test to determine if the working directory has been changed.
        """
        mock = MagicMock(return_value=True)
        with patch.object(svn, "_fail", mock):
            self.assertTrue(svn.dirty("salt", "c://salt"))

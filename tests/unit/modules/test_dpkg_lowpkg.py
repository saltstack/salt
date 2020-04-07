# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt Libs
import salt.modules.dpkg_lowpkg as dpkg

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DpkgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.dpkg
    """

    def setup_loader_modules(self):
        return {dpkg: {}}

    # 'unpurge' function tests: 2

    def test_unpurge(self):
        """
        Test if it change package selection for each package
        specified to 'install'
        """
        mock = MagicMock(return_value=[])
        with patch.dict(dpkg.__salt__, {"pkg.list_pkgs": mock, "cmd.run": mock}):
            self.assertDictEqual(dpkg.unpurge("curl"), {})

    def test_unpurge_empty_package(self):
        """
        Test if it change package selection for each package
        specified to 'install'
        """
        self.assertDictEqual(dpkg.unpurge(), {})

    # 'list_pkgs' function tests: 1

    def test_list_pkgs(self):
        """
        Test if it lists the packages currently installed
        """
        mock = MagicMock(return_value={"retcode": 0, "stderr": "", "stdout": "Salt"})
        with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(dpkg.list_pkgs("httpd"), {})

        mock = MagicMock(
            return_value={"retcode": 1, "stderr": "error", "stdout": "Salt"}
        )
        with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(dpkg.list_pkgs("httpd"), "Error:  error")

    # 'file_list' function tests: 1

    def test_file_list(self):
        """
        Test if it lists the files that belong to a package.
        """
        mock = MagicMock(return_value={"retcode": 0, "stderr": "", "stdout": "Salt"})
        with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(dpkg.file_list("httpd"), {"errors": [], "files": []})

        mock = MagicMock(
            return_value={"retcode": 1, "stderr": "error", "stdout": "Salt"}
        )
        with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(dpkg.file_list("httpd"), "Error:  error")

    # 'file_dict' function tests: 1

    def test_file_dict(self):
        """
        Test if it lists the files that belong to a package, grouped by package
        """
        mock = MagicMock(return_value={"retcode": 0, "stderr": "", "stdout": "Salt"})
        with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
            self.assertDictEqual(
                dpkg.file_dict("httpd"), {"errors": [], "packages": {}}
            )

        mock = MagicMock(
            return_value={"retcode": 1, "stderr": "error", "stdout": "Salt"}
        )
        with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
            self.assertEqual(dpkg.file_dict("httpd"), "Error:  error")

    def test_info(self):
        """
        Test package info
        """
        mock = MagicMock(
            return_value={
                "retcode": 0,
                "stderr": "",
                "stdout": os.linesep.join(
                    [
                        "package:bash",
                        "revision:",
                        "architecture:amd64",
                        "maintainer:Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>",
                        "summary:",
                        "source:bash",
                        "version:4.4.18-2ubuntu1",
                        "section:shells",
                        "installed_size:1588",
                        "size:",
                        "MD5:",
                        "SHA1:",
                        "SHA256:",
                        "origin:",
                        "homepage:http://tiswww.case.edu/php/chet/bash/bashtop.html",
                        "status:ii ",
                        "======",
                        "description:GNU Bourne Again SHell",
                        " Bash is an sh-compatible command language interpreter that executes",
                        " commands read from the standard input or from a file.  Bash also",
                        " incorporates useful features from the Korn and C shells (ksh and csh).",
                        " .",
                        " Bash is ultimately intended to be a conformant implementation of the",
                        " IEEE POSIX Shell and Tools specification (IEEE Working Group 1003.2).",
                        " .",
                        " The Programmable Completion Code, by Ian Macdonald, is now found in",
                        " the bash-completion package.",
                        "------",
                    ]
                ),
            }
        )

        with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}), patch.dict(
            dpkg.__grains__, {"os": "Ubuntu", "osrelease_info": (18, 4)}
        ), patch("salt.utils.path.which", MagicMock(return_value=False)), patch(
            "os.path.exists", MagicMock(return_value=False)
        ), patch(
            "os.path.getmtime", MagicMock(return_value=1560199259.0)
        ):
            self.assertDictEqual(
                dpkg.info("bash"),
                {
                    "bash": {
                        "architecture": "amd64",
                        "description": os.linesep.join(
                            [
                                "GNU Bourne Again SHell",
                                " Bash is an sh-compatible command language interpreter that executes",
                                " commands read from the standard input or from a file.  Bash also",
                                " incorporates useful features from the Korn and C shells (ksh and csh).",
                                " .",
                                " Bash is ultimately intended to be a conformant implementation of the",
                                " IEEE POSIX Shell and Tools specification (IEEE Working Group 1003.2).",
                                " .",
                                " The Programmable Completion Code, by Ian Macdonald, is now found in",
                                " the bash-completion package." + os.linesep,
                            ]
                        ),
                        "homepage": "http://tiswww.case.edu/php/chet/bash/bashtop.html",
                        "maintainer": "Ubuntu Developers "
                        "<ubuntu-devel-discuss@lists.ubuntu.com>",
                        "package": "bash",
                        "section": "shells",
                        "source": "bash",
                        "status": "ii",
                        "version": "4.4.18-2ubuntu1",
                    }
                },
            )

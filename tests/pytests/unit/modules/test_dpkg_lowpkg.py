"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.dpkg
"""

import logging
import os

import pytest

import salt.modules.dpkg_lowpkg as dpkg
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {dpkg: {}}


def setUp(self):
    dpkg_lowpkg_logger = logging.getLogger("salt.modules.dpkg_lowpkg")
    self.level = dpkg_lowpkg_logger.level
    dpkg_lowpkg_logger.setLevel(logging.FATAL)


def tearDown(self):
    logging.getLogger("salt.modules.dpkg_lowpkg").setLevel(self.level)


def dpkg_L_side_effect(cmd, **kwargs):
    assert cmd[:2] == ["dpkg", "-L"]
    package = cmd[2]
    return dpkg_l_output[package]


dpkg_error_msg = """dpkg-query: package 'httpd' is not installed
Use dpkg --contents (= dpkg-deb --contents) to list archive files contents.
"""


dpkg_l_output = {
    "hostname": """\
/.
/bin
/bin/hostname
/usr
/usr/share
/usr/share/doc
/usr/share/doc/hostname
/usr/share/doc/hostname/changelog.gz
/usr/share/doc/hostname/copyright
/usr/share/man
/usr/share/man/man1
/usr/share/man/man1/hostname.1.gz
/bin/dnsdomainname
/bin/domainname
/bin/nisdomainname
/bin/ypdomainname
/usr/share/man/man1/dnsdomainname.1.gz
/usr/share/man/man1/domainname.1.gz
/usr/share/man/man1/nisdomainname.1.gz
/usr/share/man/man1/ypdomainname.1.gz
"""
}


# 'unpurge' function tests: 2


def test_unpurge():
    """
    Test if it change package selection for each package
    specified to 'install'
    """
    mock = MagicMock(return_value=[])
    with patch.dict(dpkg.__salt__, {"pkg.list_pkgs": mock, "cmd.run": mock}):
        assert dpkg.unpurge("curl") == {}


def test_unpurge_empty_package():
    """
    Test if it change package selection for each package
    specified to 'install'
    """
    assert dpkg.unpurge() == {}


# 'list_pkgs' function tests: 1


def test_list_pkgs():
    """
    Test if it lists the packages currently installed
    """
    mock = MagicMock(
        return_value={
            "retcode": 0,
            "stderr": "",
            "stdout": "installed\thostname\t3.21",
        }
    )
    with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
        assert dpkg.list_pkgs("hostname") == {"hostname": "3.21"}

    mock = MagicMock(
        return_value={
            "retcode": 1,
            "stderr": "dpkg-query: no packages found matching httpd",
            "stdout": "",
        }
    )
    with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
        assert (
            dpkg.list_pkgs("httpd")
            == "Error:  dpkg-query: no packages found matching httpd"
        )


# 'file_list' function tests: 1


def test_file_list():
    """
    Test if it lists the files that belong to a package.
    """
    dpkg_query_mock = MagicMock(
        return_value={"retcode": 0, "stderr": "", "stdout": "installed\thostname"}
    )
    dpkg_L_mock = MagicMock(side_effect=dpkg_L_side_effect)
    with patch.dict(
        dpkg.__salt__, {"cmd.run_all": dpkg_query_mock, "cmd.run": dpkg_L_mock}
    ):
        assert dpkg.file_list("hostname") == {
            "errors": [],
            "files": [
                "/.",
                "/bin",
                "/bin/dnsdomainname",
                "/bin/domainname",
                "/bin/hostname",
                "/bin/nisdomainname",
                "/bin/ypdomainname",
                "/usr",
                "/usr/share",
                "/usr/share/doc",
                "/usr/share/doc/hostname",
                "/usr/share/doc/hostname/changelog.gz",
                "/usr/share/doc/hostname/copyright",
                "/usr/share/man",
                "/usr/share/man/man1",
                "/usr/share/man/man1/dnsdomainname.1.gz",
                "/usr/share/man/man1/domainname.1.gz",
                "/usr/share/man/man1/hostname.1.gz",
                "/usr/share/man/man1/nisdomainname.1.gz",
                "/usr/share/man/man1/ypdomainname.1.gz",
            ],
        }

    mock = MagicMock(
        return_value={"retcode": 1, "stderr": dpkg_error_msg, "stdout": ""}
    )
    with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
        assert dpkg.file_list("httpd") == "Error:  " + dpkg_error_msg


# 'file_dict' function tests: 1


def test_file_dict():
    """
    Test if it lists the files that belong to a package, grouped by package
    """
    dpkg_query_mock = MagicMock(
        return_value={"retcode": 0, "stderr": "", "stdout": "installed\thostname"}
    )
    dpkg_L_mock = MagicMock(side_effect=dpkg_L_side_effect)
    with patch.dict(
        dpkg.__salt__, {"cmd.run_all": dpkg_query_mock, "cmd.run": dpkg_L_mock}
    ):
        expected = {
            "errors": [],
            "packages": {
                "hostname": [
                    "/.",
                    "/bin",
                    "/bin/hostname",
                    "/usr",
                    "/usr/share",
                    "/usr/share/doc",
                    "/usr/share/doc/hostname",
                    "/usr/share/doc/hostname/changelog.gz",
                    "/usr/share/doc/hostname/copyright",
                    "/usr/share/man",
                    "/usr/share/man/man1",
                    "/usr/share/man/man1/hostname.1.gz",
                    "/bin/dnsdomainname",
                    "/bin/domainname",
                    "/bin/nisdomainname",
                    "/bin/ypdomainname",
                    "/usr/share/man/man1/dnsdomainname.1.gz",
                    "/usr/share/man/man1/domainname.1.gz",
                    "/usr/share/man/man1/nisdomainname.1.gz",
                    "/usr/share/man/man1/ypdomainname.1.gz",
                ]
            },
        }
        assert dpkg.file_dict("hostname") == expected

    mock = MagicMock(
        return_value={"retcode": 1, "stderr": dpkg_error_msg, "stdout": ""}
    )
    with patch.dict(dpkg.__salt__, {"cmd.run_all": mock}):
        assert dpkg.file_dict("httpd") == "Error:  " + dpkg_error_msg


def test_bin_pkg_info_spaces():
    """
    Test the bin_pkg_info function
    """
    file_proto_mock = MagicMock(return_value=True)
    with patch.dict(dpkg.__salt__, {"config.valid_fileproto": file_proto_mock}):
        cache_mock = MagicMock(return_value="/path/to/some/package.deb")
        with patch.dict(dpkg.__salt__, {"cp.cache_file": cache_mock}):
            dpkg_info_mock = MagicMock(
                return_value={
                    "retcode": 0,
                    "stderr": "",
                    "stdout": (
                        " new Debian package, version 2.0\n"
                        " size 123456 bytes: control archive: 4029  bytes.\n"
                        " Package          : package_name\n"
                        " Version          : 1.0\n"
                        " Section          : section_name\n"
                        " Priority         : priority\n"
                        " Architecture     : all\n"
                        " Description      : some package\n"
                    ),
                }
            )
            with patch.dict(dpkg.__salt__, {"cmd.run_all": dpkg_info_mock}):
                assert dpkg.bin_pkg_info("package.deb")["name"] == "package_name"


def test_bin_pkg_info_no_spaces():
    """
    Test the bin_pkg_info function
    """
    file_proto_mock = MagicMock(return_value=True)
    with patch.dict(dpkg.__salt__, {"config.valid_fileproto": file_proto_mock}):
        cache_mock = MagicMock(return_value="/path/to/some/package.deb")
        with patch.dict(dpkg.__salt__, {"cp.cache_file": cache_mock}):
            dpkg_info_mock = MagicMock(
                return_value={
                    "retcode": 0,
                    "stderr": "",
                    "stdout": (
                        " new Debian package, version 2.0\n"
                        " size 123456 bytes: control archive: 4029  bytes.\n"
                        " Package: package_name\n"
                        " Version: 1.0\n"
                        " Section: section_name\n"
                        " Priority: priority\n"
                        " Architecture: all\n"
                        " Description: some package\n"
                    ),
                }
            )
            with patch.dict(dpkg.__salt__, {"cmd.run_all": dpkg_info_mock}):
                assert dpkg.bin_pkg_info("package.deb")["name"] == "package_name"


def test_info():
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
                    "maintainer:Ubuntu Developers"
                    " <ubuntu-devel-discuss@lists.ubuntu.com>",
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
                    "description:GNU Bourne Again SHell",
                    " Bash is an sh-compatible command language interpreter that"
                    " executes",
                    " commands read from the standard input or from a file.  Bash"
                    " also",
                    " incorporates useful features from the Korn and C shells (ksh"
                    " and csh).",
                    " .",
                    " Bash is ultimately intended to be a conformant implementation"
                    " of the",
                    " IEEE POSIX Shell and Tools specification (IEEE Working Group"
                    " 1003.2).",
                    " .",
                    " The Programmable Completion Code, by Ian Macdonald, is now"
                    " found in",
                    " the bash-completion package.",
                    "",
                    "*/~^\\*",  # pylint: disable=W1401
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
        assert dpkg.info("bash") == {
            "bash": {
                "architecture": "amd64",
                "description": os.linesep.join(
                    [
                        "GNU Bourne Again SHell",
                        " Bash is an sh-compatible command language interpreter"
                        " that executes",
                        " commands read from the standard input or from a file."
                        "  Bash also",
                        " incorporates useful features from the Korn and C"
                        " shells (ksh and csh).",
                        " .",
                        " Bash is ultimately intended to be a conformant"
                        " implementation of the",
                        " IEEE POSIX Shell and Tools specification (IEEE"
                        " Working Group 1003.2).",
                        " .",
                        " The Programmable Completion Code, by Ian Macdonald,"
                        " is now found in",
                        " the bash-completion package." + os.linesep,
                    ]
                ),
                "homepage": "http://tiswww.case.edu/php/chet/bash/bashtop.html",
                "maintainer": (
                    "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>"
                ),
                "package": "bash",
                "section": "shells",
                "source": "bash",
                "status": "ii",
                "version": "4.4.18-2ubuntu1",
            }
        }


def test_get_pkg_license():
    """
    Test _get_pkg_license for ignore errors on reading license from copyright files
    """
    license_read_mock = mock_open(read_data="")
    with patch.object(os.path, "exists", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", license_read_mock
    ):
        dpkg._get_pkg_license("bash")

        assert license_read_mock.calls[0].args[0] == "/usr/share/doc/bash/copyright"
        assert license_read_mock.calls[0].kwargs["errors"] == "ignore"

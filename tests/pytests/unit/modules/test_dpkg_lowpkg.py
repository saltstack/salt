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
                    "install_date:1560199259",
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
                "install_date": "2019-06-10T20:40:59Z",
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


def test_info_uses_dpkg_query_only(tmp_path):
    """
    Regression test for https://github.com/saltstack/salt/issues/52605:
    dpkg_lowpkg must not read /var/lib/dpkg/{available,info/*.list} directly.
    It must only invoke dpkg-query. Lintian flags direct dpkg-database access
    via the ``uses-dpkg-database-directly`` tag.
    """
    seen_cmds = []

    def fake_run_all(cmd, **kwargs):
        seen_cmds.append(cmd)
        return {
            "retcode": 0,
            "stderr": "",
            "stdout": os.linesep.join(
                [
                    "package:bash",
                    "revision:",
                    "architecture:amd64",
                    "maintainer:",
                    "summary:",
                    "source:bash",
                    "version:4.4.18",
                    "section:shells",
                    "installed_size:1588",
                    "size:",
                    "MD5:",
                    "SHA1:",
                    "SHA256:",
                    "origin:",
                    "homepage:",
                    "status:ii ",
                    "install_date:1560199259",
                    "description:GNU Bourne Again SHell",
                    "",
                    "*/~^\\*",  # pylint: disable=W1401
                ]
            ),
        }

    # The dpkg-query call must be passed as a list (no shell), and dselect
    # is mocked absent so dpkg-query --print-avail is not invoked.
    with patch.dict(
        dpkg.__salt__, {"cmd.run_all": MagicMock(side_effect=fake_run_all)}
    ), patch.dict(dpkg.__grains__, {"os": "Ubuntu", "osrelease_info": (18, 4)}), patch(
        "salt.utils.path.which", MagicMock(return_value=False)
    ), patch(
        "os.path.exists", MagicMock(return_value=False)
    ):
        dpkg.info("bash")

    # First (and only) cmd.run_all call must be `dpkg-query -W ...` as a list,
    # not a shell string. This pins the "pass cmd as list" half of the fix.
    assert seen_cmds, "cmd.run_all was never called"
    cmd = seen_cmds[0]
    assert isinstance(cmd, list), f"cmd must be a list, got {type(cmd).__name__}"
    assert cmd[0] == "dpkg-query"
    assert cmd[1] == "-W"
    # The format string must request install_date from dpkg's public field,
    # not from /var/lib/dpkg/info/<pkg>.list mtime.
    assert "${db-fsys:Last-Modified}" in cmd[2]
    # No call to dpkg-query should reference /var/lib/dpkg internals.
    for seen in seen_cmds:
        assert "/var/lib/dpkg/info" not in " ".join(seen)
        assert "/var/lib/dpkg/available" not in " ".join(seen)


def test_info_handles_missing_install_date():
    """
    Older dpkg (< 1.19.3) does not expose ``${db-fsys:Last-Modified}`` and
    substitutes an empty value. Salt must not crash and must omit
    ``install_date`` from the result rather than raising.
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
                    "maintainer:",
                    "summary:",
                    "source:bash",
                    "version:4.4.18",
                    "section:shells",
                    "installed_size:1588",
                    "size:",
                    "MD5:",
                    "SHA1:",
                    "SHA256:",
                    "origin:",
                    "homepage:",
                    "status:ii ",
                    "install_date:",
                    "description:GNU Bourne Again SHell",
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
    ):
        result = dpkg.info("bash")

    assert "install_date" not in result["bash"]
    assert result["bash"]["package"] == "bash"


def test_get_pkg_ds_avail_uses_dpkg_query():
    """
    ``_get_pkg_ds_avail`` must call ``dpkg-query --print-avail`` instead of
    reading ``/var/lib/dpkg/available`` directly. When dselect is not
    installed it returns an empty dict without invoking dpkg-query.
    """
    # dselect absent: must not call dpkg-query, returns empty dict.
    run_all_mock = MagicMock()
    with patch("salt.utils.path.which", MagicMock(return_value=None)), patch.dict(
        dpkg.__salt__, {"cmd.run_all": run_all_mock}
    ):
        assert dpkg._get_pkg_ds_avail() == {}
    assert run_all_mock.call_count == 0

    # dselect present: must call `dpkg-query --print-avail` as a list, parse output.
    run_all_mock = MagicMock(
        return_value={
            "retcode": 0,
            "stderr": "",
            "stdout": (
                "Package: bash\n"
                "Architecture: amd64\n"
                "Version: 4.4.18-2ubuntu1\n"
                "\n"
                "Package: hostname\n"
                "Architecture: amd64\n"
                "Version: 3.20\n"
            ),
        }
    )
    with patch(
        "salt.utils.path.which", MagicMock(return_value="/usr/bin/dselect")
    ), patch.dict(dpkg.__salt__, {"cmd.run_all": run_all_mock}):
        result = dpkg._get_pkg_ds_avail()

    assert run_all_mock.call_count == 1
    called_cmd = run_all_mock.call_args[0][0]
    assert isinstance(called_cmd, list)
    assert called_cmd == ["dpkg-query", "--print-avail"]
    # parsed entries must contain both packages with lowercased keys
    assert "bash" in result
    assert result["bash"]["package"] == "bash"
    assert "hostname" in result


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

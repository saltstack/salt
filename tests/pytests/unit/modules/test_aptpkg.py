"""
    :synopsis: Unit Tests for Advanced Packaging Tool module 'module.aptpkg'
    :platform: Linux
    :maturity: develop
    versionadded:: 2017.7.0
"""


import copy
import logging
import os
import pathlib
import textwrap

import pytest
import salt.modules.aptpkg as aptpkg
import salt.modules.pkg_resource as pkg_resource
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    SaltInvocationError,
)
from tests.support.mock import MagicMock, Mock, call, patch

try:
    from aptsources import sourceslist  # pylint: disable=unused-import

    HAS_APTSOURCES = True
except ImportError:
    HAS_APTSOURCES = False

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def repo_keys_var():
    return {
        "46181433FBB75451": {
            "algorithm": 17,
            "bits": 1024,
            "capability": "scSC",
            "date_creation": 1104433784,
            "date_expiration": None,
            "fingerprint": "C5986B4F1257FFA86632CBA746181433FBB75451",
            "keyid": "46181433FBB75451",
            "uid": "Ubuntu CD Image Automatic Signing Key <cdimage@ubuntu.com>",
            "uid_hash": "B4D41942D4B35FF44182C7F9D00C99AF27B93AD0",
            "validity": "-",
        }
    }


@pytest.fixture(scope="module")
def packages_var():
    return {"wget": "1.15-1ubuntu1.14.04.2"}


@pytest.fixture(scope="module")
def lowpkg_files_var():
    return {
        "errors": {},
        "packages": {
            "wget": [
                "/.",
                "/etc",
                "/etc/wgetrc",
                "/usr",
                "/usr/bin",
                "/usr/bin/wget",
                "/usr/share",
                "/usr/share/info",
                "/usr/share/info/wget.info.gz",
                "/usr/share/doc",
                "/usr/share/doc/wget",
                "/usr/share/doc/wget/MAILING-LIST",
                "/usr/share/doc/wget/NEWS.gz",
                "/usr/share/doc/wget/AUTHORS",
                "/usr/share/doc/wget/copyright",
                "/usr/share/doc/wget/changelog.Debian.gz",
                "/usr/share/doc/wget/README",
                "/usr/share/man",
                "/usr/share/man/man1",
                "/usr/share/man/man1/wget.1.gz",
            ]
        },
    }


@pytest.fixture(scope="module")
def lowpkg_info_var():
    return {
        "wget": {
            "architecture": "amd64",
            "description": "retrieves files from the web",
            "homepage": "http://www.gnu.org/software/wget/",
            "install_date": "2016-08-30T22:20:15Z",
            "maintainer": "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>",
            "name": "wget",
            "section": "web",
            "source": "wget",
            "version": "1.15-1ubuntu1.14.04.2",
            "status": "ii",
        },
        "apache2": {
            "architecture": "amd64",
            "description": """Apache HTTP Server
     The Apache HTTP Server Project's goal is to build a secure, efficient and
     extensible HTTP server as standards-compliant open source software. The
     result has long been the number one web server on the Internet.
     .
     Installing this package results in a full installation, including the
     configuration files, init scripts and support scripts.""",
            "homepage": "http://httpd.apache.org/",
            "install_date": "2016-08-30T22:20:15Z",
            "maintainer": "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>",
            "name": "apache2",
            "section": "httpd",
            "source": "apache2",
            "version": "2.4.18-2ubuntu3.9",
            "status": "rc",
        },
    }


@pytest.fixture(scope="module")
def apt_q_update_var():
    return """
    Get:1 http://security.ubuntu.com trusty-security InRelease [65 kB]
    Get:2 http://security.ubuntu.com trusty-security/main Sources [120 kB]
    Get:3 http://security.ubuntu.com trusty-security/main amd64 Packages [548 kB]
    Get:4 http://security.ubuntu.com trusty-security/main i386 Packages [507 kB]
    Hit http://security.ubuntu.com trusty-security/main Translation-en
    Fetched 1240 kB in 10s (124 kB/s)
    Reading package lists...
    """


@pytest.fixture(scope="module")
def apt_q_update_error_var():
    return """
    Err http://security.ubuntu.com trusty InRelease

    Err http://security.ubuntu.com trusty Release.gpg
    Unable to connect to security.ubuntu.com:http:
    Reading package lists...
    W: Failed to fetch http://security.ubuntu.com/ubuntu/dists/trusty/InRelease

    W: Failed to fetch http://security.ubuntu.com/ubuntu/dists/trusty/Release.gpg  Unable to connect to security.ubuntu.com:http:

    W: Some index files failed to download. They have been ignored, or old ones used instead.
    """


@pytest.fixture(scope="module")
def autoremove_var():
    return """
    Reading package lists... Done
    Building dependency tree
    Reading state information... Done
    0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.
    """


@pytest.fixture(scope="module")
def upgrade_var():
    return """
    Reading package lists...
    Building dependency tree...
    Reading state information...
    0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.
    """


@pytest.fixture(scope="module")
def uninstall_var():
    return {"tmux": {"new": "", "old": "1.8-5"}}


@pytest.fixture(scope="module")
def install_var():
    return {"tmux": {"new": "1.8-5", "old": ""}}


def _get_uri(repo):
    """
    Get the URI portion of the a string
    """
    splits = repo.split()
    for val in splits:
        if any(val.startswith(x) for x in ("http://", "https://", "ftp://")):
            return val


class MockSourceEntry:
    def __init__(self, uri, source_type, line, invalid, dist="", file=None):
        self.uri = uri
        self.type = source_type
        self.line = line
        self.invalid = invalid
        self.file = file
        self.disabled = False
        self.dist = dist
        self.comps = []
        self.architectures = []

    def mysplit(self, line):
        return line.split()


class MockSourceList:
    def __init__(self):
        self.list = []

    def __iter__(self):
        yield from self.list

    def save(self):
        pass


@pytest.fixture
def configure_loader_modules():
    return {aptpkg: {"__grains__": {}}}


def test_version(lowpkg_info_var):
    """
    Test - Returns a string representing the package version or an empty string if
    not installed.
    """
    version = lowpkg_info_var["wget"]["version"]
    mock = MagicMock(return_value=version)
    with patch.dict(aptpkg.__salt__, {"pkg_resource.version": mock}):
        assert aptpkg.version(*["wget"]) == version


def test_upgrade_available():
    """
    Test - Check whether or not an upgrade is available for a given package.
    """
    with patch("salt.modules.aptpkg.latest_version", MagicMock(return_value="")):
        assert aptpkg.upgrade_available("wget") is False


def test_add_repo_key(repo_keys_var):
    """
    Test - Add a repo key.
    """
    with patch(
        "salt.modules.aptpkg.get_repo_keys", MagicMock(return_value=repo_keys_var)
    ):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "OK"})
        with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
            assert (
                aptpkg.add_repo_key(keyserver="keyserver.ubuntu.com", keyid="FBB75451")
                is True
            )


def test_add_repo_key_failed(repo_keys_var):
    """
    Test - Add a repo key using incomplete input data.
    """
    with patch(
        "salt.modules.aptpkg.get_repo_keys", MagicMock(return_value=repo_keys_var)
    ):
        kwargs = {"keyserver": "keyserver.ubuntu.com"}
        mock = MagicMock(return_value={"retcode": 0, "stdout": "OK"})
        with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
            with pytest.raises(SaltInvocationError):
                aptpkg.add_repo_key(**kwargs)


def test_get_repo_keys(repo_keys_var):
    """
    Test - List known repo key details.
    """
    APT_KEY_LIST = r"""
    pub:-:1024:17:46181433FBB75451:1104433784:::-:::scSC:
    fpr:::::::::C5986B4F1257FFA86632CBA746181433FBB75451:
    uid:-::::1104433784::B4D41942D4B35FF44182C7F9D00C99AF27B93AD0::Ubuntu CD Image Automatic Signing Key <cdimage@ubuntu.com>:
    """

    mock = MagicMock(return_value={"retcode": 0, "stdout": APT_KEY_LIST})
    with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
        assert aptpkg.get_repo_keys() == repo_keys_var


def test_file_dict(lowpkg_files_var):
    """
    Test - List the files that belong to a package, grouped by package.
    """
    mock = MagicMock(return_value=lowpkg_files_var)
    with patch.dict(aptpkg.__salt__, {"lowpkg.file_dict": mock}):
        assert aptpkg.file_dict("wget") == lowpkg_files_var


def test_file_list(lowpkg_files_var):
    """
    Test - List the files that belong to a package.
    """
    files = {
        "errors": lowpkg_files_var["errors"],
        "files": lowpkg_files_var["packages"]["wget"],
    }
    mock = MagicMock(return_value=files)
    with patch.dict(aptpkg.__salt__, {"lowpkg.file_list": mock}):
        assert aptpkg.file_list("wget") == files


def test_get_selections():
    """
    Test - View package state from the dpkg database.
    """
    selections = {"install": ["wget"]}
    mock = MagicMock(return_value="wget\t\t\t\t\t\tinstall")
    with patch.dict(aptpkg.__salt__, {"cmd.run_stdout": mock}):
        assert aptpkg.get_selections("wget") == selections


def test_info_installed(lowpkg_info_var):
    """
    Test - Return the information of the named package(s) installed on the system.
    """
    names = {"group": "section", "packager": "maintainer", "url": "homepage"}

    installed = copy.deepcopy({"wget": lowpkg_info_var["wget"]})
    for name in names:
        if installed["wget"].get(names[name], False):
            installed["wget"][name] = installed["wget"].pop(names[name])

    mock = MagicMock(return_value=lowpkg_info_var)
    with patch.dict(aptpkg.__salt__, {"lowpkg.info": mock}):
        del installed["wget"]["status"]
        assert aptpkg.info_installed("wget") == installed
        assert len(aptpkg.info_installed()) == 1


def test_owner():
    """
    Test - Return the name of the package that owns the file.
    """
    paths = ["/usr/bin/wget"]
    mock = MagicMock(return_value="wget: /usr/bin/wget")
    with patch.dict(aptpkg.__salt__, {"cmd.run_stdout": mock}):
        assert aptpkg.owner(*paths) == "wget"


def test_refresh_db(apt_q_update_var):
    """
    Test - Updates the APT database to latest packages based upon repositories.
    """
    refresh_db = {
        "http://security.ubuntu.com trusty-security InRelease": True,
        "http://security.ubuntu.com trusty-security/main Sources": True,
        "http://security.ubuntu.com trusty-security/main Translation-en": None,
        "http://security.ubuntu.com trusty-security/main amd64 Packages": True,
        "http://security.ubuntu.com trusty-security/main i386 Packages": True,
    }
    mock = MagicMock(return_value={"retcode": 0, "stdout": apt_q_update_var})
    with patch("salt.utils.pkg.clear_rtag", MagicMock()):
        with patch.dict(
            aptpkg.__salt__,
            {"cmd.run_all": mock, "config.get": MagicMock(return_value=False)},
        ):
            assert aptpkg.refresh_db() == refresh_db


def test_refresh_db_failed(apt_q_update_error_var):
    """
    Test - Update the APT database using unreachable repositories.
    """
    kwargs = {"failhard": True}
    mock = MagicMock(return_value={"retcode": 0, "stdout": apt_q_update_error_var})
    with patch("salt.utils.pkg.clear_rtag", MagicMock()):
        with patch.dict(
            aptpkg.__salt__,
            {"cmd.run_all": mock, "config.get": MagicMock(return_value=False)},
        ):
            with pytest.raises(CommandExecutionError):
                aptpkg.refresh_db(**kwargs)


def test_autoremove(packages_var, autoremove_var):
    """
    Test - Remove packages not required by another package.
    """
    with patch("salt.modules.aptpkg.list_pkgs", MagicMock(return_value=packages_var)):
        patch_kwargs = {
            "__salt__": {
                "config.get": MagicMock(return_value=True),
                "cmd.run_all": MagicMock(
                    return_value=MagicMock(return_value=autoremove_var)
                ),
            }
        }
        with patch.multiple(aptpkg, **patch_kwargs):
            assert aptpkg.autoremove() == {}
            assert aptpkg.autoremove(purge=True) == {}
            assert aptpkg.autoremove(list_only=True) == []
            assert aptpkg.autoremove(list_only=True, purge=True) == []


def test_install(install_var):
    """
    Test - Install packages.
    """
    with patch("salt.modules.aptpkg.install", MagicMock(return_value=install_var)):
        assert aptpkg.install(name="tmux") == install_var
        kwargs = {"force_conf_new": True}
        assert aptpkg.install(name="tmux", **kwargs) == install_var


def test_remove(uninstall_var):
    """
    Test - Remove packages.
    """
    with patch("salt.modules.aptpkg._uninstall", MagicMock(return_value=uninstall_var)):
        assert aptpkg.remove(name="tmux") == uninstall_var


def test_purge(uninstall_var):
    """
    Test - Remove packages along with all configuration files.
    """
    with patch("salt.modules.aptpkg._uninstall", MagicMock(return_value=uninstall_var)):
        assert aptpkg.purge(name="tmux") == uninstall_var


def test_upgrade(uninstall_var, upgrade_var):
    """
    Test - Upgrades all packages.
    """
    with patch("salt.utils.pkg.clear_rtag", MagicMock()):
        with patch(
            "salt.modules.aptpkg.list_pkgs", MagicMock(return_value=uninstall_var)
        ):
            mock_cmd = MagicMock(return_value={"retcode": 0, "stdout": upgrade_var})
            patch_kwargs = {
                "__salt__": {
                    "config.get": MagicMock(return_value=True),
                    "cmd.run_all": mock_cmd,
                }
            }
            with patch.multiple(aptpkg, **patch_kwargs):
                assert aptpkg.upgrade() == dict()
                kwargs = {"force_conf_new": True}
                assert aptpkg.upgrade(**kwargs) == dict()


def test_upgrade_downloadonly(uninstall_var, upgrade_var):
    """
    Tests the download-only options for upgrade.
    """
    with patch("salt.utils.pkg.clear_rtag", MagicMock()):
        with patch(
            "salt.modules.aptpkg.list_pkgs", MagicMock(return_value=uninstall_var)
        ):
            mock_cmd = MagicMock(return_value={"retcode": 0, "stdout": upgrade_var})
            patch_kwargs = {
                "__salt__": {
                    "config.get": MagicMock(return_value=True),
                    "cmd.run_all": mock_cmd,
                },
            }
            with patch.multiple(aptpkg, **patch_kwargs):
                aptpkg.upgrade()
                args_matching = [
                    True
                    for args in patch_kwargs["__salt__"]["cmd.run_all"].call_args[0]
                    if "--download-only" in args
                ]
                # Here we shouldn't see the parameter and args_matching should be empty.
                assert any(args_matching) is False

                aptpkg.upgrade(downloadonly=True)
                args_matching = [
                    True
                    for args in patch_kwargs["__salt__"]["cmd.run_all"].call_args[0]
                    if "--download-only" in args
                ]
                # --download-only should be in the args list and we should have at least on True in the list.
                assert any(args_matching) is True

                aptpkg.upgrade(download_only=True)
                args_matching = [
                    True
                    for args in patch_kwargs["__salt__"]["cmd.run_all"].call_args[0]
                    if "--download-only" in args
                ]
                # --download-only should be in the args list and we should have at least on True in the list.
                assert any(args_matching) is True


def test_show():
    """
    Test that the pkg.show function properly parses apt-cache show output.
    This test uses an abridged output per package, for simplicity.
    """
    show_mock_success = MagicMock(
        return_value={
            "retcode": 0,
            "pid": 12345,
            "stderr": "",
            "stdout": textwrap.dedent(
                """\
            Package: foo1.0
            Architecture: amd64
            Version: 1.0.5-3ubuntu4
            Description: A silly package (1.0 release cycle)
            Provides: foo
            Suggests: foo-doc

            Package: foo1.0
            Architecture: amd64
            Version: 1.0.4-2ubuntu1
            Description: A silly package (1.0 release cycle)
            Provides: foo
            Suggests: foo-doc

            Package: foo-doc
            Architecture: all
            Version: 1.0.5-3ubuntu4
            Description: Silly documentation for a silly package (1.0 release cycle)

            Package: foo-doc
            Architecture: all
            Version: 1.0.4-2ubuntu1
            Description: Silly documentation for a silly package (1.0 release cycle)

            """
            ),
        }
    )

    show_mock_failure = MagicMock(
        return_value={
            "retcode": 1,
            "pid": 12345,
            "stderr": textwrap.dedent(
                """\
            N: Unable to locate package foo*
            N: Couldn't find any package by glob 'foo*'
            N: Couldn't find any package by regex 'foo*'
            E: No packages found
            """
            ),
            "stdout": "",
        }
    )

    refresh_mock = Mock()

    expected = {
        "foo1.0": {
            "1.0.5-3ubuntu4": {
                "Architecture": "amd64",
                "Description": "A silly package (1.0 release cycle)",
                "Provides": "foo",
                "Suggests": "foo-doc",
            },
            "1.0.4-2ubuntu1": {
                "Architecture": "amd64",
                "Description": "A silly package (1.0 release cycle)",
                "Provides": "foo",
                "Suggests": "foo-doc",
            },
        },
        "foo-doc": {
            "1.0.5-3ubuntu4": {
                "Architecture": "all",
                "Description": (
                    "Silly documentation for a silly package (1.0 release cycle)"
                ),
            },
            "1.0.4-2ubuntu1": {
                "Architecture": "all",
                "Description": (
                    "Silly documentation for a silly package (1.0 release cycle)"
                ),
            },
        },
    }

    # Make a copy of the above dict and strip out some keys to produce the
    # expected filtered result.
    filtered = copy.deepcopy(expected)
    for k1 in filtered:
        for k2 in filtered[k1]:
            # Using list() because we will modify the dict during iteration
            for k3 in list(filtered[k1][k2]):
                if k3 not in ("Description", "Provides"):
                    filtered[k1][k2].pop(k3)

    with patch.dict(aptpkg.__salt__, {"cmd.run_all": show_mock_success}), patch.object(
        aptpkg, "refresh_db", refresh_mock
    ):

        # Test success (no refresh)
        assert aptpkg.show("foo*") == expected
        refresh_mock.assert_not_called()
        refresh_mock.reset_mock()

        # Test success (with refresh)
        assert aptpkg.show("foo*", refresh=True) == expected
        refresh_mock.assert_called_once()
        refresh_mock.reset_mock()

        # Test filtered return
        assert aptpkg.show("foo*", filter="description,provides") == filtered
        refresh_mock.assert_not_called()
        refresh_mock.reset_mock()

    with patch.dict(aptpkg.__salt__, {"cmd.run_all": show_mock_failure}), patch.object(
        aptpkg, "refresh_db", refresh_mock
    ):

        # Test failure (no refresh)
        assert aptpkg.show("foo*") == {}
        refresh_mock.assert_not_called()
        refresh_mock.reset_mock()

        # Test failure (with refresh)
        assert aptpkg.show("foo*", refresh=True) == {}
        refresh_mock.assert_called_once()
        refresh_mock.reset_mock()


@pytest.mark.skipif(
    not (pathlib.Path("/etc") / "apt" / "sources.list").is_file(),
    reason="Requires sources.list file",
)
def test_mod_repo_enabled():
    """
    Checks if a repo is enabled or disabled depending on the passed kwargs.
    """
    with patch.dict(
        aptpkg.__salt__,
        {"config.option": MagicMock(), "no_proxy": MagicMock(return_value=False)},
    ):
        with patch("salt.modules.aptpkg.refresh_db", MagicMock(return_value={})):
            with patch(
                "salt.utils.data.is_true", MagicMock(return_value=True)
            ) as data_is_true:
                with patch("salt.modules.aptpkg.SourcesList", MagicMock(), create=True):
                    with patch(
                        "salt.modules.aptpkg.SourceEntry", MagicMock(), create=True
                    ):
                        repo = aptpkg.mod_repo("foo", enabled=False)
                        data_is_true.assert_called_with(False)
                        # with disabled=True; should call salt.utils.data.is_true True
                        data_is_true.reset_mock()
                        repo = aptpkg.mod_repo("foo", disabled=True)
                        data_is_true.assert_called_with(True)
                        # with enabled=True; should call salt.utils.data.is_true with False
                        data_is_true.reset_mock()
                        repo = aptpkg.mod_repo("foo", enabled=True)
                        data_is_true.assert_called_with(True)
                        # with disabled=True; should call salt.utils.data.is_true False
                        data_is_true.reset_mock()
                        repo = aptpkg.mod_repo("foo", disabled=False)
                        data_is_true.assert_called_with(False)


def test_mod_repo_match():
    """
    Checks if a repo is matched without taking into account any ending "/" in the uri.
    """
    source_type = "deb"
    source_uri = "http://cdn-aws.deb.debian.org/debian/"
    source_line = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"

    mock_source = MockSourceEntry(
        source_uri, source_type, source_line, False, "stretch"
    )
    mock_source_list = MockSourceList()
    mock_source_list.list = [mock_source]

    with patch.dict(
        aptpkg.__salt__,
        {"config.option": MagicMock(), "no_proxy": MagicMock(return_value=False)},
    ):
        with patch("salt.modules.aptpkg.refresh_db", MagicMock(return_value={})):
            with patch("salt.utils.data.is_true", MagicMock(return_value=True)):
                with patch("salt.modules.aptpkg.SourceEntry", MagicMock(), create=True):
                    with patch(
                        "salt.modules.aptpkg.SourcesList",
                        MagicMock(return_value=mock_source_list),
                        create=True,
                    ):
                        with patch(
                            "salt.modules.aptpkg._split_repo_str",
                            MagicMock(
                                return_value=(
                                    "deb",
                                    [],
                                    "http://cdn-aws.deb.debian.org/debian/",
                                    "stretch",
                                    ["main"],
                                )
                            ),
                        ):
                            source_line_no_slash = (
                                "deb http://cdn-aws.deb.debian.org/debian"
                                " stretch main"
                            )
                            repo = aptpkg.mod_repo(source_line_no_slash, enabled=False)
                            assert repo[source_line_no_slash]["uri"] == source_uri


@patch("salt.utils.path.os_walk", MagicMock(return_value=[("test", "test", "test")]))
@patch("os.path.getsize", MagicMock(return_value=123456))
@patch("os.path.getctime", MagicMock(return_value=1234567890.123456))
@patch(
    "fnmatch.filter",
    MagicMock(return_value=["/var/cache/apt/archive/test_package.rpm"]),
)
def test_list_downloaded():
    """
    Test downloaded packages listing.
    :return:
    """
    DOWNLOADED_RET = {
        "test-package": {
            "1.0": {
                "path": "/var/cache/apt/archive/test_package.rpm",
                "size": 123456,
                "creation_date_time_t": 1234567890,
                "creation_date_time": "2009-02-13T23:31:30",
            }
        }
    }

    with patch.dict(
        aptpkg.__salt__,
        {
            "lowpkg.bin_pkg_info": MagicMock(
                return_value={"name": "test-package", "version": "1.0"}
            )
        },
    ):
        list_downloaded = aptpkg.list_downloaded()
        assert len(list_downloaded) == 1
        assert list_downloaded == DOWNLOADED_RET


def test__skip_source():
    """
    Test __skip_source.
    :return:
    """
    # Valid source
    source_type = "deb"
    source_uri = "http://cdn-aws.deb.debian.org/debian"
    source_line = "deb http://cdn-aws.deb.debian.org/debian stretch main\n"

    mock_source = MockSourceEntry(source_uri, source_type, source_line, False)

    ret = aptpkg._skip_source(mock_source)
    assert ret is False

    # Invalid source type
    source_type = "ded"
    source_uri = "http://cdn-aws.deb.debian.org/debian"
    source_line = "deb http://cdn-aws.deb.debian.org/debian stretch main\n"

    mock_source = MockSourceEntry(source_uri, source_type, source_line, True)

    ret = aptpkg._skip_source(mock_source)
    assert ret is True

    # Invalid source type , not skipped
    source_type = "deb"
    source_uri = "http://cdn-aws.deb.debian.org/debian"
    source_line = "deb [http://cdn-aws.deb.debian.org/debian] stretch main\n"

    mock_source = MockSourceEntry(source_uri, source_type, source_line, True)

    ret = aptpkg._skip_source(mock_source)
    assert ret is False


def test_normalize_name():
    """
    Test that package is normalized only when it should be
    """
    with patch.dict(aptpkg.__grains__, {"osarch": "amd64"}):
        result = aptpkg.normalize_name("foo")
        assert result == "foo", result
        result = aptpkg.normalize_name("foo:amd64")
        assert result == "foo", result
        result = aptpkg.normalize_name("foo:any")
        assert result == "foo", result
        result = aptpkg.normalize_name("foo:all")
        assert result == "foo", result
        result = aptpkg.normalize_name("foo:i386")
        assert result == "foo:i386", result


def test_list_repos():
    """
    Checks results from list_repos
    """
    # Valid source
    source_type = "deb"
    source_uri = "http://cdn-aws.deb.debian.org/debian/"
    source_line = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"

    mock_source = MockSourceEntry(source_uri, source_type, source_line, False)
    mock_source_list = MockSourceList()
    mock_source_list.list = [mock_source]

    with patch("salt.modules.aptpkg.SourcesList", MagicMock(), create=True):
        with patch("salt.modules.aptpkg.SourceEntry", MagicMock(), create=True):
            with patch(
                "salt.modules.aptpkg.SourcesList",
                MagicMock(return_value=mock_source_list),
                create=True,
            ):
                repos = aptpkg.list_repos()
                assert source_uri in repos

                assert isinstance(repos[source_uri], list)
                assert len(repos[source_uri]) == 1

                # Make sure last character in of the URI in line is still a /
                assert "line" in repos[source_uri][0]
                _uri = _get_uri(repos[source_uri][0]["line"])
                assert _uri[-1] == "/"

                # Make sure last character in URI is still a /
                assert "uri" in repos[source_uri][0]
                assert repos[source_uri][0]["uri"][-1] == "/"


@pytest.mark.skipif(
    HAS_APTSOURCES is False, reason="The 'aptsources' library is missing."
)
def test_expand_repo_def():
    """
    Checks results from expand_repo_def
    """
    source_type = "deb"
    source_uri = "http://cdn-aws.deb.debian.org/debian/"
    source_line = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"
    source_file = "/etc/apt/sources.list"

    # Valid source
    repo = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"
    sanitized = aptpkg.expand_repo_def(repo=repo, file=source_file)

    assert isinstance(sanitized, dict)
    assert "uri" in sanitized

    # Make sure last character in of the URI is still a /
    assert sanitized["uri"][-1] == "/"

    # Pass the architecture and make sure it is added the the line attribute
    repo = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"
    sanitized = aptpkg.expand_repo_def(
        repo=repo, file=source_file, architectures="amd64"
    )

    # Make sure line is in the dict
    assert isinstance(sanitized, dict)
    assert "line" in sanitized

    # Make sure the architecture is in line
    assert (
        sanitized["line"]
        == "deb [arch=amd64] http://cdn-aws.deb.debian.org/debian/ stretch main"
    )


def test_list_pkgs():
    """
    Test packages listing.

    :return:
    """

    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    apt_out = [
        "install ok installed accountsservice 0.6.55-0ubuntu12~20.04.1 amd64",
        "install ok installed acpid 1:2.0.32-1ubuntu1 amd64",
        "install ok installed adduser 3.118ubuntu2 all",
        "install ok installed alsa-topology-conf 1.2.2-1 all",
        "install ok installed alsa-ucm-conf 1.2.2-1ubuntu0.4 all",
        "install ok installed apparmor 2.13.3-7ubuntu5.1 amd64",
        "install ok installed apport 2.20.11-0ubuntu27.9 all",
        "install ok installed apport-symptoms 0.23 all",
        "install ok installed apt 2.0.2ubuntu0.1 amd64",
        "install ok installed apt-utils 2.0.2ubuntu0.1 amd64",
        "install ok installed at 3.1.23-1ubuntu1 amd64",
    ]
    with patch.dict(aptpkg.__grains__, {"osarch": "x86_64"}), patch.dict(
        aptpkg.__salt__,
        {"cmd.run_stdout": MagicMock(return_value=os.linesep.join(apt_out))},
    ), patch.dict(aptpkg.__salt__, {"pkg_resource.add_pkg": _add_data}), patch.dict(
        aptpkg.__salt__,
        {"pkg_resource.format_pkg_list": pkg_resource.format_pkg_list},
    ), patch.dict(
        aptpkg.__salt__, {"pkg_resource.sort_pkglist": pkg_resource.sort_pkglist}
    ):
        pkgs = aptpkg.list_pkgs(versions_as_list=True)
        for pkg_name, pkg_version in {
            "accountsservice": "0.6.55-0ubuntu12~20.04.1",
            "acpid": "1:2.0.32-1ubuntu1",
            "adduser": "3.118ubuntu2",
            "alsa-topology-conf": "1.2.2-1",
            "alsa-ucm-conf": "1.2.2-1ubuntu0.4",
            "apparmor": "2.13.3-7ubuntu5.1",
            "apport": "2.20.11-0ubuntu27.9",
            "apport-symptoms": "0.23",
            "apt": "2.0.2ubuntu0.1",
            "apt-utils": "2.0.2ubuntu0.1",
            "at": "3.1.23-1ubuntu1",
        }.items():
            assert pkgs[pkg_name] == [pkg_version]


def test_list_pkgs_no_context():
    """
    Test packages listing and ensure __context__ for pkg.list_pkgs is absent.

    :return:
    """

    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    apt_out = [
        "install ok installed accountsservice 0.6.55-0ubuntu12~20.04.1 amd64",
        "install ok installed acpid 1:2.0.32-1ubuntu1 amd64",
        "install ok installed adduser 3.118ubuntu2 all",
        "install ok installed alsa-topology-conf 1.2.2-1 all",
        "install ok installed alsa-ucm-conf 1.2.2-1ubuntu0.4 all",
        "install ok installed apparmor 2.13.3-7ubuntu5.1 amd64",
        "install ok installed apport 2.20.11-0ubuntu27.9 all",
        "install ok installed apport-symptoms 0.23 all",
        "install ok installed apt 2.0.2ubuntu0.1 amd64",
        "install ok installed apt-utils 2.0.2ubuntu0.1 amd64",
        "install ok installed at 3.1.23-1ubuntu1 amd64",
    ]
    with patch.dict(aptpkg.__grains__, {"osarch": "x86_64"}), patch.dict(
        aptpkg.__salt__,
        {"cmd.run_stdout": MagicMock(return_value=os.linesep.join(apt_out))},
    ), patch.dict(aptpkg.__salt__, {"pkg_resource.add_pkg": _add_data}), patch.dict(
        aptpkg.__salt__,
        {"pkg_resource.format_pkg_list": pkg_resource.format_pkg_list},
    ), patch.dict(
        aptpkg.__salt__, {"pkg_resource.sort_pkglist": pkg_resource.sort_pkglist}
    ), patch.object(
        aptpkg, "_list_pkgs_from_context"
    ) as list_pkgs_context_mock:
        pkgs = aptpkg.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()

        pkgs = aptpkg.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()


def test_call_apt_default():
    """
    Call default apt.
    :return:
    """
    with patch.dict(
        aptpkg.__salt__,
        {"cmd.run_all": MagicMock(), "config.get": MagicMock(return_value=False)},
    ):
        aptpkg._call_apt(["apt-get", "install", "emacs"])  # pylint: disable=W0106
        aptpkg.__salt__["cmd.run_all"].assert_called_once_with(
            ["apt-get", "install", "emacs"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )


@patch("salt.utils.systemd.has_scope", MagicMock(return_value=True))
def test_call_apt_in_scope():
    """
    Call apt within the scope.
    :return:
    """
    with patch.dict(
        aptpkg.__salt__,
        {"cmd.run_all": MagicMock(), "config.get": MagicMock(return_value=True)},
    ):
        aptpkg._call_apt(["apt-get", "purge", "vim"])  # pylint: disable=W0106
        aptpkg.__salt__["cmd.run_all"].assert_called_once_with(
            [
                "systemd-run",
                "--scope",
                "--description",
                '"salt.modules.aptpkg"',
                "apt-get",
                "purge",
                "vim",
            ],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )


def test_call_apt_with_kwargs():
    """
    Call apt with the optinal keyword arguments.
    :return:
    """
    with patch.dict(
        aptpkg.__salt__,
        {"cmd.run_all": MagicMock(), "config.get": MagicMock(return_value=False)},
    ):
        aptpkg._call_apt(
            ["dpkg", "-l", "python"],
            python_shell=True,
            output_loglevel="quiet",
            ignore_retcode=False,
            username="Darth Vader",
        )  # pylint: disable=W0106
        aptpkg.__salt__["cmd.run_all"].assert_called_once_with(
            ["dpkg", "-l", "python"],
            env={},
            ignore_retcode=False,
            output_loglevel="quiet",
            python_shell=True,
            username="Darth Vader",
        )


def test_call_apt_dpkg_lock():
    """
    Call apt and ensure the dpkg locking is handled
    :return:
    """
    cmd_side_effect = [
        {"stderr": "Could not get lock"},
        {"stderr": "Could not get lock"},
        {"stderr": "Could not get lock"},
        {"stderr": "Could not get lock"},
        {"stderr": "", "stdout": ""},
    ]

    cmd_mock = MagicMock(side_effect=cmd_side_effect)
    cmd_call = (
        call(
            ["dpkg", "-l", "python"],
            env={},
            ignore_retcode=False,
            output_loglevel="quiet",
            python_shell=True,
            username="Darth Vader",
        ),
    )
    expected_calls = [cmd_call * 5]

    with patch.dict(
        aptpkg.__salt__,
        {"cmd.run_all": cmd_mock, "config.get": MagicMock(return_value=False)},
    ):
        with patch("salt.modules.aptpkg.time.sleep", MagicMock()) as sleep_mock:
            aptpkg._call_apt(
                ["dpkg", "-l", "python"],
                python_shell=True,
                output_loglevel="quiet",
                ignore_retcode=False,
                username="Darth Vader",
            )  # pylint: disable=W0106

            # We should have sleept at least 4 times
            assert sleep_mock.call_count >= 4

            # We should attempt to call the cmd 5 times
            assert cmd_mock.call_count == 5
            cmd_mock.has_calls(expected_calls)


def test_services_need_restart_checkrestart_missing():
    """Test that the user is informed about the required dependency."""

    with patch("salt.utils.path.which_bin", Mock(return_value=None)):
        with pytest.raises(CommandNotFoundError):
            aptpkg.services_need_restart()


@patch("salt.utils.path.which_bin", Mock(return_value="/usr/sbin/checkrestart"))
def test_services_need_restart():
    """
    Test that checkrestart output is parsed correctly
    """
    cr_output = """
PROCESSES: 24
PROGRAMS: 17
PACKAGES: 8
SERVICE:rsyslog,385,/usr/sbin/rsyslogd
SERVICE:cups-daemon,390,/usr/sbin/cupsd
    """

    with patch.dict(aptpkg.__salt__, {"cmd.run_stdout": Mock(return_value=cr_output)}):
        assert sorted(aptpkg.services_need_restart()) == [
            "cups-daemon",
            "rsyslog",
        ]

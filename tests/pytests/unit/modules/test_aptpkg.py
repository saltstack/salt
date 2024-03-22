import copy
import importlib
import logging
import os
import pathlib
import textwrap

import pytest

import salt.modules.aptpkg as aptpkg
import salt.modules.pkg_resource as pkg_resource
import salt.utils.path
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    SaltInvocationError,
)
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, Mock, call, patch

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
        self.signedby = ""

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
                aptpkg.add_repo_key(
                    keyserver="keyserver.ubuntu.com",
                    keyid="FBB75451",
                    keyfile="test-key.gpg",
                )
                is True
            )


def test_add_repo_key_none_specified(repo_keys_var):
    """
    Test - Add a repo key when we do not specify any arguments
    """
    with patch(
        "salt.modules.aptpkg.get_repo_keys", MagicMock(return_value=repo_keys_var)
    ):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "OK"})
        with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
            with pytest.raises(TypeError) as err:
                aptpkg.add_repo_key()
        assert err.value.args[0] == "add_repo_key() takes at least 1 argument (0 given)"


def test_add_repo_key_no_keyfile(repo_keys_var, caplog, tmp_path):
    """
    Test - Add a repo key when aptkey is false
    and keyfile not specified when using a keyserver
    """
    with patch("salt.modules.aptpkg.get_repo_keys", MagicMock(return_value={})):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "OK"})
        with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
            ret = aptpkg.add_repo_key(
                keyserver="keyserver.ubuntu.com",
                keyid="FBB75451",
                keydir=tmp_path,
                aptkey=False,
            )
            assert ret is False
            assert (
                "You must define the name of the key file to save the key"
                in caplog.text
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


def test_add_repo_key_keydir_not_exists(repo_keys_var, tmp_path, caplog):
    """
    Test - Add a repo key when aptkey is False
    and the keydir does not exist
    """
    with patch(
        "salt.modules.aptpkg.get_repo_keys", MagicMock(return_value=repo_keys_var)
    ):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "OK"})
        with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
            ret = aptpkg.add_repo_key(
                keyserver="keyserver.ubuntu.com",
                keyid="FBB75451",
                keyfile="test-key.gpg",
                aptkey=False,
                keydir=str(tmp_path / "doesnotexist"),
            )
            assert "does not exist. Please create this directory" in caplog.text
            assert ret is False


@pytest.mark.parametrize(
    "kwargs, err_msg",
    [
        (
            {"keyid": "FBB75451", "keyfile": "test-key.gpg"},
            "No keyserver specified for keyid",
        ),
        (
            {"keyserver": "keyserver.ubuntu.com", "keyfile": "test-key.gpg"},
            "No keyid or keyid too short for keyserver",
        ),
    ],
)
def test_add_repo_key_keyserver_keyid_not_sepcified(
    repo_keys_var, tmp_path, caplog, kwargs, err_msg
):
    """
    Test - Add a repo key when and keyid is set without a keyserver
    Also test when keyserver is set but without keyid
    """
    short_key = list(repo_keys_var.keys())[0][-8:]
    with patch("salt.modules.aptpkg.get_repo_keys", MagicMock(return_value={})):
        mock = MagicMock(return_value={"retcode": 0, "stdout": "OK"})
        with patch.dict(aptpkg.__salt__, {"cmd.run_all": mock}):
            with pytest.raises(SaltInvocationError) as err:
                aptpkg.add_repo_key(**kwargs)
        assert err_msg in err.value.message


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
        with patch("os.listdir", return_value="/tmp/keys"):
            with patch("pathlib.Path.is_dir", return_value=True):
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


def test_owner_no_path():
    """
    Test owner when path is not passed
    """
    ret = aptpkg.owner()
    assert ret == ""


def test_owner_doesnotexist():
    """
    Test owner when the path does not exist
    """
    mock = MagicMock(return_value="")
    with patch.dict(aptpkg.__salt__, {"cmd.run_stdout": mock}):
        ret = aptpkg.owner("/doesnotexist")
        assert ret == ""


def test_get_http_proxy_url_username_passwd():
    """
    Test _get_http_proxy_url when username and passwod set
    """
    host = "repo.saltproject.io"
    port = "888"
    user = "user"
    passwd = "password"
    mock_conf = MagicMock()
    mock_conf.side_effect = [host, port, user, passwd]
    patch_conf = patch.dict(aptpkg.__salt__, {"config.option": mock_conf})
    with patch_conf:
        ret = aptpkg._get_http_proxy_url()
    assert ret == f"http://{user}:{passwd}@{host}:{port}"


def test_get_http_proxy_url():
    """
    Test basic functionality for _get_http_proxy_url
    """
    host = "repo.saltproject.io"
    port = "888"
    user = ""
    passwd = ""
    mock_conf = MagicMock()
    mock_conf.side_effect = [host, port, user, passwd]
    patch_conf = patch.dict(aptpkg.__salt__, {"config.option": mock_conf})
    with patch_conf:
        ret = aptpkg._get_http_proxy_url()
    assert ret == f"http://{host}:{port}"


def test_get_http_proxy_url_empty():
    """
    Test _get_http_proxy_Url when host and port are empty
    """
    host = ""
    port = ""
    user = ""
    passwd = ""
    mock_conf = MagicMock()
    mock_conf.side_effect = [host, port, user, passwd]
    patch_conf = patch.dict(aptpkg.__salt__, {"config.option": mock_conf})
    with patch_conf:
        ret = aptpkg._get_http_proxy_url()
    assert ret == ""


def test_list_upgrades():
    """
    Test basic functinoality for list_upgrades
    """
    patch_data = patch("salt.utils.data.is_true", return_value=True)
    patch_refresh = patch("salt.modules.aptpkg.refresh_db")
    apt_ret = {
        "pid": 2791,
        "retcode": 0,
        "stdout": "Reading package lists...\nBuilding dependency tree...\nReading state information...\nCalculating upgrade...\nThe following NEW packages will be installed:\n  linux-cloud-tools-5.15.0-86 linux-cloud-tools-5.15.0-86-generic\n  linux-headers-5.15.0-86 linux-headers-5.15.0-86-generic\n  linux-image-5.15.0-86-generic linux-modules-5.15.0-86-generic\n  linux-modules-extra-5.15.0-86-generic\nThe following packages have been kept back:\n  libnetplan0 libsgutils2-2 netplan. io sg3-utils sg3-utils-udev\nThe following packages will be upgraded:\n  linux-cloud-tools-virtual linux-generic linux-headers-generic\n  linux-image-generic\n4 upgraded, 7 newly installed, 0 to remove and 5 not upgraded.\nInst linux-cloud-tools-5.15.0-86 (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nInst linux-cloud-tools-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nInst linux-cloud-tools-virtual [5.15.0.69.67] (5.15.0.86.83 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nInst linux-modules-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64]) []\nInst linux-image-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nInst linux-modules-extra-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nInst linux-generic [5.15.0.69.67] (5.15.0.86.83 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64]) []\nInst linux-image-generic [5.15.0.69.67] (5.15.0.86.83 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64]) []\nInst linux-headers-5.15.0-86 (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [all]) []\nInst linux-headers-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64]) []\nInst linux-headers-generic [5.15.0.69.67] (5.15.0.86.83 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-cloud-tools-5.15.0-86 (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-cloud-tools-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-cloud-tools-virtual (5.15.0.86.83 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-modules-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-image-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-modules-extra-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-generic (5.15.0.86.83 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-image-generic (5.15.0.86.83 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-headers-5.15.0-86 (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [all])\nConf linux-headers-5.15.0-86-generic (5.15.0-86.96 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])\nConf linux-headers-generic (5.15.0.86.83 Ubuntu:22.04/jammy-updates, Ubuntu:22.04/jammy-security [amd64])",
        "stderr": "Running scope as unit: run-r014f3eae66364254b1cdacf701f1ab73.scope",
    }
    mock_apt = MagicMock(return_value=apt_ret)
    patch_apt = patch("salt.modules.aptpkg._call_apt", mock_apt)
    with patch_data, patch_refresh, patch_apt:
        ret = aptpkg.list_upgrades(dist_upgrade=False)
        assert ret == {
            "linux-cloud-tools-5.15.0-86": "5.15.0-86.96",
            "linux-cloud-tools-5.15.0-86-generic": "5.15.0-86.96",
            "linux-cloud-tools-virtual": "5.15.0.86.83",
            "linux-modules-5.15.0-86-generic": "5.15.0-86.96",
            "linux-image-5.15.0-86-generic": "5.15.0-86.96",
            "linux-modules-extra-5.15.0-86-generic": "5.15.0-86.96",
            "linux-generic": "5.15.0.86.83",
            "linux-image-generic": "5.15.0.86.83",
            "linux-headers-5.15.0-86": "5.15.0-86.96",
            "linux-headers-5.15.0-86-generic": "5.15.0-86.96",
            "linux-headers-generic": "5.15.0.86.83",
        }


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

    patch_kwargs = {
        "__salt__": {
            "pkg_resource.parse_targets": MagicMock(
                return_value=({"tmux": None}, "repository")
            ),
            "pkg_resource.sort_pkglist": MagicMock(),
            "pkg_resource.stringify": MagicMock(),
            "cmd.run_stdout": MagicMock(return_value="install ok installed python3\n"),
        }
    }
    mock_call_apt_ret = {
        "pid": 48174,
        "retcode": 0,
        "stdout": "Reading package lists...\nBuilding dependency tree...\nReading state information...\nvim is already the newest version (2:8.2.3995-1ubuntu2.4).\n",
        "stderr": "Running scope as unit: run-rc2803bccd0b445a5b00788cd74b4e635.scope",
    }
    mock_call_apt = MagicMock(return_value=mock_call_apt_ret)
    expected_call = call(
        [
            "apt-get",
            "-q",
            "-y",
            "-o",
            "DPkg::Options::=--force-confold",
            "-o",
            "DPkg::Options::=--force-confdef",
            "install",
            "tmux",
        ],
        scope=True,
    )
    with patch.multiple(aptpkg, **patch_kwargs):
        with patch(
            "salt.modules.aptpkg.get_selections", MagicMock(return_value={"hold": []})
        ):
            with patch("salt.modules.aptpkg._call_apt", mock_call_apt):
                ret = aptpkg.install(name="tmux", scope=True)
                assert expected_call in mock_call_apt.mock_calls


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


def test_upgrade_allow_downgrades(uninstall_var, upgrade_var):
    """
    Tests the allow_downgrades option for upgrade.
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
                    if "--allow-downgrades" in args
                ]
                # Here we shouldn't see the parameter and args_matching should be empty.
                assert any(args_matching) is False

                aptpkg.upgrade(allow_downgrades=True)
                args_matching = [
                    True
                    for args in patch_kwargs["__salt__"]["cmd.run_all"].call_args[0]
                    if "--allow-downgrades" in args
                ]
                # --allow-downgrades should be in the args list and we should have at least on True in the list.
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
    source_type = "deb"
    source_uri = "http://cdn-aws.deb.debian.org/debian/"
    source_line = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"

    mock_source = MockSourceEntry(source_uri, source_type, source_line, False)

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
                        "salt.modules.aptpkg.SourceEntry",
                        MagicMock(return_value=mock_source),
                        create=True,
                    ):
                        with patch("pathlib.Path", MagicMock()):
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
                                return_value={
                                    "type": "deb",
                                    "architectures": [],
                                    "uri": "http://cdn-aws.deb.debian.org/debian/",
                                    "dist": "stretch",
                                    "comps": ["main"],
                                    "signedby": "",
                                }
                            ),
                        ):
                            source_line_no_slash = (
                                "deb http://cdn-aws.deb.debian.org/debian"
                                " stretch main"
                            )
                            if salt.utils.path.which("apt-key"):
                                repo = aptpkg.mod_repo(
                                    source_line_no_slash, enabled=False
                                )
                                assert repo[source_line_no_slash]["uri"] == source_uri
                            else:
                                with pytest.raises(Exception) as err:
                                    repo = aptpkg.mod_repo(
                                        source_line_no_slash, enabled=False
                                    )
                                assert (
                                    "missing 'signedby' option when apt-key is missing"
                                    in str(err.value)
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
    with patch(
        "salt.utils.path.os_walk", MagicMock(return_value=[("test", "test", "test")])
    ), patch("os.path.getsize", MagicMock(return_value=123456)), patch(
        "os.path.getctime", MagicMock(return_value=1234567890.123456)
    ), patch(
        "fnmatch.filter",
        MagicMock(return_value=["/var/cache/apt/archive/test_package.rpm"]),
    ), patch.dict(
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


@pytest.mark.parametrize(
    "case",
    (
        {"ok": False, "line": "", "invalid": True, "disabled": False},
        {"ok": False, "line": "#", "invalid": True, "disabled": True},
        {"ok": False, "line": "##", "invalid": True, "disabled": True},
        {"ok": False, "line": "# comment", "invalid": True, "disabled": True},
        {"ok": False, "line": "## comment", "invalid": True, "disabled": True},
        {"ok": False, "line": "deb #", "invalid": True, "disabled": False},
        {"ok": False, "line": "# deb #", "invalid": True, "disabled": True},
        {"ok": False, "line": "deb [ invalid line", "invalid": True, "disabled": False},
        {
            "ok": True,
            "line": "# deb http://debian.org/debian/ stretch main\n",
            "invalid": False,
            "disabled": True,
        },
        {
            "ok": True,
            "line": "deb http://debian.org/debian/ stretch main # comment\n",
            "invalid": False,
            "disabled": False,
        },
        {
            "ok": True,
            "line": "deb [trusted=yes] http://debian.org/debian/ stretch main\n",
            "invalid": False,
            "disabled": False,
        },
        {
            "ok": True,
            "line": (
                "# deb cdrom:[Debian GNU/Linux 11.4.0 _Bullseye_ - Official amd64 NETINST 20220709-10:31]/ bullseye main\n"
                "\n"
                "deb http://httpredir.debian.org/debian bullseye main\n"
                "deb-src http://httpredir.debian.org/debian bullseye main\n"
            ),
            "invalid": False,
            "disabled": True,
        },
    ),
)
def test__parse_source(case):
    with patch.dict("sys.modules", {"aptsources.sourceslist": None}):
        importlib.reload(aptpkg)
        NoAptSourceEntry = aptpkg.SourceEntry
    importlib.reload(aptpkg)

    source = NoAptSourceEntry(case["line"])
    ok = source._parse_sources(case["line"])

    assert ok is case["ok"]
    assert source.invalid is case["invalid"]
    assert source.disabled is case["disabled"]


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


def test__expand_repo_def():
    """
    Checks results from _expand_repo_def
    """
    source_file = "/etc/apt/sources.list"

    # Valid source
    repo = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"
    sanitized = aptpkg._expand_repo_def(
        os_name="debian", os_codename="stretch", repo=repo, file=source_file
    )

    assert isinstance(sanitized, dict)
    assert "uri" in sanitized

    # Make sure last character in of the URI is still a /
    assert sanitized["uri"][-1] == "/"

    # Pass the architecture and make sure it is added the line attribute
    repo = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"
    sanitized = aptpkg._expand_repo_def(
        os_name="debian",
        os_codename="stretch",
        repo=repo,
        file=source_file,
        architectures="amd64",
    )

    # Make sure line is in the dict
    assert isinstance(sanitized, dict)
    assert "line" in sanitized

    # Make sure the architecture is in line
    assert (
        sanitized["line"]
        == "deb [arch=amd64] http://cdn-aws.deb.debian.org/debian/ stretch main"
    )


def test__expand_repo_def_cdrom():
    """
    Checks results from _expand_repo_def
    """
    source_file = "/etc/apt/sources.list"

    # Valid source
    repo = "# deb cdrom:[Debian GNU/Linux 11.4.0 _Bullseye_ - Official amd64 NETINST 20220709-10:31]/ bullseye main\n"
    sanitized = aptpkg._expand_repo_def(
        os_name="debian", os_codename="bullseye", repo=repo, file=source_file
    )

    assert isinstance(sanitized, dict)
    assert "uri" in sanitized

    # Make sure last character in of the URI is still a /
    assert sanitized["uri"][-1] == "/"

    # Pass the architecture and make sure it is added the line attribute
    repo = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"
    sanitized = aptpkg._expand_repo_def(
        os_name="debian",
        os_codename="stretch",
        repo=repo,
        file=source_file,
        architectures="amd64",
    )

    # Make sure line is in the dict
    assert isinstance(sanitized, dict)
    assert "line" in sanitized

    # Make sure the architecture is in line
    assert (
        sanitized["line"]
        == "deb [arch=amd64] http://cdn-aws.deb.debian.org/debian/ stretch main"
    )


def test_expand_repo_def_cdrom():
    """
    Checks results from expand_repo_def
    """
    source_file = "/etc/apt/sources.list"

    # Valid source
    repo = "# deb cdrom:[Debian GNU/Linux 11.4.0 _Bullseye_ - Official amd64 NETINST 20220709-10:31]/ bullseye main\n"
    sanitized = aptpkg._expand_repo_def(os_name="debian", repo=repo, file=source_file)
    log.debug("SAN: %s", sanitized)

    assert isinstance(sanitized, dict)
    assert "uri" in sanitized

    # Make sure last character in of the URI is still a /
    assert sanitized["uri"][-1] == "/"

    # Pass the architecture and make sure it is added the line attribute
    repo = "deb http://cdn-aws.deb.debian.org/debian/ stretch main\n"
    sanitized = aptpkg._expand_repo_def(
        os_name="debian", repo=repo, file=source_file, architectures="amd64"
    )

    # Make sure line is in the dict
    assert isinstance(sanitized, dict)
    assert "line" in sanitized

    # Make sure the architecture is in line
    assert (
        sanitized["line"]
        == "deb [arch=amd64] http://cdn-aws.deb.debian.org/debian/ stretch main"
    )


def test__expand_repo_def_not_repo():
    """
    Checks results from _expand_repo_def
    when repo is not in kwargs
    """
    with pytest.raises(SaltInvocationError) as err:
        aptpkg._expand_repo_def(
            os_name="debian",
            os_codename="stretch",
            architectures="amd64",
        )
    assert err.value.message == "missing 'repo' argument"


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


def test_call_apt_in_scope():
    """
    Call apt within the scope.
    :return:
    """
    with patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=True)
    ), patch.dict(
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
    cmd_call = [
        call(
            ["dpkg", "-l", "python"],
            output_loglevel="quiet",
            python_shell=True,
            env={},
            ignore_retcode=False,
            username="Darth Vader",
        ),
    ]
    expected_calls = cmd_call * 5

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
            cmd_mock.assert_has_calls(expected_calls)


def test_services_need_restart_checkrestart_missing():
    """Test that the user is informed about the required dependency."""

    with patch("salt.utils.path.which_bin", Mock(return_value=None)):
        with pytest.raises(CommandNotFoundError):
            aptpkg.services_need_restart()


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
    with patch(
        "salt.utils.path.which_bin", Mock(return_value="/usr/sbin/checkrestart")
    ), patch.dict(aptpkg.__salt__, {"cmd.run_stdout": Mock(return_value=cr_output)}):
        assert sorted(aptpkg.services_need_restart()) == [
            "cups-daemon",
            "rsyslog",
        ]


@pytest.fixture
def _test_sourceslist_multiple_comps_fs(fs):
    fs.create_dir("/etc/apt/sources.list.d")
    fs.create_file(
        "/etc/apt/sources.list",
        contents="deb http://archive.ubuntu.com/ubuntu/ focal-updates main restricted",
    )
    yield


@pytest.mark.usefixtures("_test_sourceslist_multiple_comps_fs")
def test_sourceslist_multiple_comps():
    """
    Test SourcesList when repo has multiple comps
    """
    sources = aptpkg.SourcesList()
    for source in sources:
        assert source.type == "deb"
        assert source.uri == "http://archive.ubuntu.com/ubuntu/"
        assert source.comps == ["main", "restricted"]
        assert source.dist == "focal-updates"


@pytest.fixture(
    params=(
        "deb [ arch=amd64 ] http://archive.ubuntu.com/ubuntu/ focal-updates main restricted",
        "deb [arch=amd64 ] http://archive.ubuntu.com/ubuntu/ focal-updates main restricted",
        "deb [arch=amd64 test=one ] http://archive.ubuntu.com/ubuntu/ focal-updates main restricted",
        "deb [arch=amd64,armel test=one ] http://archive.ubuntu.com/ubuntu/ focal-updates main restricted",
        "deb [ arch=amd64,armel test=one ] http://archive.ubuntu.com/ubuntu/ focal-updates main restricted",
        "deb [ arch=amd64,armel test=one] http://archive.ubuntu.com/ubuntu/ focal-updates main restricted",
        "deb [arch=amd64] http://archive.ubuntu.com/ubuntu/ focal-updates main restricted",
    )
)
def repo_line(request, fs):
    fs.create_dir("/etc/apt/sources.list.d")
    fs.create_file("/etc/apt/sources.list", contents=request.param)
    yield request.param


def test_sourceslist_architectures(repo_line):
    """
    Test SourcesList when architectures is in repo
    """
    sources = aptpkg.SourcesList()
    for source in sources:
        assert source.type == "deb"
        assert source.uri == "http://archive.ubuntu.com/ubuntu/"
        assert source.comps == ["main", "restricted"]
        assert source.dist == "focal-updates"
        if "," in repo_line:
            assert source.architectures == ["amd64", "armel"]
        else:
            assert source.architectures == ["amd64"]


@pytest.mark.parametrize(
    "pkg,arch",
    [
        ("zsh", "amd64"),
        ("php", "x86_64"),
    ],
)
def test_parse_arch(pkg, arch):
    """
    Test parse_arch when we pass in
    valid package and arch names
    """
    ret = aptpkg.parse_arch(f"{pkg}:{arch}")
    assert ret == {"name": pkg, "arch": arch}


@pytest.mark.parametrize(
    "pkg",
    [
        "php",
    ],
)
def test_parse_arch_invalid(pkg):
    """
    Test parse_arch when we pass in
    invalid package and arch names
    """
    ret = aptpkg.parse_arch(f"{pkg}")
    assert ret == {"name": pkg, "arch": None}


def test_latest_version_repo_kwarg():
    """
    Test latest_version when `repo` is passed in as a kwarg
    """
    with pytest.raises(SaltInvocationError) as exc:
        aptpkg.latest_version("php", repo="https://repo.com")
    assert exc.value.message == "The 'repo' argument is invalid, use 'fromrepo' instead"


def test_latest_version_names_empty():
    """
    Test latest_version when names is empty
    """
    ret = aptpkg.latest_version()
    assert ret == ""


def test_latest_version_fromrepo():
    """
    test latest_version when `fromrepo` is passed in as a kwarg
    """
    version = "5.15.0.86.83"
    fromrepo = "jammy-updates"
    list_ret = {"linux-cloud-tools-virtual": [version]}
    apt_ret = {
        "pid": 4361,
        "retcode": 0,
        "stdout": "linux-cloud-tools-virtual:\n"
        f"Installed: 5.15.0.69.67\n  Candidate: {version}\n  Version"
        f"table:\n     {version} 990\n 990"
        f"https://mirrors.edge.kernel.org/ubuntu {fromrepo}/main amd64"
        "Packages\n        500 https://mirrors.edge.kernel.org/ubuntu"
        "jammy-security/main amd64 Packages\n ***5.15.0.69.67 100\n"
        "100 /var/lib/dpkg/status\n     5.15.0.25.27 500\n        500"
        "https://mirrors.edge.kernel.org/ubuntu jammy/main amd64 Packages",
        "stderr": "",
    }
    mock_apt = MagicMock(return_value=apt_ret)
    patch_apt = patch("salt.modules.aptpkg._call_apt", mock_apt)
    mock_list_pkgs = MagicMock(return_value=list_ret)
    patch_list_pkgs = patch("salt.modules.aptpkg.list_pkgs", mock_list_pkgs)
    with patch_apt, patch_list_pkgs:
        ret = aptpkg.latest_version(
            "linux-cloud-tools-virtual",
            fromrepo=fromrepo,
            refresh=False,
            show_installed=True,
        )
        assert ret == version
        assert mock_apt.call_args == call(
            [
                "apt-cache",
                "-q",
                "policy",
                "linux-cloud-tools-virtual",
                "-o",
                f"APT::Default-Release={fromrepo}",
            ],
            scope=False,
        )


def test_latest_version_fromrepo_multiple_names():
    """
    test latest_version when multiple names of pkgs are pased
    """
    version = "5.15.0.86.83"
    fromrepo = "jammy-updates"
    list_ret = {
        "linux-cloud-tools-virtual": ["5.15.0.69.67"],
        "linux-generic": ["5.15.0.69.67"],
    }
    apt_ret = {
        "pid": 4361,
        "retcode": 0,
        "stdout": textwrap.dedent(
            f"""\
            linux-cloud-tools-virtual:
            Installed: 5.15.0.69.67
            Candidate: {version}
            Versiontable:
                {version} 990
            990https://mirrors.edge.kernel.org/ubuntu {fromrepo}/main amd64Packages
                    500 https://mirrors.edge.kernel.org/ubuntujammy-security/main amd64 Packages
            ***5.15.0.69.67 100
            100 /var/lib/dpkg/status
                5.15.0.25.27 500
                    500https://mirrors.edge.kernel.org/ubuntu jammy/main amd64 Packages
            linux-generic:
            Installed: 5.15.0.69.67
            Candidate: {version}
            Version table:
                {version} 990
                    990https://mirrors.edge.kernel.org/ubuntujammy-updates/main amd64 Packages
                    500https://mirrors.edge.kernel.org/ubuntujammy-security/main amd64 Packages
            *** 5.15.0.69.67100
                    100 /var/lib/dpkg/status
            5.15.0.25.27500
                    500 https://mirrors.edge.kernel.org/ubuntujammy/main amd64 Packages
        """
        ),
        "stderr": "",
    }

    mock_apt = MagicMock(return_value=apt_ret)
    patch_apt = patch("salt.modules.aptpkg._call_apt", mock_apt)
    mock_list_pkgs = MagicMock(return_value=list_ret)
    patch_list_pkgs = patch("salt.modules.aptpkg.list_pkgs", mock_list_pkgs)
    with patch_apt, patch_list_pkgs:
        ret = aptpkg.latest_version(
            "linux-cloud-tools-virtual",
            "linux-generic",
            fromrepo=fromrepo,
            refresh=False,
            show_installed=True,
        )
        assert ret == {"linux-cloud-tools-virtual": version, "linux-generic": version}
        mock_apt.assert_called_once_with(
            [
                "apt-cache",
                "-q",
                "policy",
                "linux-cloud-tools-virtual",
                "linux-generic",
                "-o",
                "APT::Default-Release=jammy-updates",
            ],
            scope=False,
        )


def test_hold():
    """
    test aptpkg.hold() when passing in the name of a package
    """
    set_sel = {"vim": {"old": "install", "new": "hold"}}
    get_sel = {"hold": []}
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", return_value=get_sel)
    patch_set_sel = patch("salt.modules.aptpkg.set_selections", return_value=set_sel)
    with patch_get_sel, patch_set_sel:
        ret = aptpkg.hold("vim")
    assert ret == {
        "vim": {
            "name": "vim",
            "changes": {"old": "install", "new": "hold"},
            "result": True,
            "comment": "Package vim is now being held.",
        }
    }


def test_hold_no_name_pkgs():
    """
    test aptpkg.hold when we do not pass in a name or list of pkgs
    """
    with pytest.raises(SaltInvocationError) as err:
        aptpkg.hold()
    assert err.value.message == "One of name, pkgs, or sources must be specified."


def test_hold_pkgs_sources():
    """
    test aptpkg.hold when we we set sources and a list of pkgs.
    """
    with pytest.raises(SaltInvocationError) as err:
        aptpkg.hold(
            pkgs=["vim", "apache2"], sources=["http://source1", "http://source2"]
        )
    assert err.value.message == "Only one of pkgs or sources can be specified."


@pytest.mark.parametrize(
    "sources",
    [
        [
            OrderedDict(
                [
                    (
                        "vim",
                        "https://mirrors.edge.kernel.org/ubuntu/pool/main/v/vim/vim_8.2.3995-1ubuntu2.12_amd64.deb",
                    )
                ]
            )
        ],
        [
            (
                "vim",
                "https://mirrors.edge.kernel.org/ubuntu/pool/main/v/vim/vim_8.2.3995-1ubuntu2.12_amd64.deb",
            )
        ],
    ],
)
def test_hold_sources(sources):
    """
    test aptpkg.hold when using sources
    """
    set_sel = {"vim": {"old": "install", "new": "hold"}}
    get_sel = {"hold": []}
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", return_value=get_sel)
    patch_set_sel = patch("salt.modules.aptpkg.set_selections", return_value=set_sel)
    with patch_get_sel, patch_set_sel:
        ret = aptpkg.hold(sources=sources)
    assert ret == {
        "vim": {
            "name": "vim",
            "changes": {"old": "install", "new": "hold"},
            "result": True,
            "comment": "Package vim is now being held.",
        }
    }


def test_hold_true():
    """
    test aptpkg.hold() when passing in the name of a package
    and test is True
    """
    set_sel = {"vim": {"old": "install", "new": "hold"}}
    get_sel = {"hold": []}
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", return_value=get_sel)
    patch_set_sel = patch("salt.modules.aptpkg.set_selections", return_value=set_sel)
    with patch_get_sel, patch_set_sel:
        with patch.dict(aptpkg.__opts__, {"test": True}):
            ret = aptpkg.hold("vim")
    assert ret == {
        "vim": {
            "name": "vim",
            "changes": {},
            "result": None,
            "comment": "Package vim is set to be held.",
        }
    }


def test_hold_already_set():
    """
    test aptpkg.hold() when the pkg is already set
    """
    get_sel = {"hold": ["vim"]}
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", return_value=get_sel)
    with patch_get_sel:
        ret = aptpkg.hold("vim")
    assert ret == {
        "vim": {
            "name": "vim",
            "changes": {},
            "result": True,
            "comment": "Package vim is already set to be held.",
        }
    }


def test_hold_pkgs():
    """
    test aptpkg.hold() when passing in pkgs
    """
    get_sel = {"hold": []}
    mock_set_sel = MagicMock()
    mock_set_sel.side_effect = [
        {"vim": {"old": "install", "new": "hold"}},
        {"vim-nox": {"old": "install", "new": "hold"}},
    ]
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", return_value=get_sel)
    patch_set_sel = patch("salt.modules.aptpkg.set_selections", mock_set_sel)
    with patch_get_sel, patch_set_sel:
        ret = aptpkg.hold(pkgs=["vim", "vim-nox"])
        assert ret == {
            "vim": {
                "name": "vim",
                "changes": {"old": "install", "new": "hold"},
                "result": True,
                "comment": "Package vim is now being held.",
            },
            "vim-nox": {
                "name": "vim-nox",
                "changes": {"old": "install", "new": "hold"},
                "result": True,
                "comment": "Package vim-nox is now being held.",
            },
        }


def test_unhold():
    """
    test aptpkg.unhold when passing pacakge as name
    """
    set_sel = {"vim": {"old": "hold", "new": "install"}}
    get_sel = {"hold": ["vim"]}
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", return_value=get_sel)
    patch_set_sel = patch("salt.modules.aptpkg.set_selections", return_value=set_sel)
    with patch_get_sel, patch_set_sel:
        ret = aptpkg.unhold("vim")
        assert ret == {
            "vim": {
                "name": "vim",
                "changes": {"old": "hold", "new": "install"},
                "result": True,
                "comment": "Package vim is no longer being held.",
            }
        }


def test_unhold_no_name_pkgs():
    """
    test aptpkg.unhold when we do not pass in a name or list of pkgs
    """
    with pytest.raises(SaltInvocationError) as err:
        aptpkg.unhold()
    assert err.value.message == "One of name, pkgs, or sources must be specified."


def test_unhold_pkgs_sources():
    """
    test aptpkg.unhold when we we set sources and a list of pkgs.
    """
    with pytest.raises(SaltInvocationError) as err:
        aptpkg.unhold(
            pkgs=["vim", "apache2"], sources=["http://source1", "http://source2"]
        )
    assert err.value.message == "Only one of pkgs or sources can be specified."


@pytest.mark.parametrize(
    "sources",
    [
        [
            OrderedDict(
                [
                    (
                        "vim",
                        "https://mirrors.edge.kernel.org/ubuntu/pool/main/v/vim/vim_8.2.3995-1ubuntu2.12_amd64.deb",
                    )
                ]
            )
        ],
        [
            (
                "vim",
                "https://mirrors.edge.kernel.org/ubuntu/pool/main/v/vim/vim_8.2.3995-1ubuntu2.12_amd64.deb",
            )
        ],
    ],
)
def test_unhold_sources(sources):
    """
    test aptpkg.unhold when using sources
    """
    set_sel = {"vim": {"old": "hold", "new": "install"}}
    get_sel = {"hold": ["vim"]}
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", return_value=get_sel)
    patch_set_sel = patch("salt.modules.aptpkg.set_selections", return_value=set_sel)
    with patch_get_sel, patch_set_sel:
        ret = aptpkg.unhold(sources=sources)
    assert ret == {
        "vim": {
            "name": "vim",
            "changes": {"old": "hold", "new": "install"},
            "result": True,
            "comment": "Package vim is no longer being held.",
        }
    }


def test_unhold_true():
    """
    test aptpkg.unhold() when passing in the name of a package
    and test is True
    """
    set_sel = {"vim": {"old": "install", "new": "hold"}}
    get_sel = {"hold": ["vim"]}
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", return_value=get_sel)
    patch_set_sel = patch("salt.modules.aptpkg.set_selections", return_value=set_sel)
    with patch_get_sel, patch_set_sel:
        with patch.dict(aptpkg.__opts__, {"test": True}):
            ret = aptpkg.unhold("vim")
    assert ret == {
        "vim": {
            "name": "vim",
            "changes": {},
            "result": None,
            "comment": "Package vim is set not to be held.",
        }
    }


def test_unhold_already_set():
    """
    test aptpkg.unhold() when the pkg is already set
    """
    get_sel = {"install": ["vim"]}
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", return_value=get_sel)
    with patch_get_sel:
        ret = aptpkg.unhold("vim")
    assert ret == {
        "vim": {
            "name": "vim",
            "changes": {},
            "result": True,
            "comment": "Package vim is already set not to be held.",
        }
    }


def test_unhold_pkgs():
    """
    test aptpkg.hold() when passing in pkgs
    """
    mock_get_sel = MagicMock()
    mock_get_sel.side_effect = [{"hold": ["vim"]}, {"hold": ["vim-nox"]}]
    mock_set_sel = MagicMock()
    mock_set_sel.side_effect = [
        {"vim": {"old": "hold", "new": "install"}},
        {"vim-nox": {"old": "hold", "new": "install"}},
    ]
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", mock_get_sel)
    patch_set_sel = patch("salt.modules.aptpkg.set_selections", mock_set_sel)
    with patch_get_sel, patch_set_sel:
        ret = aptpkg.unhold(pkgs=["vim", "vim-nox"])
        assert ret == {
            "vim": {
                "name": "vim",
                "changes": {"old": "hold", "new": "install"},
                "result": True,
                "comment": "Package vim is no longer being held.",
            },
            "vim-nox": {
                "name": "vim-nox",
                "changes": {"old": "hold", "new": "install"},
                "result": True,
                "comment": "Package vim-nox is no longer being held.",
            },
        }


def test_get_key_from_id_keylength_not_valid(tmp_path, caplog):
    """
    test _get_key_from_id when the keyid lenght is not valid
    """
    ret = aptpkg._get_key_from_id(tmp_path, "FBB754512")
    assert ret is False
    assert "The keyid needs to be either 8 or 16 characters" in caplog.text


def test_get_key_from_id_not_added(tmp_path, caplog):
    """
    test _get_key_from_id when the keyfile is not added
    """
    ret = aptpkg._get_key_from_id(tmp_path, "FBB75451")
    assert ret is False
    assert "Could not find the key file for keyid" in caplog.text


def test_del_repo_key_keydir_doesnotexist(tmp_path, caplog):
    """
    test del_repo_key when keydir does not exist and aptkey is False
    """
    ret = aptpkg.del_repo_key(
        keyid="0E08A149DE57BFBE", keydir=str(tmp_path / "keydir"), aptkey=False
    )
    assert ret is False
    assert "does not exist. Please create this directory" in caplog.text


def test_del_repo_key_keyid_doesnotexist(tmp_path, caplog):
    """
    test del_repo_key when keyid is not passed in
    """
    with patch("salt.utils.path.which", return_value=False):
        with pytest.raises(SaltInvocationError) as err:
            ret = aptpkg.del_repo_key(keydir=tmp_path, aptkey=False)

    assert err.value.message == "keyid or keyid_ppa and PPA name must be passed"


def test_del_repo_key_keyfile_doesnotexist(tmp_path, caplog):
    """
    test del_repo_key when keyfile does not exist
    """
    with patch("salt.utils.path.which", return_value=False):
        ret = aptpkg.del_repo_key(
            keyid="0E08A149DE57BFBE", keydir=tmp_path, aptkey=False
        )
        assert ret is False


def test_set_selections():
    """
    test set_selections() with valid state
    """
    pkg = "salt-minion"
    mock_get_sel = MagicMock(
        return_value={
            "install": ["adduser", pkg, "apparmor"],
            "deinstall": ["python3-json-pointer"],
        }
    )
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", mock_get_sel)
    mock_call_apt = MagicMock(
        return_value={"pid": 8748, "retcode": 0, "stdout": "", "stderr": ""}
    )
    patch_call_apt = patch("salt.modules.aptpkg._call_apt", mock_call_apt)
    patch_opts = patch.dict(aptpkg.__opts__, {"test": False})
    with patch_get_sel, patch_call_apt, patch_opts:
        ret = aptpkg.set_selections(selection=f'{{"hold": [{pkg}]}}')
    assert ret == {pkg: {"old": "install", "new": "hold"}}


def test_set_selections_no_path_selection():
    """
    test set_selections() when path or selection are not passed
    """
    pkg = "salt-minion"
    mock_get_sel = MagicMock(
        return_value={
            "install": ["adduser", pkg, "apparmor"],
            "deinstall": ["python3-json-pointer"],
        }
    )
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", mock_get_sel)
    mock_call_apt = MagicMock(
        return_value={"pid": 8748, "retcode": 0, "stdout": "", "stderr": ""}
    )
    patch_call_apt = patch("salt.modules.aptpkg._call_apt", mock_call_apt)
    patch_opts = patch.dict(aptpkg.__opts__, {"test": False})
    with patch_get_sel, patch_call_apt, patch_opts:
        ret = aptpkg.set_selections()
    assert ret == {}


def test_set_selections_path_and_selection(tmp_path):
    """
    test set_selections() when path and selection are passed
    """
    pkg = "salt-minion"
    mock_get_sel = MagicMock(
        return_value={
            "install": ["adduser", pkg, "apparmor"],
            "deinstall": ["python3-json-pointer"],
        }
    )
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", mock_get_sel)
    mock_call_apt = MagicMock(
        return_value={"pid": 8748, "retcode": 0, "stdout": "", "stderr": ""}
    )
    patch_call_apt = patch("salt.modules.aptpkg._call_apt", mock_call_apt)
    patch_opts = patch.dict(aptpkg.__opts__, {"test": False})
    with patch_get_sel, patch_call_apt, patch_opts:
        with pytest.raises(SaltInvocationError) as err:
            ret = aptpkg.set_selections(selection=f'{{"hold": [{pkg}]}}', path=tmp_path)
    assert "The 'selection' and 'path' arguments" in err.value.message


def test_set_selections_invalid_yaml():
    """
    test set_selections() with invalid yaml with selections
    """
    pkg = "salt-minion"
    mock_get_sel = MagicMock(
        return_value={
            "install": ["adduser", pkg, "apparmor"],
            "deinstall": ["python3-json-pointer"],
        }
    )
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", mock_get_sel)
    mock_call_apt = MagicMock(
        return_value={"pid": 8748, "retcode": 0, "stdout": "", "stderr": ""}
    )
    patch_call_apt = patch("salt.modules.aptpkg._call_apt", mock_call_apt)
    patch_opts = patch.dict(aptpkg.__opts__, {"test": False})
    with patch_get_sel, patch_call_apt, patch_opts:
        with pytest.raises(SaltInvocationError) as err:
            aptpkg.set_selections(selection='{{"hold": [{pkg}]}')
    assert "Improperly-formatted selection" in err.value.message


def test_set_selections_path(tmp_path):
    """
    test set_selections() with path
    """
    pkg = "salt-minion"
    select_file = tmp_path / "select"
    mock_get_sel = MagicMock(
        return_value={
            "install": ["adduser", pkg, "apparmor"],
            "deinstall": ["python3-json-pointer"],
        }
    )
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", mock_get_sel)
    mock_call_apt = MagicMock(
        return_value={"pid": 8748, "retcode": 0, "stdout": "", "stderr": ""}
    )
    patch_call_apt = patch("salt.modules.aptpkg._call_apt", mock_call_apt)
    patch_opts = patch.dict(aptpkg.__opts__, {"test": False})
    patch_salt = patch.dict(
        aptpkg.__salt__, {"cp.cache_file": MagicMock(return_value=select_file)}
    )

    with salt.utils.files.fopen(select_file, "w") as fp:
        fp.write("salt-minion hold\n adduser hold")
    with patch_get_sel, patch_call_apt, patch_opts, patch_salt:
        ret = aptpkg.set_selections(path=str(select_file))
        assert ret == {
            pkg: {"old": "install", "new": "hold"},
            "adduser": {"old": "install", "new": "hold"},
        }


def test_set_selections_invalid_state():
    """
    test set_selections() with invalid state
    """
    pkg = "salt-minion"
    mock_get_sel = MagicMock(
        return_value={
            "install": ["adduser", pkg, "apparmor"],
            "deinstall": ["python3-json-pointer"],
        }
    )
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", mock_get_sel)
    mock_call_apt = MagicMock(
        return_value={"pid": 8748, "retcode": 0, "stdout": "", "stderr": ""}
    )
    patch_call_apt = patch("salt.modules.aptpkg._call_apt", mock_call_apt)
    patch_opts = patch.dict(aptpkg.__opts__, {"test": False})
    with patch_get_sel, patch_call_apt, patch_opts:
        with pytest.raises(SaltInvocationError) as err:
            aptpkg.set_selections(selection=f'{{"doesnotexist": [{pkg}]}}')

    assert err.value.message == "Invalid state(s): doesnotexist"


def test_set_selections_test():
    """
    test set_selections() with valid state and test is True in opts
    """
    pkg = "salt-minion"
    mock_get_sel = MagicMock(
        return_value={
            "install": ["adduser", pkg, "apparmor"],
            "deinstall": ["python3-json-pointer"],
        }
    )
    patch_get_sel = patch("salt.modules.aptpkg.get_selections", mock_get_sel)
    mock_call_apt = MagicMock(
        return_value={"pid": 8748, "retcode": 0, "stdout": "", "stderr": ""}
    )
    patch_call_apt = patch("salt.modules.aptpkg._call_apt", mock_call_apt)
    patch_opts = patch.dict(aptpkg.__opts__, {"test": True})
    with patch_get_sel, patch_call_apt, patch_opts:
        ret = aptpkg.set_selections(selection=f'{{"hold": [{pkg}]}}')
    assert ret == {}


def test_latest_version_calls_aptcache_once_per_run():
    """
    Performance Test - don't call apt-cache once for each pkg, call once and parse output
    """
    mock_list_pkgs = MagicMock(return_value={"sudo": "1.8.27-1+deb10u5"})
    apt_cache_ret = {
        "stdout": textwrap.dedent(
            """sudo:
              Installed: 1.8.27-1+deb10u5
              Candidate: 1.8.27-1+deb10u5
              Version table:
             *** 1.8.27-1+deb10u5 500
                    500 http://security.debian.org/debian-security buster/updates/main amd64 Packages
                    100 /var/lib/dpkg/status
                 1.8.27-1+deb10u3 500
                    500 http://deb.debian.org/debian buster/main amd64 Packages
            unzip:
              Installed: (none)
              Candidate: 6.0-23+deb10u3
              Version table:
                 6.0-23+deb10u3 500
                    500 http://security.debian.org/debian-security buster/updates/main amd64 Packages
                 6.0-23+deb10u2 500
                    500 http://deb.debian.org/debian buster/main amd64 Packages
            """
        )
    }
    mock_apt_cache = MagicMock(return_value=apt_cache_ret)
    with patch("salt.modules.aptpkg._call_apt", mock_apt_cache), patch(
        "salt.modules.aptpkg.list_pkgs", mock_list_pkgs
    ):
        ret = aptpkg.latest_version("sudo", "unzip", refresh=False)
    mock_apt_cache.assert_called_once()
    assert ret == {"sudo": "6.0-23+deb10u3", "unzip": ""}
